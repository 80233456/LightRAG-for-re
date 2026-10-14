"""Regression fixtures using scores from the 2026-10-14 false conflict."""
from evidencechain.schema import Evidence
from evidencechain.verifier import EvidenceVerifier, entity_anchors


class ModelLikeScorer:
    def score(self, premises, hypotheses):
        rows = []
        for premise in premises:
            if "Yarrowport" in premise:
                rows.append((0.96727, 0.02))
            elif "Quartzbay" in premise or "Riverholt" in premise:
                rows.append((0.02, 0.99638))
            else:
                rows.append((0.12, 0.02))
        return rows


CLAIM = "Project Aster-01-7255 was launched in 2022 in Yarrowport."


def test_false_cross_project_contradiction_is_ignored():
    ev = [
        Evidence("1", "Project Aster-01-7255 was launched in 2022 in Yarrowport.", "synthetic/p00/project"),
        Evidence("2", "Project Aster-02-7061 was launched in 2015 in Riverholt.", "synthetic/p01/project"),
        Evidence("3", "Project Aster-07-1030 was launched in 2008 in Quartzbay.", "synthetic/p06/project"),
    ]
    result = EvidenceVerifier(ModelLikeScorer()).check([CLAIM], ev)
    assert result["accepted"]
    assert result["verdicts"][0]["label"] == "supported"
    assert result["verdicts"][0]["support_id"] == "1"


def test_multiple_projects_within_one_chunk():
    ev = [Evidence("1", (
        "Project Aster-01-7255 was launched in 2022 in Yarrowport. "
        "Project Aster-07-1030 was launched in 2008 in Quartzbay."
    ), "combined")]
    assert EvidenceVerifier(ModelLikeScorer()).check([CLAIM], ev)["accepted"]


def test_genuine_same_entity_contradiction_still_rejects():
    ev = [
        Evidence("1", "Project Aster-01-7255 was launched in 2022 in Yarrowport.", "right"),
        Evidence("2", "Project Aster-01-7255 was launched in 2018 in Quartzbay.", "wrong"),
    ]
    result = EvidenceVerifier(ModelLikeScorer()).check([CLAIM], ev)
    assert not result["accepted"]
    assert result["verdicts"][0]["label"] == "conflict"


def test_unrelated_evidence_cannot_prove_claim():
    ev = [Evidence("1", "Project Aster-07-1030 was launched in 2022 in Yarrowport.", "wrong")]
    result = EvidenceVerifier(ModelLikeScorer()).check([CLAIM], ev)
    assert not result["accepted"]
    assert result["verdicts"][0]["label"] == "insufficient"


def test_year_not_entity_id():
    ids, name = entity_anchors(CLAIM)
    assert ids == ("aster-01-7255",)
    assert name is None


def test_anonymous_contradiction_still_rejected():
    class Contradicts:
        def score(self, premises, hypotheses):
            return [(0.05, 0.97)] * len(premises)

    output = EvidenceVerifier(Contradicts()).check(
        ["北境王国的首都不是北京。"], [Evidence("1", "北境王国的首都是北京。", "demo")]
    )
    assert not output["accepted"]


def test_verifier_inspects_expanded_evidence_beyond_first_eight():
    ev = [Evidence(str(i), "An unrelated passage about other topics.", f"source-{i}") for i in range(1, 9)]
    ev.append(Evidence("9", "Project Aster-01-7255 was launched in 2022 in Yarrowport.", "right"))
    result = EvidenceVerifier(ModelLikeScorer()).check([CLAIM], ev)
    assert result["accepted"]
    assert result["verdicts"][0]["support_id"] == "9"
