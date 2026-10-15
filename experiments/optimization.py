"""One frozen optimization experiment. Reference answers never enter inference."""
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time

ROOT = Path('/root/autodl-tmp/evidencechain_optimization_20261015')
PRIOR = Path('/root/autodl-tmp/evidencechain_rerun_20261015')
OLD = Path('/root/autodl-tmp/evidencechain_run_20261014/project')
sys.path.insert(0, str(ROOT/'project/src'))
from paired_common import PairedRetriever, PairedGenerator, append, key, read, rows

VARIANTS = ('baseline', 'v1_full', 'joint_verify', 'recovery_only', 'optimized_full')


def hashes():
    base = ROOT/'project'
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'experiments') for p in sorted((base/folder).rglob('*.py'))}


def prepare():
    (ROOT/'results').mkdir(parents=True, exist_ok=True)
    target = ROOT/'index'
    if not target.exists():
        shutil.copytree(PRIOR/'indices/multihop', target)
    split_path = OLD/'configs/multihop_split_indices.json'
    split, previous = read(split_path), read(PRIOR/'protocol.json')
    remaining = sorted(set(split['test_indices']) - set(previous['multihop_test_indices']))
    protocol = {
        'base_commit': 'b9009d237c3b432ea1139fccf1102fa6b9b4247e',
        'method': 'joint semantic answer adjudication with literal quote checks and bounded question-only recovery',
        'validation_indices': sorted(random.Random(2026101501).sample(split['validation_indices'], 32)),
        'test_indices': sorted(random.Random(2026101502).sample(remaining, 100)),
        'previous_test_indices_excluded': previous['multihop_test_indices'],
        'selection': 'Original frozen split; new QA validation32 and new test100, not official full benchmark scores',
        'variants': list(VARIANTS), 'model': 'deepseek-flash', 'temperature': 0,
        'embedding': 'unchanged local BGE-M3 CUDA weights; unchanged persisted 609-document corpus graph',
        'nli_control': 'unchanged mDeBERTa CUDA; support0.78 contradiction0.70',
        'first_retrieval': 'mix top8; same original generator/prompt/ordered context across paired first pass',
        'budget': {'max_retrieval_calls': 3, 'max_final_chunks': 12, 'max_generation_attempts': 2,
                   'max_recovery_queries': 2, 'chars_per_chunk': 1800},
        'recovery': 'Only empty answer or insufficient verdict; never refuted/conflict/invalid or malformed generation. Preserve initial evidence.',
        'scoring': 'existing normalized token EM/F1; null gold empty; malformed generation zero even on null; no sample replacement',
        'cache': 'new empty caches, exact input only; first-pass candidates paired; gold absent from all inference inputs',
        'timing': 'Paired caches make per-variant latency unsuitable for independent speed claims',
        'freeze': 'Code frozen after validation and before first test; no tuning on either previous or new test100',
        'limitations': 'Same-model generation and judgment; quote presence is not semantic proof. This is QA optimization, not a RAGBench adherence score.',
        'split_sha256': hashlib.sha256(split_path.read_bytes()).hexdigest()}
    path = ROOT/'protocol.json'
    if path.exists() and read(path) != protocol:
        raise RuntimeError('Protocol already frozen and differs')
    path.write_text(json.dumps(protocol, indent=2))
    (ROOT/'initial_source_sha256.json').write_text(json.dumps(hashes(), indent=2))
    print('PREPARED validation32 test100, corpus copied, protocol frozen', flush=True)


class LoggedClient:
    def __init__(self, delegate):
        self.delegate = delegate
        self.path = ROOT/'cache/judge_planner.jsonl'
        self.cache = {r['key']: r['raw_response'] for r in rows(self.path)}

    async def complete(self, prompt, **kwargs):
        token = key([prompt, kwargs])
        if token not in self.cache:
            raw = await self.delegate.complete(prompt, **kwargs)
            self.cache[token] = raw
            append(self.path, {'key': token, 'prompt': prompt, 'options': kwargs, 'raw_response': raw})
        return self.cache[token]


def summary(records):
    result = {}
    for variant in VARIANTS:
        arr = [r for r in records if r['variant'] == variant]
        if not arr:
            continue
        answered = [r for r in arr if not r['output']['abstained']]
        answerable = [r for r in arr if r['answerable']]
        correct_candidates = [r for r in arr if r['answerable'] and r['candidate_em'] == 1]
        avg = lambda values: sum(values)/len(values) if values else None
        result[variant] = {
            'n': len(arr), 'correct': sum(r['em'] for r in arr), 'em': avg([r['em'] for r in arr]),
            'f1': avg([r['f1'] for r in arr]), 'n_answerable': len(answerable),
            'answerable_correct': sum(r['em'] for r in answerable),
            'answerable_em': avg([r['em'] for r in answerable]),
            'answered': len(answered), 'coverage': len(answered)/len(arr),
            'selective_accuracy': avg([r['em'] for r in answered]),
            'wrong_answers': sum(r['em'] == 0 for r in answered),
            'null_unsafe_accepts': sum(not r['answerable'] for r in answered),
            'correct_candidates': len(correct_candidates),
            'correct_candidates_rejected': sum(r['output']['abstained'] for r in correct_candidates),
            'format_errors': sum(bool(r['generation_format_error']) for r in arr),
            'mean_retrieval_calls': avg([r['output']['retrieval']['calls'] for r in arr]),
            'fact_recall_proxy': avg([r['fact_recall'] for r in arr if r['fact_recall'] is not None]),
            'by_kind': {kind: {'n': len(sub), 'em': avg([r['em'] for r in sub])}
                        for kind in sorted({r['question_type'] for r in arr})
                        if (sub := [r for r in arr if r['question_type'] == kind])}}
    return result


