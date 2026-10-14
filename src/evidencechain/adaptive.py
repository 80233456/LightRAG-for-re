"""Budgeted adaptive expansion that keeps the original mix@8 baseline intact.

Heuristic policy, not a learned multihop classifier; requires new blind tests.
"""
from dataclasses import dataclass
import re

from .schema import Evidence, overlap
from .retrievers import Retriever


@dataclass(frozen=True)
class RetrievalTrace:
    risk: float
    coverage: float
    calls: int
    modes: tuple[str, ...]
    contexts_seen: int
    requested_top_k: tuple[int, ...] = ()


class AdaptiveController:
    """Preserve the first mix@8 results; expand to mix@16 for likely missing hops."""
    STRONG_CUES = ("比较", "之间", "分别", "为什么", "如何", "共同", "哪些", "同时",
                   "compare", "between", "both", "whose", "whom", "respectively",
                   "relationship", "according to", "before", "after", "followed by")
    CHAIN_PATTERNS = (
        re.compile(r"\b(?:who|which|what)\b.{8,}\b(?:who|whose|that|which|where|and)\b", re.I),
        re.compile(r"\bof\b.{2,80}\bof\b", re.I),
        re.compile(r"\b(?:who|which|what)\b.{8,}[;,].{8,}", re.I),
        re.compile(r"(?:谁|哪|何|什么).{1,35}(?:的|之后|之前).{1,25}(?:的|所|导致)")
    )

    def __init__(self, risk_threshold: float = 0.50, coverage_threshold: float = 0.30,
                 first_k: int = 8, expand_k: int = 16, final_k: int = 12,
                 baseline_k: int = 8):
        if min(first_k, expand_k, final_k, baseline_k) <= 0:
            raise ValueError("retrieval sizes must be positive")
        if final_k < first_k:
            raise ValueError("final_k must not discard first-pass evidence")
        self.risk_threshold = risk_threshold
        self.coverage_threshold = coverage_threshold
        self.first_k = first_k
        self.expand_k = expand_k
        self.final_k = final_k
        self.baseline_k = baseline_k

    def prior_risk(self, question: str) -> float:
        low = question.casefold()
        count = sum(cue in low for cue in self.STRONG_CUES)
        structured = any(p.search(question) for p in self.CHAIN_PATTERNS)
        return min(1.0, 0.12 + min(0.36, 0.18 * count) +
                   (0.30 if structured else 0.0) +
                   (0.16 if len(question) > 100 else 0.0) +
                   (0.12 if question.count("?") + question.count("？") > 1 else 0.0))

    @staticmethod
    def _merge(a: list[Evidence], b: list[Evidence], limit: int) -> list[Evidence]:
        result = []
        seen = set()
        for ev in a + b:
            key = (ev.source, ev.content)
            if key not in seen:
                seen.add(key)
                result.append(ev)
            if len(result) >= limit:
                break
        return result

    async def run(self, retriever: Retriever, question: str, adaptive: bool = True):
        if not adaptive:
            evs = await retriever.search(question, mode="mix", top_k=self.baseline_k)
            return evs, RetrievalTrace(0.0, overlap(question, " ".join(e.content for e in evs)),
                                       1, ("mix",), len(evs), (self.baseline_k,))
        first = await retriever.search(question, mode="mix", top_k=self.first_k)
        coverage = overlap(question, " ".join(e.content for e in first))
        risk = self.prior_risk(question)
        if coverage < self.coverage_threshold or risk >= self.risk_threshold:
            more = await retriever.search(question, mode="mix", top_k=self.expand_k)
            evs = self._merge(first, more, self.final_k)
            return evs, RetrievalTrace(risk, coverage, 2, ("mix", "mix"),
                                       len(first) + len(more), (self.first_k, self.expand_k))
        return first, RetrievalTrace(risk, coverage, 1, ("mix",), len(first), (self.first_k,))
