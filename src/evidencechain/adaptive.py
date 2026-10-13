"""Original candidate module A: budgeted, uncertainty-triggered retrieval expansion.

    This is a deterministic research prototype, not a trained or globally optimal policy.
"""
from dataclasses import dataclass
from .schema import Evidence, overlap
from .retrievers import Retriever


@dataclass(frozen=True)
class RetrievalTrace:
    risk: float
    coverage: float
    calls: int
    modes: tuple[str, ...]
    contexts_seen: int


class AdaptiveController:
    CUES = ("比较", "之间", "分别", "为什么", "如何", "共同", "哪些", "根据", "同时",
            "compare", "between", "both", "which", "according", "relationship", "after", "before")

    def __init__(self, risk_threshold: float = 0.43, coverage_threshold: float = 0.30,
                 first_k: int = 4, expand_k: int = 8, final_k: int = 8):
        self.risk_threshold = risk_threshold
        self.coverage_threshold = coverage_threshold
        self.first_k = first_k
        self.expand_k = expand_k
        self.final_k = final_k

    def prior_risk(self, question: str) -> float:
        low = question.lower()
        matched = sum(cue in low for cue in self.CUES)
        return min(1.0, 0.12 + min(0.42, 0.22 * matched) +
                   (0.18 if len(question) > 90 else 0.0) +
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
            evs = await retriever.search(question, mode="mix", top_k=self.final_k)
            return evs, RetrievalTrace(0.0, overlap(question, " ".join(e.content for e in evs)),
                                       1, ("mix",), len(evs))
        first = await retriever.search(question, mode="naive", top_k=self.first_k)
        coverage = overlap(question, " ".join(e.content for e in first))
        risk = self.prior_risk(question)
        if coverage < self.coverage_threshold or risk >= self.risk_threshold:
            more = await retriever.search(question, mode="mix", top_k=self.expand_k)
            evs = self._merge(first, more, self.final_k)
            return evs, RetrievalTrace(risk, coverage, 2, ("naive", "mix"), len(first)+len(more))
        return first[:self.final_k], RetrievalTrace(risk, coverage, 1, ("naive",), len(first))
