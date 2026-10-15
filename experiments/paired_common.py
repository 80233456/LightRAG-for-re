"""Frozen, resumable real-model comparison. Never sends gold to inference."""
import argparse
import asyncio
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
from statistics import mean
import sys
import time

ROOT = Path('/root/autodl-tmp/evidencechain_rerun_20261015')
OLD = Path('/root/autodl-tmp/evidencechain_run_20261014/project')
NEW = ROOT / 'project'


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line] if Path(path).exists() else []


def append(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as out:
        out.write(json.dumps(record, ensure_ascii=False) + '\n')
        out.flush()


def key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class PairedRetriever:
    def __init__(self, delegate, path):
        self.delegate, self.path = delegate, path
        self.cache = {r['key']: r['evidence'] for r in rows(path)}
        self.events = []

    async def search(self, query, mode, top_k):
        from evidencechain.schema import Evidence
        token = key([query, mode, top_k])
        hit = token in self.cache
        if not hit:
            result = await self.delegate.search(query, mode, top_k)
            self.cache[token] = [e.as_dict() for e in result]
            append(self.path, {'key': token, 'query': query, 'mode': mode,
                               'top_k': top_k, 'evidence': self.cache[token]})
        self.events.append({'mode': mode, 'top_k': top_k, 'paired_cache_hit': hit})
        return [Evidence(**e) for e in self.cache[token]]

    async def close(self):
        await self.delegate.close()


class PairedGenerator:
    def __init__(self, delegate, path):
        self.delegate, self.path = delegate, path
        self.cache = {r['key']: r['prediction'] for r in rows(path)}
        self.last_cache_hit = False
        self.last_format_error = None

    async def generate(self, question, evidence):
        token = key([question, [e.as_dict() for e in evidence]])
        self.last_cache_hit = token in self.cache
        if not self.last_cache_hit:
            raw_response = None
            original_complete = self.delegate.client.complete

            async def capture(*args, **kwargs):
                nonlocal raw_response
                raw_response = await original_complete(*args, **kwargs)
                return raw_response

            self.delegate.client.complete = capture
            try:
                self.cache[token] = await self.delegate.generate(question, evidence)
            except ValueError as error:
                expected = raw_response is not None and (isinstance(error, json.JSONDecodeError) or any(
                    message in str(error) for message in
                    ['Nonempty answer must contain 1-3 claims', 'Expected JSON', 'Expected claims']))
                if not expected:
                    raise
                self.cache[token] = {'answer': '', 'claims': [], '_format_error': str(error)}
                append(self.path.parent/'format_errors.jsonl', {'key': token, 'question': question,
                       'error': type(error).__name__, 'message': str(error), 'raw_response': raw_response,
                       'scoring': 'zero EM/F1 for every variant using this input, including null_query; no resampling'})
            finally:
                self.delegate.client.complete = original_complete
            append(self.path, {'key': token, 'prediction': self.cache[token]})
        prediction = self.cache[token]
        self.last_format_error = prediction.get('_format_error')
        return {'answer': prediction['answer'], 'claims': list(prediction['claims'])}


def selected_questions(suite):
    if suite == 'onsite':
        return [{**q, 'query': q['question'], 'index': q['id'],
                 'scoring_gold': q['answer'], 'question_type': q['kind']}
                for q in rows(OLD/'data/onsite_synthetic/questions.jsonl')]
    data = read(OLD/'data/public_raw/MultiHopRAG/MultiHopRAG.json')
    plan = read(ROOT/'protocol.json')
    indices = plan['multihop_test_indices' if suite == 'multihop_test' else 'multihop_regression_indices']
    return [{**data[i], 'index': i, 'scoring_gold': '' if data[i]['question_type'] == 'null_query'
             else str(data[i].get('answer') or ''), 'answerable': data[i]['question_type'] != 'null_query'}
            for i in indices]


def summarize(records):
    from evidencechain.pipeline import VARIANTS
    result = {}
    for variant in VARIANTS:
        arr = [r for r in records if r['variant'] == variant]
        if not arr:
            continue
        answerable = [r for r in arr if r['answerable']]
        null = [r for r in arr if not r['answerable']]
        answered = [r for r in arr if not r['output']['abstained']]
        candidates = [r for r in arr if r['candidate_em'] == 1 and r['answerable']]
        metric = lambda values: mean(values) if values else None
        result[variant] = {
            'n': len(arr), 'correct': sum(r['em'] for r in arr),
            'em': metric([r['em'] for r in arr]), 'f1': metric([r['f1'] for r in arr]),
            'n_answerable': len(answerable), 'answerable_correct': sum(r['em'] for r in answerable),
            'answerable_em': metric([r['em'] for r in answerable]),
            'answered': len(answered), 'coverage': len(answered)/len(arr),
            'selective_accuracy': metric([r['em'] for r in answered]),
            'wrong_answers': sum(r['em'] == 0 for r in answered),
            'unsafe_accept_rate': metric([not r['output']['abstained'] for r in null]),
            'correct_candidates': len(candidates),
            'correct_candidates_rejected': sum(r['output']['abstained'] for r in candidates),
            'generation_format_failures': sum(bool(r.get('generation_format_error')) for r in arr),
            'mean_retrieval_calls': metric([r['output']['retrieval']['calls'] for r in arr]),
            'fact_recall_proxy': metric([r['fact_recall'] for r in arr if r['fact_recall'] is not None]),
            'by_kind': {kind: {'n': len(sub), 'em': mean(r['em'] for r in sub)}
                        for kind in sorted({r['question_type'] for r in arr})
                        if (sub := [r for r in arr if r['question_type'] == kind])}}
    return result


async def qa(args, settings):
    from evidencechain.factory import make_chain
    from evidencechain.metrics import answer_em, answer_f1, fact_recall
    from evidencechain.pipeline import VARIANTS
    selected = selected_questions(args.suite)
    root = ROOT/'results'/args.suite/args.version
    root.mkdir(parents=True, exist_ok=True)
    settings = replace(settings, working_dir=str(ROOT/'indices'/('onsite' if args.suite == 'onsite' else 'multihop')))
    safe = asdict(settings)
    safe.pop('llm_api_key')
    manifest = {'version': args.version, 'suite': args.suite, 'settings': safe,
                'question_indices': [q['index'] for q in selected], 'count': len(selected),
                'source_sha256': key({str(p.relative_to(Path(sys.path[0]))): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in Path(sys.path[0]).rglob('*.py')}),
                'cache': 'exact query+mode+k retrieval and query+ordered evidence generation, shared old/new; no gold in cache keys',
                'latency': 'cache reuse means not a fair independent timing measurement'}
    manifest_path = root/'manifest.json'
    if manifest_path.exists() and read(manifest_path) != manifest:
        raise RuntimeError('Frozen manifest changed')
    manifest_path.write_text(json.dumps(manifest, indent=2))
    chain = await make_chain(settings, 'lightrag', 'nli')
    from lightrag.base import DocStatus
    statuses = await chain.retriever.rag.doc_status.get_docs_by_statuses(list(DocStatus))
    actual = [value for token, value in statuses.items() if token.startswith('doc-')]
    ingestion = {'actual_documents': len(actual),
                 'processed': sum(value.status == DocStatus.PROCESSED for value in actual),
                 'failed': sum(value.status != DocStatus.PROCESSED for value in actual),
                 'duplicate_audit_records': sum(token.startswith('dup-') for token in statuses)}
    (root/'index_status.json').write_text(json.dumps(ingestion, indent=2))
    expected_documents = 48 if args.suite == 'onsite' else 609
    assert ingestion['processed'] == expected_documents and ingestion['failed'] == 0
    chain.retriever = PairedRetriever(chain.retriever, ROOT/'cache'/args.suite/'retrieval.jsonl')
    chain.generator = PairedGenerator(chain.generator, ROOT/'cache'/args.suite/'generation.jsonl')
    path = root/'records.jsonl'
    done = {(r['index'], r['variant']) for r in rows(path)}
    try:
        for number, question in enumerate(selected, 1):
            for variant in VARIANTS:
                if (question['index'], variant) in done:
                    continue
                chain.retriever.events = []
                output = await chain.ask(question['query'], variant)
                format_error = chain.generator.last_format_error
                facts = [e['fact'] for e in question.get('evidence_list', []) if e.get('fact')]
                record = {'index': question['index'], 'query': question['query'],
                          'gold': question['answer'], 'scoring_gold': question['scoring_gold'],
                          'answerable': question['answerable'], 'question_type': question['question_type'],
                          'split': question.get('split', 'test' if args.suite == 'multihop_test' else 'dev'),
                          'variant': variant, 'output': output,
                          'em': 0.0 if format_error else answer_em(output['answer'], question['scoring_gold']),
                          'candidate_em': 0.0 if format_error else answer_em(output['candidate_answer'], question['scoring_gold']),
                          'f1': 0.0 if format_error else answer_f1(output['answer'], question['scoring_gold']),
                          'generation_format_error': format_error,
                          'fact_recall': fact_recall([e['content'] for e in output['evidence']], facts),
                          'generation_cache_hit': chain.generator.last_cache_hit,
                          'retrieval_events': chain.retriever.events}
                append(path, record)
                print('QA', args.suite, args.version, number, '/', len(selected), variant,
                      'em', record['em'], 'abstained', output['abstained'], flush=True)
        records = rows(path)
        assert len(records) == len(selected)*4
        summary = summarize(records)
        if args.suite == 'onsite':
            summary = {split: summarize([r for r in records if r['split'] == split]) for split in ('dev', 'test')}
        (root/'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary), flush=True)
    finally:
        await chain.retriever.close()


def ragbench(args, settings):
    import pyarrow.parquet as pq
    from evidencechain.factory import make_verifier
    from evidencechain.metrics import binary_metrics
    sys.path.insert(1, str(NEW/'scripts'))
    from eval_ragbench import prepare_record, support_label
    verifier = make_verifier(settings, 'nli')
    for split, start, stop, name in [('test', 0, 246, 'test246_regression'),
                                      ('validation', 100, 267, 'validation167_unseen')]:
        data = pq.read_table(OLD/f'data/public_raw/ragbench/covidqa/{split}-00000-of-00001.parquet').to_pylist()
        root = ROOT/'results'/'ragbench'/name/args.version
        root.mkdir(parents=True, exist_ok=True)
        path = root/'records.jsonl'
        done = {r['row_index'] for r in rows(path)}
        for index in range(start, min(stop, len(data))):
            if index in done:
                continue
            row = data[index]
            label = support_label(row)
            assert label is not None
            claims, evidence = prepare_record(row, 5)
            started = time.time()
            verdict = verifier.check(claims, evidence)
            append(path, {'row_index': index, 'id': row.get('id'), 'gold': label,
                          'predicted': bool(verdict['accepted']), 'verification': verdict,
                          'claims': claims, 'elapsed_s': time.time()-started})
            print('RAGBENCH', name, args.version, index+1, '/', min(stop, len(data)), flush=True)
        records = rows(path)
        assert len(records) == min(stop, len(data))-start
        result = binary_metrics([r['gold'] for r in records], [r['predicted'] for r in records])
        (root/'summary.json').write_text(json.dumps(result, indent=2))
        print('RAGBENCH SUMMARY', name, args.version, json.dumps(result), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--version', choices=['old', 'new'], required=True)
    p.add_argument('--suite', choices=['onsite', 'multihop_regression', 'multihop_test', 'ragbench'], required=True)
    args = p.parse_args()
    source = OLD if args.version == 'old' else NEW
    sys.path.insert(0, str(source/'src'))
    from dotenv import load_dotenv
    load_dotenv(OLD/'.env', override=False)
    os.environ['API_USAGE_LOG'] = str(ROOT/'results/api_usage.jsonl')
    os.environ['EXPERIMENT_STAGE'] = args.suite + '_' + args.version
    os.environ['LLM_MAX_ASYNC'] = '2'
    os.environ['GENERATION_TIMEOUT'] = '30'
    from evidencechain.config import settings_from_env
    settings = settings_from_env()
    assert settings.llm_model == 'deepseek-flash'
    assert settings.support_threshold == .78 and settings.contradiction_threshold == .70
    import evidencechain
    print('ACTUAL SOURCE', evidencechain.__file__, flush=True)
    if args.suite == 'ragbench':
        ragbench(args, settings)
    else:
        asyncio.run(qa(args, settings))


if __name__ == '__main__':
    main()
