import asyncio
from evidencechain.schema import Evidence
from evidencechain.verifier import EvidenceVerifier
from evidencechain.pipeline import EvidenceChain

CLAIM = 'Project Aster-01-7255 relies on Beryl-02-1000 for deployment.'


class CrossSourceScorer:
    def score(self, premises, hypotheses):
        result = []
        for context in premises:
            has_aster = 'Aster-01-7255' in context
            has_beryl = 'Beryl-02-1000' in context
            result.append((0.93, 0.02) if has_aster and has_beryl else (0.12, 0.02))
        return result


def test_multisource_compound_claim_is_no_longer_mechanically_ignored():
    ev = [
        Evidence('A', 'Project Aster-01-7255 relies on the deployment coordinator.', 'doc-A'),
        Evidence('B', 'Beryl-02-1000 is the deployment coordinator.', 'doc-B'),
    ]
    result = EvidenceVerifier(CrossSourceScorer()).check([CLAIM], ev)
    assert result['accepted']
    assert set(result['verdicts'][0]['support_ids']) == {'A', 'B'}


def test_missing_second_entity_still_does_not_support_compound_claim():
    ev = [Evidence('A', 'Project Aster-01-7255 relies on the deployment coordinator.', 'doc-A')]
    result = EvidenceVerifier(CrossSourceScorer()).check([CLAIM], ev)
    assert not result['accepted']
    assert result['verdicts'][0]['label'] == 'insufficient'


def test_pipeline_exposes_both_citation_ids():
    class FixedRetriever:
        async def search(self, query, mode, top_k):
            return [Evidence('A', 'Project Aster-01-7255 relies on the coordinator.', 'doc-A'),
                    Evidence('B', 'Beryl-02-1000 is the coordinator.', 'doc-B')]

    class FixedGenerator:
        async def generate(self, question, evidence):
            return {'answer': 'Beryl-02-1000', 'claims': [CLAIM]}

    result = asyncio.run(EvidenceChain(FixedRetriever(), FixedGenerator(),
                                      EvidenceVerifier(CrossSourceScorer())).ask('Who is involved?', 'verify'))
    assert result['answer'] == 'Beryl-02-1000'
    assert set(result['citation_ids']) == {'A', 'B'}
