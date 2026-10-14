"""Original candidate module B: claim-level support/refutation/conflict and selective abstention.

Lexical mode is deliberately ONLY a wiring check. Run NLI mode with thresholds tuned
on a validation set for any research comparison, and report uncalibrated scores honestly.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Protocol
import re

from .schema import Evidence, overlap


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
    def __init__(self, model_name: str, max_length: int = 384, batch_size: int = 8, device: str = "cpu"):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
        self.torch = torch
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(device)
        self.device = device
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
            tokens = {k: v.to(self.device) for k, v in tokens.items()}
            with self.torch.no_grad():
                logits = self.model(**tokens).logits
                probs = self.torch.softmax(logits, dim=-1)
            for row in probs:
                result.append((float(row[self.support_id]), float(row[self.refute_id])))
        return result



# Distinct alphanumeric IDs are entity anchors; pure years are not IDs.
_ID_PATTERN = re.compile(r"\b[a-z][a-z0-9]*(?:[-_][a-z0-9]+)+\b|\b[a-z]{1,8}\d+\b", re.I)
_NAME_PATTERN = re.compile(r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,})){1,3}\b")
_GENERIC_NAMES = {"the", "this", "that", "these", "those", "there", "with", "according", "which", "where", "what", "who"}


def entity_anchors(claim: str) -> tuple[tuple[str, ...], str | None]:
    """Identify the project/subject, falling back when no explicit anchor exists."""
    ids = tuple(dict.fromkeys(m.group().casefold() for m in _ID_PATTERN.finditer(claim)
                              if any(ch.isdigit() for ch in m.group())))
    if ids:
        return ids, None
    phrases = [m.group().casefold() for m in _NAME_PATTERN.finditer(claim)]
    phrases = [name for name in phrases if name.split()[0] not in _GENERIC_NAMES]
    return (), phrases[0] if phrases else None


def _has_exact_anchor(fragment: str, ids: tuple[str, ...], name: str | None) -> bool:
    if ids:
        found = set(m.group().casefold() for m in _ID_PATTERN.finditer(fragment))
        return all(item in found for item in ids)
    if name:
        return bool(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", fragment.casefold()))
    return True


def _windows(text: str, claim: str, limit: int, size: int = 650, stride: int = 520) -> list[str]:
    """Rank claim-relevant spans throughout each source; isolate strong-ID subjects."""
    ids, _ = entity_anchors(claim)
    if ids:
        sentences = re.split(r"(?<=[.!?。！？])\s+|(?<=[。！？])", text)
        focused = [s.strip() for s in sentences if _has_exact_anchor(s, ids, None)]
        if not focused:
            return []
        text = " ".join(focused)
    candidates = [(i, text[i:i+size].strip()) for i in range(0, len(text), stride)]
    candidates = [(i, chunk) for i, chunk in candidates if chunk]
    if len(candidates) <= limit:
        return [chunk for _, chunk in candidates]
    selected = sorted(candidates, key=lambda item: (-overlap(claim, item[1]), item[0]))[:limit]
    return [chunk for _, chunk in sorted(selected)]


@dataclass(frozen=True)
class ClaimVerdict:
    claim: str
    label: str
    support_score: float
    contradiction_score: float
    support_id: str | None
    contradiction_id: str | None
    ignored_unrelated_contradictions: int = 0

    def as_dict(self):
        return asdict(self)


class EvidenceVerifier:
    def __init__(self, scorer: PairScorer, support_threshold: float = 0.78,
                 contradiction_threshold: float = 0.70, max_evidence: int = 8,
                 windows_per_evidence: int = 5):
        self.scorer = scorer
        self.support_threshold = support_threshold
        self.contradiction_threshold = contradiction_threshold
        self.max_evidence = max_evidence
        self.windows_per_evidence = windows_per_evidence

    def check(self, claims: list[str], evidence: list[Evidence]) -> dict:
        evidence = evidence[:self.max_evidence]
        if not claims or not evidence:
            return {"accepted": False, "coverage": 0.0, "verdicts": [], "reason": "no claims/evidence"}

        pairs: list[tuple[int, str, str]] = []
        premises: list[str] = []
        hypotheses: list[str] = []
        anchors = [entity_anchors(claim) for claim in claims]
        for ci, claim in enumerate(claims):
            for ev in evidence:
                for chunk in _windows(ev.content, claim, self.windows_per_evidence):
                    pairs.append((ci, ev.evidence_id, chunk))
                    premises.append(chunk)
                    hypotheses.append(claim)
        scores = self.scorer.score(premises, hypotheses)
        if len(scores) != len(pairs):
            raise ValueError("NLI scorer returned wrong number of pairs")

        verdicts: list[ClaimVerdict] = []
        for ci, claim in enumerate(claims):
            ids, name = anchors[ci]
            supports = []
            refutations = []
            ignored = 0
            for (pair_ci, ev_id, chunk), (support_score, contradiction_score) in zip(pairs, scores):
                if pair_ci != ci:
                    continue
                same_entity = _has_exact_anchor(chunk, ids, name)
                if not ids or same_entity:
                    supports.append((ev_id, support_score))
                if same_entity:
                    refutations.append((ev_id, contradiction_score))
                elif contradiction_score >= self.contradiction_threshold:
                    ignored += 1
            support = max(supports, key=lambda x: x[1], default=(None, 0.0))
            contra = max(refutations, key=lambda x: x[1], default=(None, 0.0))
            if support[1] >= self.support_threshold and contra[1] >= self.contradiction_threshold:
                label = "conflict"
            elif contra[1] >= self.contradiction_threshold:
                label = "refuted"
            elif support[1] >= self.support_threshold:
                label = "supported"
            else:
                label = "insufficient"
            verdicts.append(ClaimVerdict(claim, label, round(support[1], 5),
                                         round(contra[1], 5), support[0], contra[0], ignored))
        supported = sum(v.label == "supported" for v in verdicts)
        accepted = supported == len(verdicts)
        return {"accepted": accepted, "coverage": supported / len(verdicts),
                "verdicts": [v.as_dict() for v in verdicts],
                "reason": "all-supported" if accepted else "unsafe-or-insufficient"}
