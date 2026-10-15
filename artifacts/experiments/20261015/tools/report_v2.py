"""Recompute public scores, source provenance and Boolean certificates for V2."""
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(sys.argv[1])


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x]


def paired(records, left, right):
    a = {r['index']: r for r in records if r['variant'] == left}
    b = {r['index']: r for r in records if r['variant'] == right}
    assert a.keys() == b.keys()
    gains = sum(a[i]['em'] == 0 and b[i]['em'] == 1 for i in a)
    losses = sum(a[i]['em'] == 1 and b[i]['em'] == 0 for i in a)
    differences = [b[i]['em']-a[i]['em'] for i in sorted(a)]
    rng = random.Random(20261015)
    boot = sorted(sum(rng.choices(differences, k=len(differences)))/len(differences) for _ in range(10000))
    n = gains+losses
    p = min(1.0, 2*sum(math.comb(n, k) for k in range(min(gains, losses)+1))/2**n) if n else 1.0
    return {'left': left, 'right': right, 'gains': gains, 'losses': losses,
            'delta': sum(differences)/len(differences), 'paired_bootstrap_95ci': [boot[249], boot[9749]],
            'mcnemar_exact_two_sided_p': p}


def wilson(successes, n):
    z = 1.95996398454
    p = successes/n
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [center-half, center+half]


def pct(value):
    return '-' if value is None else f'{100*value:.2f}%'


