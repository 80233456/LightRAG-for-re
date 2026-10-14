from .config import Settings
from .retrievers import DemoRetriever, LightRAGRetriever
from .generation import DemoGenerator, OllamaGenerator
from .verifier import EvidenceVerifier, LexicalScorer, NLIModelScorer
from .pipeline import EvidenceChain


def make_verifier(settings: Settings, backend: str | None = None):
    backend = backend or settings.verifier_backend
    if backend == "lexical":
        scorer = LexicalScorer()
    elif backend == "nli":
        scorer = NLIModelScorer(settings.nli_model, device=settings.nli_device)
    else:
        raise ValueError("verifier backend must be lexical or nli")
    return EvidenceVerifier(scorer, settings.support_threshold, settings.contradiction_threshold)


async def make_chain(settings: Settings, backend: str = "demo", verifier: str | None = None):
    if backend == "demo":
        retriever = DemoRetriever()
        generator = DemoGenerator()
    elif backend == "lightrag":
        retriever = await LightRAGRetriever(settings).start()
        generator = OllamaGenerator(settings.host, settings.llm_model, settings.timeout)
    else:
        raise ValueError("backend must be demo or lightrag")
    return EvidenceChain(retriever, generator, make_verifier(settings, verifier))
