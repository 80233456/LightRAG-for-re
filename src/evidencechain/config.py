from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    llm_model: str
    embedding_model: str
    embedding_dim: int
    working_dir: str
    timeout: float
    verifier_backend: str
    nli_model: str
    support_threshold: float
    contradiction_threshold: float
    nli_device: str = "cpu"
    llm_provider: str = "ollama"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    embedding_backend: str = "ollama"
    embedding_device: str = "cuda"
    api_usage_log: str = ""
    llm_max_async: int = 2


def settings_from_env() -> Settings:
    load_dotenv(override=False)
    return Settings(
        host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        llm_model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "bge-m3"),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
        working_dir=os.getenv("LIGHTRAG_WORKDIR", "./data/lightrag_store"),
        timeout=float(os.getenv("GENERATION_TIMEOUT", "300")),
        verifier_backend=os.getenv("VERIFIER_BACKEND", "lexical"),
        nli_model=os.getenv("NLI_MODEL", "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"),
        support_threshold=float(os.getenv("SUPPORT_THRESHOLD", "0.78")),
        contradiction_threshold=float(os.getenv("CONTRADICTION_THRESHOLD", "0.70")),
        nli_device=os.getenv("NLI_DEVICE", "cpu"),
        llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        embedding_backend=os.getenv("EMBEDDING_BACKEND", "ollama"),
        embedding_device=os.getenv("EMBEDDING_DEVICE", "cuda"),
        api_usage_log=os.getenv("API_USAGE_LOG", ""),
        llm_max_async=int(os.getenv("LLM_MAX_ASYNC", "2")),
    )
