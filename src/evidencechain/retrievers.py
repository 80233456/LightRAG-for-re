"""Retriever adapters. LightRAG's aquery_data() is the stable structured retrieval boundary."""
from __future__ import annotations
from functools import partial
import hashlib
import os
import asyncio
from pathlib import Path
from urllib.parse import quote, unquote
from typing import Protocol

from .config import Settings
from .schema import Evidence, overlap


class Retriever(Protocol):
    async def search(self, query: str, mode: str, top_k: int) -> list[Evidence]: ...
    async def add(self, documents: list[dict[str, str]]) -> None: ...
    async def close(self) -> None: ...


class DemoRetriever:
    """Deterministic in-memory retrieval for offline smoke tests ONLY."""

    def __init__(self, documents: list[dict[str, str]] | None = None):
        self.documents = list(documents or [])

    async def add(self, documents: list[dict[str, str]]) -> None:
        self.documents.extend(documents)

    async def search(self, query: str, mode: str, top_k: int) -> list[Evidence]:
        ranked = sorted(self.documents, key=lambda d: overlap(query, d["text"]), reverse=True)
        return [Evidence(f"E{i+1}", d["text"], d.get("id", str(i))) for i, d in enumerate(ranked[:top_k])]

    async def close(self) -> None:
        return None


class LightRAGRetriever:
    """Use exact upstream Python SDK interface checked against HKUDS/LightRAG 2026-10-14.

    Once installed, record the exact `lightrag-hku` version and git revision in experiments.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.rag = None

    async def start(self):
        try:
            from lightrag import LightRAG
            from lightrag.llm.ollama import ollama_model_complete, ollama_embed
            from lightrag.utils import EmbeddingFunc
        except ImportError as e:
            raise RuntimeError("缺少 LightRAG 依赖：pip install -e '.[real]'") from e

        Path(self.settings.working_dir).mkdir(parents=True, exist_ok=True)
        llm_func = ollama_model_complete
        llm_kwargs = {"host": self.settings.host, "options": {"num_ctx": 8192},
                      "timeout": int(self.settings.timeout)}
        if self.settings.llm_provider == "deepseek":
            from .api_client import DeepSeekClient
            llm_func = DeepSeekClient(self.settings).complete
            llm_kwargs = {}
        elif self.settings.llm_provider != "ollama":
            raise ValueError("LLM_PROVIDER must be ollama or deepseek")
        embed_func = partial(ollama_embed.func, embed_model=self.settings.embedding_model,
                             host=self.settings.host)
        if self.settings.embedding_backend == "sentence_transformers":
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(
                self.settings.embedding_model, device=self.settings.embedding_device)

            async def local_embed(texts, **kwargs):
                vectors = await asyncio.to_thread(
                    self.embedding_model.encode, texts, normalize_embeddings=True,
                    batch_size=16, show_progress_bar=False)
                if vectors.shape[1] != self.settings.embedding_dim:
                    raise ValueError("Actual embedding dimension differs from EMBEDDING_DIM")
                return vectors

            embed_func = local_embed
        elif self.settings.embedding_backend != "ollama":
            raise ValueError("EMBEDDING_BACKEND must be ollama or sentence_transformers")
        self.rag = LightRAG(
            working_dir=self.settings.working_dir,
            llm_model_func=llm_func,
            llm_model_name=self.settings.llm_model,
            llm_model_kwargs=llm_kwargs,
            llm_model_max_async=self.settings.llm_max_async,
            max_parallel_insert=min(self.settings.llm_max_async, 12),
            embedding_func_max_async=1,
            embedding_func=EmbeddingFunc(
                embedding_dim=self.settings.embedding_dim,
                max_token_size=8192,
                func=embed_func,
            ),
        )
        await self.rag.initialize_storages()
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()
        return self

    async def add(self, documents: list[dict[str, str]]) -> None:
        if self.rag is None:
            raise RuntimeError("先调用 await retriever.start()")
        # Ingest in batches. file_path stays in returned chunk provenance.
        for doc in documents:
            body = doc["text"].strip()
            if not body:
                continue
            source = str(doc.get("id") or hashlib.sha1(body.encode()).hexdigest()[:12])
            # Preserve hierarchy even when upstream uses file basename as a key.
            await self.rag.ainsert(body, file_paths=quote(source, safe=""))

    async def search(self, query: str, mode: str = "mix", top_k: int = 8) -> list[Evidence]:
        if self.rag is None:
            raise RuntimeError("先调用 await retriever.start()")
        from lightrag import QueryParam
        result = await self.rag.aquery_data(
            query, param=QueryParam(mode=mode, top_k=top_k, chunk_top_k=top_k, enable_rerank=False)
        )
        if result.get("status") == "failure":
            return []
        chunks = (result.get("data") or {}).get("chunks") or []
        evidences = []
        for idx, chunk in enumerate(chunks[:top_k]):
            text = str(chunk.get("content", "")).strip()
            if not text:
                continue
            evidences.append(Evidence(
                evidence_id=str(chunk.get("reference_id") or chunk.get("chunk_id") or f"E{idx+1}"),
                content=text,
                source=unquote(str(chunk.get("file_path") or "unknown")),
            ))
        return evidences

    async def close(self) -> None:
        if self.rag is not None:
            await self.rag.finalize_storages()
            self.rag = None
