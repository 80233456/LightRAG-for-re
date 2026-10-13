"""Original candidate module B: claim-level support/refutation/conflict and selective abstention.

Lexical mode is deliberately ONLY a wiring check. Run NLI mode with thresholds tuned
on a validation set for any research comparison, and report uncalibrated scores honestly.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Protocol
import re

from .schema import Evidence, overlap, words


class PairScorer(Protocol):
    def score(self, premises: list[str], hypotheses: list[str]) -> list[tuple[float, float]]: ...


class LexicalScorer:
    """Transparent non-semantic fallback. Do not use as an award-claiming metric."""
    @staticmethod
    def _flat(text: str) -> str:
        return re.sub(r"\s+|[，。,.!?！？:：;；\-]", "", text.lower())

    def score(self, premises: list[str], hypotheses: list[str]) -> list[tuple[float, float]]:
        out = []
        for p, h in zip(premises, hypotheses):
            a, b = self._flat(p), self._flat(h)
            # Exact substring indicates likely support, but negations can reverse it.
            negative = ["不是", "并非", "没有", "not", "never", "n't"]
            a_neg = any(w in a for w in negative)
            b_neg = any(w in b for w in negative)
            ratio = overlap(h, p)
            close = (b in a or a in b) and min(len(a), len(b)) >= 4
            if (a_neg != b_neg) and ratio >= 0.55:
                out.append((0.05, 0.94))
            elif close:
                out.append((0.97, 0.01))
            else:
                out.append((min(0.74, ratio * 0.76), 0.03))
        return out


class NLIModelScorer:
    """HF NLI inference. Loaded lazily; no model downloaded during offline tests."""
    def __init__(self, model_name: str, max_length: int = 384, batch_size: int = 8):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
        self.torch = torch
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model.eval()
        self.max_length = max_length
        self.batch_size = batch_size
        raw = {int(k): str(v).lower() for k, v in self.model.config.id2label.items()}
        def index(prefix: str) -> int:
            matching = [i for i, name in raw.items() if prefix in name]
            if len(matching) != 1:
                raise ValueError(f"NLI labels can't be resolved for {model_name}: {raw}")
            return matching[0]
        self.support_id = index("entail")
        self.refute_id = index("contrad")

    def score(self, premises: list[str], hypotheses: list[str]) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        for start in range(0, len(premises), self.batch_size):
            p = premises[start:start+self.batch_size]
            h = hypotheses[start:start+self.batch_size]
            tokens = self.tokenizer(p, h, return_tensors="pt", padding=True,
                                    truncation=True, max_length=self.max_length)
            with self.torch.no_grad():
                logits = self.model(**tokens).logits
                probs = self.torch.softmax(logits, dim=-1)
            for row in probs:
                result.append((float(row[self.support_id]), float(row[self.refute_id])))
        return result


@dataclass(frozen=True)
class ClaimVerdict:
    claim: str
    label: str
    support_score: float
    contradiction_score: float
    support_id: str | None
    contradiction_id: str | None

    def as_dict(self):
        return asdict(self)


class EvidenceVerifier:
    def __init__(self, scorer: PairScorer, support_threshold: float = 0.78,
                 contradiction_threshold: float = 0.70, max_evidence: int = 8):
        self.scorer = scorer
        self.support_threshold = support_threshold
        self.contradiction_threshold = contradiction_threshold
        self.max_evidence = max_evidence

    def check(self, claims: list[str], evidence: list[Evidence]) -> dict:
        evidence = evidence[:self.max_evidence]
        if not claims or not evidence:
            return {"accepted": False, "coverage": 0.0, "verdicts": [], "reason": "no claims/evidence"}
        # Segment long chunks to reduce truncation. Keep same reference/source ID.
        windows = []
        for ev in evidence:
            text = ev.content
            for start in range(0, min(len(text), 2200), 650):
                fragment = text[start:start+750].strip()
                if fragment:
                    windows.append((ev.evidence_id, fragment))
        premises = [chunk for _, chunk in windows for _ in claims]
        hypotheses = [claim for _ in windows for claim in claims]
        scores = self.scorer.score(premises, hypotheses)
        if len(scores) != len(premises):
            raise ValueError("NLI scorer returned wrong number of pairs")
        verdicts: list[ClaimVerdict] = []
        for ci, claim in enumerate(claims):
            rows = [(windows[wi][0], *scores[wi*len(claims)+ci]) for wi in range(len(windows))]
            support = max(rows, key=lambda x: x[1])
            contra = max(rows, key=lambda x: x[2])
            if support[1] >= self.support_threshold and contra[2] >= self.contradiction_threshold:
                label = "conflict"
            elif contra[2] >= self.contradiction_threshold:
                label = "refuted"
            elif support[1] >= self.support_threshold:
                label = "supported"
            else:
                label = "insufficient"
            verdicts.append(ClaimVerdict(claim, label, round(support[1], 5),
                                         round(contra[2], 5), support[0], contra[0]))
        good = sum(v.label == "supported" for v in verdicts)
        accepted = good == len(verdicts)
        return {"accepted": accepted, "coverage": good / len(verdicts),
                "verdicts": [v.as_dict() for v in verdicts],
                "reason": "all-supported" if accepted else "unsafe-or-insufficient"}
