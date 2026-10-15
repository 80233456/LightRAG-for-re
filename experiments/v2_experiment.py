"""Frozen-split real-model evaluation; the target80 is not an acceptance override."""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time

ROOT = Path('/root/autodl-tmp/evidencechain_v2_20261015')
OLD = Path('/root/autodl-tmp/evidencechain_run_20261014/project')
V1 = Path('/root/autodl-tmp/evidencechain_optimization_20261015')
PREVIOUS = Path('/root/autodl-tmp/evidencechain_rerun_20261015')
sys.path.insert(0, str(ROOT/'project/src'))
from paired_common import PairedRetriever, PairedGenerator, append, key, rows, read

VARIANTS = ['baseline', 'previous_recovery', 'v2_context', 'v2_verify', 'v2_full']


def source_hashes():
    base = ROOT/'project'
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ['src', 'experiments'] for p in sorted((base/folder).rglob('*.py'))}


def prepare():
    (ROOT/'results').mkdir(exist_ok=True)
    if not (ROOT/'index').exists():
        shutil.copytree(V1/'index', ROOT/'index')
    split = read(OLD/'configs/multihop_split_indices.json')
    v1, prev = read(V1/'protocol.json'), read(PREVIOUS/'protocol.json')
    used_test = set(v1['test_indices']) | set(prev['multihop_test_indices'])
    dev = sorted(set(split['dev_indices'])-set(prev['multihop_regression_indices']))
    val = sorted(set(split['validation_indices'])-set(v1['validation_indices']))
    test = sorted(set(split['test_indices'])-used_test)
    protocol = {
        'base': 'b9009d2 plus previous optimization source, separate v2 strategy',
        'target': '80% normalized token EM on new blind100, aspirational not guaranteed',
        'dev_indices': sorted(random.Random(2026101511).sample(dev, 24)),
        'validation_indices': sorted(random.Random(2026101512).sample(val, 40)),
        'test_indices': sorted(random.Random(2026101513).sample(test, 100)),
        'previous_test_indices_excluded': sorted(used_test), 'variants': VARIANTS,
        'corpus': 'same609 news articles, no QA labels available to retrievers; parent index built from corpus.json only',
        'model': 'deepseek-flash', 'temperature': 0, 'embedding': 'same BGE-M3 CUDA',
        'reranker': read(ROOT/'models/bge-reranker-v2-m3/download_revision.json'),
        'budget': {'facets': 4, 'correction_queries': 2, 'initial_graph_calls': 2, 'max_graph_calls': 4,
                   'rerank_candidates_per_query': 32, 'initial_chars': 64000, 'max_chars': 96000,
                   'max_passages': 32, 'max_generations': 2, 'max_verification_rounds': 2, 'max_verifications': 4,
                   'boolean_atoms': 8, 'boolean_ast_nodes': 32, 'complete_parent_upgrade_limit': 12000},
        'comparison': 'new retrieval and generator change compute budget; v2_context versus v2_verify isolates first-pass verification and Boolean correction',
        'scoring': 'unchanged normalized EM/F1; null gold empty; malformed generation zero even on null; no replacement questions',
        'safety': 'candidate-blind atomic truth plus three-valued Boolean logic; independent joint-proof fallback on parser failure or unresolved atomic evidence; never auto-approve uncertainty; citation-invalid audits and conflicts fail closed; absence requires complete parent coverage',
        'retrieval': 'local BM25+LightRAG+RRF(k60)+BGE crossencoder+literal parent spans; no web search at inference',
        'tuning': 'development24 only; validation40 once before freeze; test100 once after freeze; preserve every development trial',
        'latency': 'paired exact caches; per-variant wall time is not independent latency',
        'references': ['https://github.com/HKUDS/LightRAG', 'https://huggingface.co/BAAI/bge-reranker-v2-m3',
                       'https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/fusion_retriever.py',
                       'https://arxiv.org/abs/2401.15884', 'https://arxiv.org/abs/2309.11495',
                       'https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/metrics/_faithfulness.py']}
    path = ROOT/'protocol.json'
    if path.exists():
        previous = read(path)
        if previous != protocol:
            assert not rows(ROOT/'results/validation/records.jsonl') and not rows(ROOT/'results/test/records.jsonl')
            for name in ['dev_indices', 'validation_indices', 'test_indices', 'previous_test_indices_excluded']:
                assert previous[name] == protocol[name], 'Never resample after inference'
            backup = ROOT/'protocol_initial_before_development.json'
            if not backup.exists():
                backup.write_text(json.dumps(previous, indent=2))
            path.write_text(json.dumps(protocol, indent=2))
            print('Protocol method amendment before validation; all indices unchanged', flush=True)
    else:
        path.write_text(json.dumps(protocol, indent=2))
    print('PREPARED dev24 validation40 blind100;200 previous test indices excluded', flush=True)


