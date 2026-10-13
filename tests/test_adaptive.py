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
    assert trace.modes == ("naive", "mix")


def test_baseline_is_fixed():
    ctrl = AdaptiveController()
    _, trace = asyncio.run(ctrl.run(DemoRetriever([]), "abc question", False))
    assert trace.calls == 1
    assert trace.modes == ("mix",)
