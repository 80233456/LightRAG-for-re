from evidencechain.schema import Evidence
from evidencechain.verifier import EvidenceVerifier, LexicalScorer


def test_support_accepts_exact_claim():
    v = EvidenceVerifier(LexicalScorer())
    result = v.check(["星桥项目于2023年在南京启动。"],
                     [Evidence("E1", "星桥项目于2023年在南京启动。", "doc1")])
    assert result["accepted"]
    assert result["verdicts"][0]["label"] == "supported"


def test_no_evidence_abstains():
    v = EvidenceVerifier(LexicalScorer())
    assert not v.check(["地球是方形的"], [])["accepted"]


def test_conflict_with_negation():
    v = EvidenceVerifier(LexicalScorer())
    claim = "星桥项目不是2024年启动。"
    evs = [Evidence("E1", claim, "doc1"), Evidence("E2", "星桥项目是2024年启动。", "doc2")]
    result = v.check([claim], evs)
    assert not result["accepted"]
    assert result["verdicts"][0]["label"] == "conflict"