def table(summary):
    names = {'baseline': '原基础LightRAG', 'previous_recovery': '上一轮仅补检索', 'v2_context': 'V2检索/上下文，不加验证',
             'v2_verify': 'V2验证与逻辑纠正', 'v2_full': 'V2完整流程'}
    result = ['|方案|EM|F1|可回答题EM|作答率|已作答EM|非空错答|平均图检索次数|', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for variant, item in summary.items():
        result.append(f"|{names[variant]}|{pct(item['em'])}|{pct(item['f1'])}|{pct(item['answerable_em'])}|"
                      f"{pct(item['coverage'])}|{pct(item['selective_accuracy'])}|{item['wrong_nonempty']}|{item['mean_graph_calls']:.2f}|")
    return '\n'.join(result)


def kind_table(summary):
    result = ['|题型|题数|基础EM|V2未验证EM|V2 full EM|', '|---|---:|---:|---:|---:|']
    for kind, item in summary['v2_full']['by_kind'].items():
        result.append(f"|{kind}|{item['n']}|{pct(summary['baseline']['by_kind'][kind]['em'])}|"
                      f"{pct(summary['v2_context']['by_kind'][kind]['em'])}|{pct(item['em'])}|")
    return '\n'.join(result)


protocol, frozen = read(ROOT/'protocol.json'), read(ROOT/'freeze.json')
for relative, expected in frozen['source_sha256'].items():
    assert hashlib.sha256((ROOT/'project'/relative).read_bytes()).hexdigest() == expected, relative
assert hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest() == frozen['protocol_sha256']
for relative, expected in read(ROOT/'baseline_source_sha256.json').items():
    if relative != 'evidencechain/factory.py':
        assert hashlib.sha256((ROOT/'project/src'/relative).read_bytes()).hexdigest() == expected, relative
sys.path.insert(0, str(ROOT/'project/src'))
from evidencechain.metrics import answer_em, answer_f1
from evidencechain.parent_retrieval import corpus_documents
from evidencechain.boolean_verifier import validate_logic, evaluate_logic, complete_documents

dataset = read(ROOT/'data/public_raw/MultiHopRAG/MultiHopRAG.json')
corpus = {doc.document_id: doc for doc in corpus_documents(read(ROOT/'data/public_raw/MultiHopRAG/corpus.json'))}
assert len(corpus) == 609
assert set(protocol['test_indices']).isdisjoint(protocol['previous_test_indices_excluded'])
assert set(protocol['test_indices']).isdisjoint(protocol['dev_indices']+protocol['validation_indices'])
assert 0 not in protocol['test_indices']
question_key = lambda q: ' '.join(q.casefold().split())
old_questions = {question_key(dataset[i]['query']) for i in protocol['previous_test_indices_excluded']}
text_overlap = [i for i in protocol['test_indices'] if question_key(dataset[i]['query']) in old_questions]
development_questions = {question_key(dataset[i]['query'])
                         for i in protocol['dev_indices']+protocol['validation_indices']}
development_overlap = [i for i in protocol['test_indices']
                       if question_key(dataset[i]['query']) in development_questions]
validation, test = rows(ROOT/'results/validation/records.jsonl'), rows(ROOT/'results/test/records.jsonl')
assert len(validation) == 200 and len(test) == 500
summaries = {stage: read(ROOT/f'results/{stage}/summary.json') for stage in ['validation', 'test']}
for stage, records in [('validation', validation), ('test', test)]:
    manifest = read(ROOT/f'results/{stage}/manifest.json')
    assert manifest['source_sha256'] == frozen['source_sha256']
    assert {(r['index'], r['variant']) for r in records} == {(i, v) for i in protocol[f'{stage}_indices'] for v in protocol['variants']}
    for variant in protocol['variants']:
        group = [r for r in records if r['variant'] == variant]
        saved = summaries[stage][variant]
        assert saved['n'] == len(group)
        for score in ['em', 'f1']:
            assert math.isclose(saved[score], sum(r[score] for r in group)/len(group))

all_records = validation+test
dev_summaries = {}
for folder in sorted((ROOT/'results/dev').iterdir()):
    if folder.is_dir() and (folder/'records.jsonl').exists():
        all_records += rows(folder/'records.jsonl')
        dev_summaries[folder.name] = read(folder/'summary.json')
boolean_certificates = 0
for record in all_records:
    error = record['generation_format_error']
    assert record['em'] == (0 if error else answer_em(record['output']['answer'], record['scoring_gold']))
    assert record['f1'] == (0 if error else answer_f1(record['output']['answer'], record['scoring_gold']))
for record in validation+test:
    output = record['output']
    if not record['variant'].startswith('v2_'):
        continue
    assert len(output['attempts']) <= 2 and len(output['evidence']) <= 32
    assert output['retrieval']['calls'] <= 4
    assert sum(len(e['content']) for e in output['evidence']) <= 96000
    known = {e['evidence_id']: e for e in output['evidence']}
    assert len(known) == len(output['evidence'])
    for identifier, evidence in known.items():
        parent = corpus[evidence['source']]
        span = output['provenance'][identifier]
        assert span['body_total_chars'] == len(parent.body)
        assert evidence['content'] == parent.header+'\nBody:\n'+parent.body[span['body_start']:span['body_end']]
    report = output.get('verification')
    if output['abstained'] or report is None:
        continue
    assert report['accepted'] and output['citation_ids']
    for verdict in report['verdicts']:
        assert verdict['support_ids']
        for citation in verdict['citations']:
            assert citation['id'] in known
            assert citation['quote'] == known[citation['id']]['content']
    if report['method'] == 'candidate-blind-atoms-plus-three-valued-logic':
        validate_logic(report['logic'])
        values = {c['id']: True if c['status'] == 'supported' else False if c['status'] == 'refuted' else None
                  for c in report['atom_checks']}
        truth, proof = evaluate_logic(report['logic']['expression'], values)
        assert truth is not None
        assert output['answer'] == ('Yes' if truth else 'No')
        assert proof == set(report['certificate_atoms'])
        boolean_certificates += 1
for records in [validation, test]:
    for index in {r['index'] for r in records}:
        group = {r['variant']: r['output'] for r in records if r['index'] == index}
        base = group['v2_context']
        for variant in ['v2_verify', 'v2_full']:
            assert group[variant]['attempts'][0]['prediction'] == base['attempts'][0]['prediction']
            assert group[variant]['evidence'][:len(base['evidence'])] == base['evidence']

controls = rows(ROOT/'results/verifier_controls.jsonl')
assert len(controls) == 25
assert all(r['passed'] for r in controls)
smoke = read(ROOT/'results/factory_smoke.json')
assert smoke['development_index'] in protocol['dev_indices']
assert smoke['output']['evidence'] and smoke['output']['attempts']
with (ROOT/'results/per_question_scores.csv').open('w', encoding='utf-8-sig', newline='') as out:
    writer = csv.DictWriter(out, fieldnames=['stage', 'index', 'variant', 'question_type', 'query',
                                            'gold', 'answer', 'em', 'f1', 'abstained',
                                            'graph_calls', 'generation_attempts', 'verification_method'])
    writer.writeheader()
    for stage, records in [('validation', validation), ('test', test)]:
        for record in records:
            output = record['output']
            writer.writerow({'stage': stage, 'index': record['index'], 'variant': record['variant'],
                             'question_type': record['question_type'], 'query': record['query'],
                             'gold': record['scoring_gold'], 'answer': output['answer'],
                             'em': record['em'], 'f1': record['f1'], 'abstained': output['abstained'],
                             'graph_calls': output['retrieval']['calls'],
                             'generation_attempts': len(output.get('attempts') or []),
                             'verification_method': (output.get('verification') or {}).get('method', '')})
usage = rows(ROOT/'results/api_usage.jsonl')
assert all(r['time'] >= frozen['time'] for r in usage if r['stage'] == 'test')
tokens = Counter()
for entry in usage:
    for name, value in (entry.get('usage') or {}).items():
        if isinstance(value, (float, int)):
            tokens[name] += value
api = {'response_records': len(usage), 'tokens': dict(tokens),
       'by_stage_purpose': dict(Counter(r['stage']+':'+r['purpose'] for r in usage)),
       'returned_models': dict(Counter(r['model'] for r in usage))}
comparisons = [paired(test, left, right) for left, right in [
    ('baseline', 'v2_full'), ('previous_recovery', 'v2_full'), ('v2_context', 'v2_verify'), ('v2_verify', 'v2_full')]]
main = summaries['test']['v2_full']
interval = wilson(sum(r['em'] for r in test if r['variant'] == 'v2_full'), 100)
gpu = {stage: read(ROOT/f'results/gpu_{stage}_summary.json') for stage in ['validation', 'test']}
peak_mib = max(v['peak_device_memory_mib'] for v in gpu.values())
full_records = [r for r in test if r['variant'] == 'v2_full']
boolean_records = [r for r in full_records if (r['output'].get('verification') or {}).get('method') == 'candidate-blind-atoms-plus-three-valued-logic' and not r['output']['abstained']]
corrections = [r for r in boolean_records if r['output']['verification'].get('answer_corrected')]
correction_transitions = dict(Counter((r['output']['candidate_answer'] or '<empty>')+' -> '+r['output']['answer']
                                      for r in corrections))
audit = {'primary_records': 700, 'all_scored_records': len(all_records), 'source_and_protocol_freeze': 'verified',
         'scores_recomputed': True, 'parent_spans_and_citations': 'verified', 'paired_first_pass': 'verified',
         'boolean_certificates_recomputed': boolean_certificates, 'test_text_overlap_previous200': text_overlap,
         'test_text_overlap_dev_validation': development_overlap,
         'target80_met_on_test100': main['em'] >= .80, 'test_v2_full_em_wilson95': interval,
         'dev': dev_summaries, 'validation': summaries['validation'], 'test': summaries['test'],
         'paired_comparisons': comparisons, 'controls': {'n': len(controls), 'passed': sum(r['passed'] for r in controls)},
         'test_boolean_outputs': len(boolean_records), 'test_corrected_candidates': len(corrections),
         'test_correction_transitions': correction_transitions,
         'test_corrected_candidates_em': sum(r['em'] for r in corrections)/len(corrections) if corrections else None,
         'api': api, 'gpu': gpu}
(ROOT/'results/audit_and_comparison.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
examples = {'corrected_candidates_first5': corrections[:5],
            'accepted_em_mismatches_first5': [r for r in full_records if not r['output']['abstained'] and not r['em']][:5],
            'remaining_abstentions_first5': [r for r in full_records if r['answerable'] and r['output']['abstained']][:5]}
(ROOT/'results/examples_and_remaining_failures.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding='utf-8')

status = '达到' if audit['target80_met_on_test100'] else '尚未达到'
report = f'''# LightRAG V2：检索与验证器优化验收

## 结论

固定版本 V2 full 在新留出100题上的 EM 为 **{pct(main['em'])}**，F1为 **{pct(main['f1'])}**，本次抽样{status}80%目标。
这是全100题的得分，不是只计算已作答题的精度，也不是官方完整榜单成绩。
EM的Wilson95%区间为 [{pct(interval[0])}, {pct(interval[1])}]；小样本达到80%不保证总体准确率至少80%。
已作答EM为 {pct(main['selective_accuracy'])}，作答率为 {pct(main['coverage'])}，可回答题EM为 {pct(main['answerable_em'])}。

**验证器没有独立提分：** 未验证V2为 {pct(summaries['test']['v2_context']['em'])}，加入验证后为 {pct(summaries['test']['v2_verify']['em'])}，
新增答对{comparisons[2]['gains']}题、丢失{comparisons[2]['losses']}题；非空错答从{summaries['test']['v2_context']['wrong_nonempty']}题降到{main['wrong_nonempty']}题。
本次整体提升主要来自召回、父上下文和结构化生成的组合，不应宣传成“验证器本身带来31个百分点提升”。
额外修复检索相对仅验证分支的净EM收益为{100*comparisons[3]['delta']:+.2f}个百分点；本轮没有证明这部分额外开销能提高得分。

## 新留出集100题

{table(summaries['test'])}

{kind_table(summaries['test'])}

基线和上一轮仅补检索也重新运行在同一批新题上；不能直接拿上一批100题的48%/51%作严格配对比较。
本轮采用同一609篇英语新闻语料、BGE-M3及DeepSeek-flash，另加BGE重排序和更宽上下文，计算预算高于原top8方案。
V2未验证分支也使用新的结构化生成提示，因此它相对基础方案的收益是召回、上下文与生成的合并收益，不能单独归因于重排序。
基础方案有{summaries['test']['baseline']['format_errors']}条生成格式错误，V2 full有{main['format_errors']}条；按照预定规则计零，不删除样本。工程格式稳健性也是本轮合并改动的一部分。

## 独立验证集40题

{table(summaries['validation'])}

## 开发过程完整记录

|轮次|基础EM|V2未验证EM|V2验证EM|V2 full EM|
|---|---:|---:|---:|---:|
'''
for trial, summary in dev_summaries.items():
    report += f"|{trial}|{pct(summary['baseline']['em'])}|{pct(summary['v2_context']['em'])}|{pct(summary['v2_verify']['em'])}|{pct(summary['v2_full']['em'])}|\n"
report += f'''
开发集仅24题，以上多轮结果是开发诊断，不能替代留出测试。失败轮次、提示词及源代码快照均保留。
trial1采用原子事实与关系审查；trial2修正否定措辞、引用数量和作者元数据；trial3尝试严格原子命题/布尔验证，误拒过多；trial4保留原子逻辑纠正，并以有效联合证据证明作为补充路径，修复解析失败导致检索分解丢失的问题。
最终版本在验证前选定，完成验证后冻结源代码/协议哈希，再运行新测试100题；没有根据新测试结果继续调参。

## 为什么此前不提升

原流程只给生成器每段前1800字符，网页头部噪声和跨文档事实缺失限制了候选质量。原验证器又混淆了题干真假、候选答案真假和跨源关系，特别容易误杀正确的No答案。
开发样例中出现“理由说明No正确、标签却写refuted”，也出现源事实正确但最终Yes/No极性错误。单纯调整阈值无法解决这种逻辑不一致。

## 本次改动

1. 使用 rank-bm25、LightRAG 图/向量召回、标准RRF(k60)及BGE交叉编码器重排。对每个分问题保留相关片段，减少同主题片段挤占全部上下文。
2. 根据精确字符偏移展开原文，保留标题、作者、来源、发表时间。初始上下文上限64000字符；有余量时补全不超过12000字符的父文档，不再只截取段落开头。
3. 对Yes/No问题，模型在看不到候选答案的情况下核查源限定原子命题；程序用有边界的and/or/not三值逻辑计算答案。未知不当作False，题干被反驳可以正是No正确的证据。
4. 当逻辑解析失败或原子证据不足时，允许另一条联合证据核验路径给出明确证明；不是把未知自动放行。引用无效和未解决原子冲突不会走该补充路径。
5. 核验命题可直接纠正候选Yes/No。原候选、最终答案、改正标记、逻辑表达式及决定性证据全部保存。未验证分支与验证分支使用相同首轮候选。
6. 缺证据时最多补两条查询；桥接实体必须已出现在检索原文中。最多两次生成、两轮验证，每轮至多两种审查。保留初始证据，最终上限96000字符/32段，最多4次图检索。
7. 引用由程序从真实段落复制，模型只选择已知编号。非提及证明仅适用于完整报告文本，不能用文章没提某事来证明现实中没发生。

本轮测试中有 {len(boolean_records)} 条最终输出由原子命题的布尔证据链产生，其中 {len(corrections)} 条标记了候选纠正；该组EM为 {pct(audit['test_corrected_candidates_em'])}。
纠正方向为 {json.dumps(correction_transitions, ensure_ascii=False)}；`<empty>`表示原生成器没有给出答案，后由独立命题核查形成有据答案。
这不意味着每次纠正都正确。模型仍可能误解析问题或误判原子事实；引用真实也不等于逻辑与语义必然正确。

## 配对收益与损失

'''
for item in comparisons:
    low, high = item['paired_bootstrap_95ci']
    report += (f"- {item['right']} 相对 {item['left']}：{100*item['delta']:+.2f}个百分点，"
               f"新增答对{item['gains']}题、丢失{item['losses']}题；配对bootstrap95%区间"
               f"[{100*low:+.2f}, {100*high:+.2f}]，精确McNemar双侧p={item['mcnemar_exact_two_sided_p']:.4g}。\n")
report += f'''
以上为探索性、未多重比较校正的统计量；问题共享文章，独立同分布假设并不完全成立。
V2 context与V2 verify的差异包含验证、逻辑纠正及额外审查计算；不是训练出更大模型的结果。

## 验收与资源

- 本地工程测试104项通过；服务器真实API构造反例 {sum(r['passed'] for r in controls)}/{len(controls)} 通过。反例只统计原候选是否被认可，返回有据修正答案不等于认可错误候选。这不是RAGBench成绩。
- 已通过直接部署工厂入口再次运行一条已公开开发题，保留`factory_smoke.json`；该额外问答不计入100题成绩，也不用于继续调参。
- 重新计算 {len(all_records)} 条记录的EM/F1；其中独立验证/测试700条。已核验父文档偏移、引用原文、首轮候选配对、预算及冻结哈希，并重新计算 {boolean_certificates} 个最终布尔证据证书。
- 新测试排除旧200题索引；题面与旧200题规范化重复 {len(text_overlap)} 题。用于查看数据格式的第0题不在本次新测试中。
- 新测试题面与本轮开发/验证题规范化重复 {len(development_overlap)} 题；此检查只覆盖完全相同的规范化题面，不排除相似问题或共享新闻。
- 实际API响应日志 {len(usage)} 条；返回模型标识 {json.dumps(api['returned_models'], ensure_ascii=False)}。
- 实际token汇总：{json.dumps(dict(tokens), ensure_ascii=False)}。这是共享缓存实验的总消耗，不是各方案独立部署成本；没有估报人民币费用。
- 运行仍采用DeepSeek API；服务器运行BGE-M3、BGE reranker及图算法，不运行本地Qwen或NLI。
- 验证/测试阶段每秒采样的设备显存峰值 **{peak_mib} MiB（{peak_mib/1024:.2f} GiB）**。采样可能漏过亚秒尖峰，不包含更早开发阶段和首次图谱入库。没有在Tesla T10实测。
- 缓存用于配对复用，因此记录中的分支耗时不能当作独立在线速度对比。更宽上下文、重排序和额外验证会增加计算/API开销。

## 开源参考与边界

- [LightRAG](https://github.com/HKUDS/LightRAG)：复用现有图/向量召回；上游也提供查询阶段重排序选项。
- [LlamaIndex RRF](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/fusion_retriever.py)：采用标准倒数排名融合，不是移植整个框架。
- [BGE reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3)：使用现有相关性重排模型，不把相关性分数当成事实蕴含概率。
- [CRAG](https://arxiv.org/abs/2401.15884)：借鉴证据纠错路由，未复现其训练或外部网络搜索。
- [RAGAS](https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/metrics/_faithfulness.py)及[CoVe](https://arxiv.org/abs/2309.11495)：参考原子声明核验及答案独立检查思路，未宣称复现论文成绩。

这是应用层推理流程优化，没有训练新模型，也不声称已证明论文级原创性或优于完整调优后的官方LightRAG。

## 剩余限制与交付

规划、生成和事实检查仍共享DeepSeek，错误可能相关。三值逻辑只能保证在给定原子判断下组合正确，不能保证问题解析和事实判断正确。
完整性硬检查针对显式标记为absence的证明；如果模型漏标非提及理由，或联合审查把现实事件误当作报告内容，仍可能误放行。这不是对所有语义缺陷的程序级证明。
父文档有噪声、局部信息缺失或题干定位语不严谨时仍可能错答/拒答。已在 `examples_and_remaining_failures.json` 保存真实纠正与失败样例；未据此更改冻结算法。
本轮只评估MultiHop-RAG英语新闻问答；未新增RAGBench完整响应faithfulness分数，也未验证其他领域或中文输入泛化。

`protocol.json` / `freeze.json` 保存划分与参数；`results/`保存每题答案、证据及日志，`per_question_scores.csv`可直接查看700条独立验证/测试得分；`cache/`保存真实模型原始输出和精确输入；`project/`为可运行源码。
`trial1_source.tar`至`trial3_source.tar`保存失败版本，`selected_source.tar.gz`保存最终版本；模型权重与大图索引留在服务器，不含在下载包里。
服务器目录：`/root/autodl-tmp/evidencechain_v2_20261015`。私有`.env`与密钥不打包。
'''
(ROOT/'results/v2_report_zh.md').write_text(report, encoding='utf-8')
print(json.dumps({'target80_met': audit['target80_met_on_test100'], 'test': summaries['test'],
                  'comparisons': comparisons, 'gpu_peak_mib': peak_mib, 'audited_records': len(all_records)}, ensure_ascii=False, indent=2))
