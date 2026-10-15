"""Candidate-driven, bounded recovery with independently reconstructed evidence."""
from __future__ import annotations

import json
from time import perf_counter

from .grounding import JointEvidenceVerifier, QueryPlanner
from .pipeline import VARIANTS
from .schema import Evidence, overlap


def canonical_evidence(evidence: list[Evidence]) -> list[Evidence]:
    return [Evidence(f"E{i+1}", item.content, item.source) for i, item in enumerate(evidence)]


def merge_balanced(first: list[Evidence], groups: list[list[Evidence]], limit: int) -> list[Evidence]:
    result, seen = [], set()
    for item in first:
        token = (item.source, item.content)
        if token not in seen:
            seen.add(token)
            result.append(item)
    queues = [list(group) for group in groups]
    while len(result) < limit and any(queues):
        for queue in queues:
            while queue:
                item = queue.pop(0)
                token = (item.source, item.content)
                if token not in seen:
                    seen.add(token)
                    result.append(item)
                    break
            if len(result) == limit:
                break
    return canonical_evidence(result[:limit])


class GroundedEvidenceChain:
    def __init__(self, retriever, generator, verifier: JointEvidenceVerifier, planner: QueryPlanner,
                 first_k: int = 8, final_k: int = 12):
        if first_k <= 0 or final_k < first_k:
            raise ValueError("Final evidence budget must preserve the first retrieval")
        self.retriever, self.generator = retriever, generator
        self.verifier, self.planner = verifier, planner
        self.first_k, self.final_k = first_k, final_k

    async def _generate(self, question, evidence):
        try:
            prediction = await self.generator.generate(question, evidence)
            return prediction, prediction.get("_format_error") or getattr(self.generator, "last_format_error", None)
        except ValueError as error:
            if not isinstance(error, json.JSONDecodeError) and not any(message in str(error) for message in
                    ["Nonempty answer must contain 1-3 claims", "Expected JSON", "Expected claims"]):
                raise
            return {"answer": "", "claims": []}, str(error)

    async def ask(self, question: str, variant: str = "full") -> dict:
        if variant not in VARIANTS:
            raise ValueError(f"variant must be one of {VARIANTS}")
        started = perf_counter()
        verified = variant in ("verify", "full")
        first = await self.retriever.search(question, mode="mix", top_k=self.first_k)
        # Keep generation input identical to baseline for a paired first-pass comparison.
        prediction, format_error = await self._generate(question, first)
        evidence = canonical_evidence(first)
        report = await self.verifier.check_answer(question, prediction["answer"], evidence) if verified else None
        attempts = [{"candidate_answer": prediction["answer"], "candidate_claims": prediction["claims"],
                     "evidence_count": len(evidence), "decision": report["decision"] if report else None,
                     "generation_format_error": format_error}]
        queries, groups = [], []
        recover = (not format_error and variant in ("adaptive", "full") and
                   (not prediction["answer"] or (report is not None and report["decision"] == "insufficient")))
        if recover:
            queries = await self.planner.plan(question)
            for query in queries:
                groups.append(await self.retriever.search(query, mode="mix", top_k=self.first_k))
            merged = merge_balanced(first, groups, self.final_k)
            old_content = {(e.source, e.content) for e in evidence}
            if any((e.source, e.content) not in old_content for e in merged):
                evidence = merged
                prediction, format_error = await self._generate(question, evidence)
                report = await self.verifier.check_answer(question, prediction["answer"], evidence) if verified else None
                attempts.append({"candidate_answer": prediction["answer"], "candidate_claims": prediction["claims"],
                                 "evidence_count": len(evidence), "decision": report["decision"] if report else None,
                                 "generation_format_error": format_error})
        accepted = not format_error and bool(prediction["answer"]) and (not verified or bool(report["accepted"]))
        citations = list(dict.fromkeys(source for verdict in report["verdicts"] for source in verdict["support_ids"])) if accepted and report else []
        claims = [verdict["claim"] for verdict in report["verdicts"]] if accepted and report else prediction["claims"]
        return {"question": question, "variant": variant, "answer": prediction["answer"] if accepted else "",
                "candidate_answer": prediction["answer"], "candidate_claims": prediction["claims"],
                "claims": claims, "abstained": not accepted, "citation_ids": citations,
                "evidence": [item.as_dict() for item in evidence], "verification": report,
                "retrieval": {"risk": None, "coverage": overlap(question, " ".join(e.content for e in first)),
                              "calls": 1+len(queries), "modes": ["mix"]*(1+len(queries)),
                              "contexts_seen": len(first)+sum(len(group) for group in groups),
                              "requested_top_k": [self.first_k]*(1+len(queries)),
                              "recovery_queries": queries, "generation_attempts": len(attempts)},
                "generation_format_error": format_error, "attempts": attempts,
                "latency_ms": round((perf_counter()-started)*1000, 2)}
