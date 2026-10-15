from .config import Settings
from .retrievers import DemoRetriever, LightRAGRetriever
from .generation import DemoGenerator, OllamaGenerator, DeepSeekGenerator
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
        if settings.llm_provider == "deepseek":
            generator = DeepSeekGenerator(settings)
        elif settings.llm_provider == "ollama":
            generator = OllamaGenerator(settings.host, settings.llm_model, settings.timeout)
        else:
            raise ValueError("LLM_PROVIDER must be ollama or deepseek")
    else:
        raise ValueError("backend must be demo or lightrag")
    return EvidenceChain(retriever, generator, make_verifier(settings, verifier))


async def make_grounded_chain(settings: Settings):
    """Opt-in real-model strategy; the existing NLI/demo factory is unchanged."""
    if settings.llm_provider != "deepseek":
        raise ValueError("The joint verifier currently requires the DeepSeek adapter")
    from .api_client import DeepSeekClient
    from .grounding import JointEvidenceVerifier, QueryPlanner
    from .recovery import GroundedEvidenceChain
    retriever = await LightRAGRetriever(settings).start()
    client = DeepSeekClient(settings)
    return GroundedEvidenceChain(retriever, DeepSeekGenerator(settings),
                                 JointEvidenceVerifier(client), QueryPlanner(client))


async def make_corrective_chain(settings: Settings, corpus_path: str, reranker_path: str):
    import json
    from pathlib import Path
    from .api_client import DeepSeekClient
    from .corrective import CorrectiveEvidenceChain
    from .parent_retrieval import ParentCorpusIndex, HybridParentRetriever, CrossEncoderReranker, corpus_documents
    if settings.llm_provider != 'deepseek':
        raise ValueError('Corrective strategy currently uses the DeepSeek adapter')
    client = DeepSeekClient(settings)
    documents = corpus_documents(json.loads(Path(corpus_path).read_text(encoding='utf-8')))
    index = ParentCorpusIndex(documents)
    reranker = CrossEncoderReranker(reranker_path, device=settings.embedding_device)
    graph = await LightRAGRetriever(settings).start()
    return CorrectiveEvidenceChain(HybridParentRetriever(index, graph, reranker), client)
