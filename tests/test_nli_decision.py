from evidencechain.schema import Evidence
from evidencechain.verifier import EvidenceVerifier


class FixedScorer:
    def score(self, premises, hypotheses):
        assert len(premises) == len(hypotheses)
        return [(0.90, 0.01) if "支持" in item else (0.02, 0.92) for item in premises]


def test_conflict_with_model_scores():
    checker = EvidenceVerifier(FixedScorer())
    ev = [Evidence("A", "支持的证据片段", "a"), Evidence("B", "反驳的证据片段", "b")]
    verdict = checker.check(["完整事实声明"], ev)
    assert not verdict["accepted"]
    assert verdict["verdicts"][0]["label"] == "conflict"
    assert verdict["verdicts"][0]["support_id"] == "A"
    assert verdict["verdicts"][0]["contradiction_id"] == "B"
