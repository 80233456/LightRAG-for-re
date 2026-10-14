import asyncio
from evidencechain.config import settings_from_env
from evidencechain import factory


def test_nli_device_environment_reaches_scorer(monkeypatch):
    monkeypatch.setenv("NLI_DEVICE", "cuda")
    settings = settings_from_env()
    assert settings.nli_device == "cuda"
    seen = {}

    class FakeModelScorer:
        def __init__(self, model_name, device):
            seen["model_name"] = model_name
            seen["device"] = device

        def score(self, premises, hypotheses):
            return []

    monkeypatch.setattr(factory, "NLIModelScorer", FakeModelScorer)
    checker = factory.make_verifier(settings, "nli")
    assert checker.scorer is not None
    assert seen == {"model_name": settings.nli_model, "device": "cuda"}


def test_identical_question_and_evidence_reuses_candidate():
    from scripts.eval_multihop import CachedGenerator
    from evidencechain.schema import Evidence

    class CountingGenerator:
        def __init__(self):
            self.calls = 0

        async def generate(self, question, evidence):
            self.calls += 1
            return {"answer": "Nanjing", "claims": ["The launch was in Nanjing."]}

    async def run():
        delegate = CountingGenerator()
        cache = CachedGenerator(delegate)
        e1 = [Evidence("E1", "The launch was in Nanjing.", "src")]
        a = await cache.generate("Where?", e1)
        b = await cache.generate("Where?", [Evidence("E1", "The launch was in Nanjing.", "src")])
        b["claims"].append("mutated")  # caller cannot poison cache
        c = await cache.generate("Where?", e1)
        assert delegate.calls == 1
        assert a == c
        assert len(c["claims"]) == 1
        await cache.generate("Different question?", e1)
        await cache.generate("Where?", [Evidence("E2", "The launch was in Nanjing.", "src")])
        assert delegate.calls == 3
    asyncio.run(run())
