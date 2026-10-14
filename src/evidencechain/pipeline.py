"""Deterministic ablation switches: baseline, adaptive-only, verifier-only, full."""
from __future__ import annotations
from time import perf_counter
from dataclasses import asdict

from .adaptive import AdaptiveController
from .generation import Generator
from .retrievers import Retriever
from .verifier import EvidenceVerifier
from .answer_guard import answer_anchored_in_claims

VARIANTS = ("baseline", "adaptive", "verify", "full")


class EvidenceChain:
    def __init__(self, retriever: Retriever, generator: Generator,
                 verifier: EvidenceVerifier, controller: AdaptiveController | None = None):
        self.retriever = retriever
        self.generator = generator
        self.verifier = verifier
        self.controller = controller or AdaptiveController()

    async def ask(self, question: str, variant: str = "full") -> dict:
        if variant not in VARIANTS:
            raise ValueError(f"variant must be one of {VARIANTS}")
        t0 = perf_counter()
        evidences, trace = await self.controller.run(self.retriever, question,
                                                   adaptive=variant in ("adaptive", "full"))
        prediction = await self.generator.generate(question, evidences)
        raw_answer = prediction["answer"]
        claims = prediction["claims"]
        verified = variant in ("verify", "full")
        report = self.verifier.check(claims, evidences) if verified else None
        # Grounded claims alone must not license a contradictory answer.
        answer_claim_consistent = answer_anchored_in_claims(raw_answer, claims) if verified else None
        if report is not None:
            report["answer_claim_consistent"] = answer_claim_consistent
            if not answer_claim_consistent:
                report["reason"] = "answer-claim-mismatch"
                report["accepted"] = False
        accepted = bool(raw_answer) and (not verified or bool(report["accepted"]))
        cited_ids = []
        if report and accepted:
            cited_ids = list(dict.fromkeys(
                source_id
                for verdict in report["verdicts"]
                for source_id in (verdict.get("support_ids") or
                                  ([verdict["support_id"]] if verdict["support_id"] else []))
            ))
        return {
            "question": question,
            "variant": variant,
            "answer": raw_answer if accepted else "",
            "candidate_answer": raw_answer,
            "abstained": not accepted,
            "claims": claims,
            "citation_ids": cited_ids,
            "evidence": [e.as_dict() for e in evidences],
            "retrieval": asdict(trace),
            "verification": report,
            "latency_ms": round((perf_counter() - t0) * 1000, 2),
        }