class CachedClient:
    def __init__(self, delegate, stage):
        self.delegate = delegate
        self.path = ROOT/f'cache/{stage}/completions.jsonl'
        self.cache = {r['key']: r['raw_response'] for r in rows(self.path)}

    async def complete(self, prompt, **kwargs):
        token = key([prompt, kwargs])
        if token not in self.cache:
            response = await self.delegate.complete(prompt, **kwargs)
            self.cache[token] = response
            append(self.path, {'key': token, 'prompt': prompt, 'options': kwargs, 'raw_response': response})
        return self.cache[token]


class CachedReranker:
    def __init__(self, delegate, stage):
        self.delegate = delegate
        self.path = ROOT/f'cache/{stage}/reranking.jsonl'
        self.cache = {r['key']: r['scores'] for r in rows(self.path)}

    async def score(self, query, texts):
        token = key([query, texts])
        if token not in self.cache:
            scores = await self.delegate.score(query, texts)
            self.cache[token] = scores
            append(self.path, {'key': token, 'query': query, 'text_sha256': [key(t) for t in texts], 'scores': scores})
        return self.cache[token]


def summarize(records):
    result = {}
    for variant in VARIANTS:
        selected = [r for r in records if r['variant'] == variant]
        if not selected:
            continue
        answered = [r for r in selected if not r['output']['abstained']]
        answerable = [r for r in selected if r['answerable']]
        avg = lambda values: sum(values)/len(values) if values else None
        result[variant] = {'n': len(selected), 'em': avg([r['em'] for r in selected]),
                          'f1': avg([r['f1'] for r in selected]), 'coverage': len(answered)/len(selected),
                          'selective_accuracy': avg([r['em'] for r in answered]), 'answered': len(answered),
                          'wrong_nonempty': sum(r['em'] == 0 for r in answered), 'n_answerable': len(answerable),
                          'answerable_em': avg([r['em'] for r in answerable]),
                          'null_unsafe_accepts': sum(not r['answerable'] for r in answered),
                          'format_errors': sum(bool(r['generation_format_error']) for r in selected),
                          'mean_graph_calls': avg([r['output']['retrieval']['calls'] for r in selected]),
                          'fact_recall_proxy': avg([r['fact_recall'] for r in selected if r['fact_recall'] is not None]),
                          'by_kind': {kind: {'n': len(sub), 'em': avg([r['em'] for r in sub])}
                                      for kind in sorted({r['question_type'] for r in selected})
                                      if (sub := [r for r in selected if r['question_type'] == kind])}}
    return result


def settings(stage):
    from dotenv import load_dotenv
    load_dotenv(OLD/'.env', override=False)
    os.environ.update(API_USAGE_LOG=str(ROOT/'results/api_usage.jsonl'), EXPERIMENT_STAGE=stage,
                      GENERATION_TIMEOUT='90', LLM_MAX_ASYNC='2', LIGHTRAG_WORKDIR=str(ROOT/'index'))
    from evidencechain.config import settings_from_env
    result = settings_from_env()
    assert result.llm_model == 'deepseek-flash'
    return result