def settings(stage):
    from dotenv import load_dotenv
    load_dotenv(OLD/'.env', override=False)
    os.environ.update(API_USAGE_LOG=str(ROOT/'results/api_usage.jsonl'), EXPERIMENT_STAGE=stage,
                      LLM_MAX_ASYNC='2', GENERATION_TIMEOUT='30', LIGHTRAG_WORKDIR=str(ROOT/'index'))
    from evidencechain.config import settings_from_env
    config = settings_from_env()
    assert config.llm_model == 'deepseek-flash' and config.llm_provider == 'deepseek'
    assert config.support_threshold == .78 and config.contradiction_threshold == .70
    return config


async def evaluate(stage):
    from evidencechain.api_client import DeepSeekClient
    from evidencechain.factory import make_chain
    from evidencechain.grounding import JointEvidenceVerifier, QueryPlanner
    from evidencechain.recovery import GroundedEvidenceChain
    from evidencechain.metrics import answer_em, answer_f1, fact_recall
    from lightrag.base import DocStatus
    config = settings(stage)
    protocol = read(ROOT/'protocol.json')
    if stage == 'test':
        frozen = read(ROOT/'freeze.json')
        assert hashes() == frozen['source_sha256'], 'Source changed after validation freeze'
        assert len(rows(ROOT/'results/validation/records.jsonl')) == 32*len(VARIANTS)
    control = await make_chain(config, 'lightrag', 'nli')
    statuses = await control.retriever.rag.doc_status.get_docs_by_statuses(list(DocStatus))
    actual = [v for k, v in statuses.items() if k.startswith('doc-')]
    ingestion = {'actual_documents': len(actual), 'processed': sum(v.status == DocStatus.PROCESSED for v in actual),
                 'failed': sum(v.status != DocStatus.PROCESSED for v in actual)}
    assert ingestion == {'actual_documents': 609, 'processed': 609, 'failed': 0}, ingestion
    (ROOT/'results/index_status.json').write_text(json.dumps(ingestion, indent=2))
    retriever = PairedRetriever(control.retriever, ROOT/f'cache/{stage}/retrieval.jsonl')
    generator = PairedGenerator(control.generator, ROOT/f'cache/{stage}/generation.jsonl')
    control.retriever, control.generator = retriever, generator
    client = LoggedClient(DeepSeekClient(config))
    grounded = GroundedEvidenceChain(retriever, generator, JointEvidenceVerifier(client), QueryPlanner(client))
    path = ROOT/f'results/{stage}/records.jsonl'
    done = {(r['index'], r['variant']) for r in rows(path)}
    dataset = read(OLD/'data/public_raw/MultiHopRAG/MultiHopRAG.json')
    try:
        for number, index in enumerate(protocol[f'{stage}_indices'], 1):
            question = dataset[index]
            gold = '' if question['question_type'] == 'null_query' else str(question.get('answer') or '')
            for variant in VARIANTS:
                if (index, variant) in done:
                    continue
                retriever.events = []
                if variant in ('baseline', 'v1_full'):
                    output = await control.ask(question['query'], 'baseline' if variant == 'baseline' else 'full')
                else:
                    output = await grounded.ask(question['query'], {'joint_verify': 'verify',
                        'recovery_only': 'adaptive', 'optimized_full': 'full'}[variant])
                error = output.get('generation_format_error') or generator.last_format_error
                output['variant'] = variant
                facts = [e['fact'] for e in question.get('evidence_list', []) if e.get('fact')]
                record = {'index': index, 'query': question['query'], 'gold': question.get('answer'),
                          'scoring_gold': gold, 'answerable': question['question_type'] != 'null_query',
                          'question_type': question['question_type'], 'variant': variant, 'output': output,
                          'em': 0.0 if error else answer_em(output['answer'], gold),
                          'f1': 0.0 if error else answer_f1(output['answer'], gold),
                          'candidate_em': 0.0 if error else answer_em(output['candidate_answer'], gold),
                          'generation_format_error': error,
                          'fact_recall': fact_recall([e['content'] for e in output['evidence']], facts),
                          'retrieval_events': retriever.events}
                append(path, record)
                print(stage, number, '/', len(protocol[f'{stage}_indices']), variant, 'em', record['em'],
                      'abstained', output['abstained'], flush=True)
        records = rows(path)
        assert len(records) == len(protocol[f'{stage}_indices'])*len(VARIANTS)
        (path.parent/'summary.json').write_text(json.dumps(summary(records), indent=2))
        print('COMPLETE', stage, json.dumps(summary(records)), flush=True)
    finally:
        await retriever.close()


def freeze():
    assert len(rows(ROOT/'results/validation/records.jsonl')) == 32*len(VARIANTS)
    assert not rows(ROOT/'results/test/records.jsonl'), 'Cannot freeze after test began'
    path = ROOT/'freeze.json'
    data = {'time': time.time(), 'source_sha256': hashes(),
            'protocol_sha256': hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest()}
    if path.exists():
        assert read(path)['source_sha256'] == data['source_sha256']
    else:
        path.write_text(json.dumps(data, indent=2))
    print('FROZEN', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'validation', 'freeze', 'test'])
    args = parser.parse_args()
    if args.stage == 'prepare':
        prepare()
    elif args.stage == 'freeze':
        freeze()
    else:
        asyncio.run(evaluate(args.stage))
