import asyncio
from evidencechain.adaptive import AdaptiveController
from evidencechain.retrievers import DemoRetriever


def test_low_risk_single_search():
    doc = [{"id": "x", "text": "星桥项目的研发中心位于南京市。"}]
    ctrl = AdaptiveController()
    ev, trace = asyncio.run(ctrl.run(DemoRetriever(doc), "星桥项目研发中心位于哪里？", True))
    assert trace.calls in (1, 2)
    assert len(ev) == 1
    assert ev[0].source == "x"


def test_expansion_when_missing_evidence():
    ctrl = AdaptiveController(coverage_threshold=0.95)
    retriever = DemoRetriever([{"id": "x", "text": "无关句子"}])
    _, trace = asyncio.run(ctrl.run(retriever, "请比较两种跨域检索方式", True))
    assert trace.calls == 2
    assert trace.modes == ("mix", "mix")
    assert trace.requested_top_k == (8, 16)


def test_baseline_is_fixed():
    ctrl = AdaptiveController()
    _, trace = asyncio.run(ctrl.run(DemoRetriever([]), "abc question", False))
    assert trace.calls == 1
    assert trace.modes == ("mix",)


class RankAwareRetriever:
    def __init__(self):
        self.calls = []

    async def search(self, query, mode, top_k):
        from evidencechain.schema import Evidence
        self.calls.append((mode, top_k))
        return [Evidence(str(i), f"evidence {i}", str(i)) for i in range(top_k)]


def test_low_risk_retains_first_mix_pass():
    ctrl = AdaptiveController(coverage_threshold=0.0)
    retriever = RankAwareRetriever()
    ev, trace = asyncio.run(ctrl.run(retriever, "Where is the station?", True))
    assert retriever.calls == [("mix", 8)]
    assert len(ev) == 8
    assert trace.modes == ("mix",)


def test_multihop_structure_expands_without_discarding_first_results():
    ctrl = AdaptiveController()
    retriever = RankAwareRetriever()
    question = "Which online betting platform provides a welcome bonus for newcomers, runs sports promotions, and is anticipated to expand to another state?"
    ev, trace = asyncio.run(ctrl.run(retriever, question, True))
    assert retriever.calls == [("mix", 8), ("mix", 16)]
    assert len(ev) == 12
    assert [e.evidence_id for e in ev[:8]] == [str(i) for i in range(8)]
    assert trace.requested_top_k == (8, 16)


def test_baseline_stays_fixed_mix_eight():
    ctrl = AdaptiveController()
    retriever = RankAwareRetriever()
    ev, trace = asyncio.run(ctrl.run(retriever, "Complex question with whose relatives?", False))
    assert retriever.calls == [("mix", 8)]
    assert len(ev) == 8
    assert trace.calls == 1