async def evaluate(stage, trial):
    from evidencechain.api_client import DeepSeekClient
    from evidencechain.retrievers import LightRAGRetriever
    from evidencechain.generation import DeepSeekGenerator
    from evidencechain.pipeline import EvidenceChain
    from evidencechain.grounding import JointEvidenceVerifier, QueryPlanner
    from evidencechain.recovery import GroundedEvidenceChain
    from evidencechain.corrective import CorrectiveEvidenceChain
    from evidencechain.parent_retrieval import ParentCorpusIndex, HybridParentRetriever, CrossEncoderReranker, corpus_documents
    from evidencechain.metrics import answer_em, answer_f1, fact_recall
    protocol = read(ROOT/'protocol.json')
    if stage == 'test':
        frozen = read(ROOT/'freeze.json')
        assert source_hashes() == frozen['source_sha256']
        assert hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest() == frozen['protocol_sha256']
    name = stage+'/'+trial if stage == 'dev' else stage
    root = ROOT/f'results/{name}'
    root.mkdir(parents=True, exist_ok=True)
    manifest = {'source_sha256': source_hashes(), 'indices': protocol[stage+'_indices'], 'variants': VARIANTS}
    manifest_path = root/'manifest.json'
    if manifest_path.exists():
        assert read(manifest_path) == manifest, 'Trial already contains a different algorithm version'
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2))
    config = settings(name)
    graph = await LightRAGRetriever(config).start()
    from lightrag.base import DocStatus
    statuses = await graph.rag.doc_status.get_docs_by_statuses(list(DocStatus))
    docs = [v for k, v in statuses.items() if k.startswith('doc-')]
    assert len(docs) == 609 and all(v.status == DocStatus.PROCESSED for v in docs)
    retriever = PairedRetriever(graph, ROOT/f'cache/{name}/graph.jsonl')
    generator = PairedGenerator(DeepSeekGenerator(config), ROOT/f'cache/{name}/baseline_generation.jsonl')
    client = CachedClient(DeepSeekClient(config), name)
    baseline = EvidenceChain(retriever, generator, None)
    previous = GroundedEvidenceChain(retriever, generator, JointEvidenceVerifier(client), QueryPlanner(client))
    corpus = read(OLD/'data/public_raw/MultiHopRAG/corpus.json')
    index = ParentCorpusIndex(corpus_documents(corpus))
    reranker = CachedReranker(CrossEncoderReranker(str(ROOT/'models/bge-reranker-v2-m3')), name)
    chain = CorrectiveEvidenceChain(HybridParentRetriever(index, retriever, reranker), client)
    questions = read(OLD/'data/public_raw/MultiHopRAG/MultiHopRAG.json')
    path = root/'records.jsonl'
    done = {(r['index'], r['variant']) for r in rows(path)}
    try:
        for number, qid in enumerate(protocol[stage+'_indices'], 1):
            question = questions[qid]
            gold = '' if question['question_type'] == 'null_query' else str(question.get('answer') or '')
            for variant in VARIANTS:
                if (qid, variant) in done:
                    continue
                if variant == 'baseline':
                    output = await baseline.ask(question['query'], 'baseline')
                    error = generator.last_format_error
                elif variant == 'previous_recovery':
                    output = await previous.ask(question['query'], 'adaptive')
                    error = output.get('generation_format_error') or generator.last_format_error
                else:
                    output = await chain.ask(question['query'], {'v2_context': 'context_only', 'v2_verify': 'verify', 'v2_full': 'full'}[variant])
                    error = output.get('generation_format_error')
                output['variant'] = variant
                facts = [e['fact'] for e in question.get('evidence_list', []) if e.get('fact')]
                record = {'index': qid, 'query': question['query'], 'gold': question.get('answer'), 'scoring_gold': gold,
                          'answerable': question['question_type'] != 'null_query', 'question_type': question['question_type'],
                          'variant': variant, 'output': output, 'generation_format_error': error,
                          'em': 0.0 if error else answer_em(output['answer'], gold),
                          'f1': 0.0 if error else answer_f1(output['answer'], gold),
                          'candidate_em': 0.0 if error else answer_em(output['candidate_answer'], gold),
                          'fact_recall': fact_recall([e['content'] for e in output['evidence']], facts)}
                append(path, record)
                print(name, number, '/', len(protocol[stage+'_indices']), variant, 'em', record['em'],
                      'abstained', output['abstained'], flush=True)
        records = rows(path)
        assert len(records) == len(protocol[stage+'_indices'])*len(VARIANTS)
        result = summarize(records)
        (root/'summary.json').write_text(json.dumps(result, indent=2))
        print('COMPLETE', name, json.dumps(result), flush=True)
    finally:
        await graph.close()


def freeze():
    assert len(rows(ROOT/'results/validation/records.jsonl')) == 40*len(VARIANTS)
    assert not rows(ROOT/'results/test/records.jsonl')
    data = {'time': time.time(), 'source_sha256': source_hashes(),
            'protocol_sha256': hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest()}
    path = ROOT/'freeze.json'
    if path.exists():
        assert read(path)['source_sha256'] == data['source_sha256']
    else:
        path.write_text(json.dumps(data, indent=2))
    print('FROZEN', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['prepare', 'dev', 'validation', 'freeze', 'test'])
    p.add_argument('--trial', default='trial1')
    args = p.parse_args()
    if args.stage == 'prepare':
        prepare()
    elif args.stage == 'freeze':
        freeze()
    else:
        asyncio.run(evaluate(args.stage, args.trial))
