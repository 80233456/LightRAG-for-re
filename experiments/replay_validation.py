"""Re-execute validation after duplicate-only recovery guard, with recorded real inputs.

No delegate is available: any unexpected cache miss fails rather than generating
new samples. Existing control branches are unchanged. Original records preserved.
"""
import asyncio
import json
from optimization import ROOT, VARIANTS, LoggedClient, summary, rows
from paired_common import PairedRetriever, PairedGenerator
from evidencechain.grounding import JointEvidenceVerifier, QueryPlanner
from evidencechain.recovery import GroundedEvidenceChain
from evidencechain.metrics import answer_em, answer_f1, fact_recall


async def main():
    path = ROOT/'results/validation/records.jsonl'
    previous = rows(path)
    assert len(previous) == 32*len(VARIANTS)
    retriever = PairedRetriever(None, ROOT/'cache/validation/retrieval.jsonl')
    generator = PairedGenerator(None, ROOT/'cache/validation/generation.jsonl')
    client = LoggedClient(None)
    chain = GroundedEvidenceChain(retriever, generator, JointEvidenceVerifier(client), QueryPlanner(client))
    records, changes = [], []
    for record in previous:
        if record['variant'] in ('baseline', 'v1_full'):
            records.append(record)
            continue
        out = await chain.ask(record['query'], {'joint_verify': 'verify', 'recovery_only': 'adaptive', 'optimized_full': 'full'}[record['variant']])
        out['variant'] = record['variant']
        for field in ('answer', 'candidate_answer', 'claims', 'evidence', 'verification', 'retrieval', 'attempts'):
            if out[field] != record['output'][field]:
                changes.append({'index': record['index'], 'variant': record['variant'], 'field': field})
        # An actual validation outcome change needs explicit inspection, not overwrite.
        assert out['answer'] == record['output']['answer']
        assert out['evidence'] == record['output']['evidence']
        record['output'] = out
        record['validation_replay'] = 'duplicate-only guard; exact recorded real-model inputs; no API resampling'
        records.append(record)
    backup = path.with_name('records_before_duplicate_guard.jsonl')
    if not backup.exists():
        backup.write_bytes(path.read_bytes())
    path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records))
    (path.parent/'summary.json').write_text(json.dumps(summary(records), indent=2))
    audit = {'replayed_optimized_branches': 96, 'unexpected_cache_misses': 0,
             'answer_changes': 0, 'context_changes': 0, 'other_changes': changes}
    (path.parent/'duplicate_guard_replay.json').write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
