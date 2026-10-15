import asyncio
import copy
import json

import pytest

from evidencechain.grounding import JointEvidenceVerifier, QueryPlanner
from evidencechain.recovery import GroundedEvidenceChain, canonical_evidence
from evidencechain.schema import Evidence


class Client:
    def __init__(self, result):
        self.result, self.calls = result, []

    async def complete(self, prompt, **kwargs):
        self.calls.append((json.loads(prompt), kwargs))
        return json.dumps(self.result)


PROOF = {"decision": "supported", "answer_supported": True, "answers_question": True,
         "facts": [{"statement": "Alpha started before Beta.", "citations": [
             {"id": "E1", "quote": "Alpha started in 2020."},
             {"id": "E2", "quote": "Beta started in 2022."}]}]}
SOURCES = [Evidence("E1", "Alpha started in 2020.", "alpha"),
           Evidence("E2", "Beta started in 2022.", "beta")]


def test_joint_sources_and_semantic_yes():
    client = Client(PROOF)
    result = asyncio.run(JointEvidenceVerifier(client).check_answer("Did Alpha start before Beta?", "Yes", SOURCES))
    assert result["accepted"]
    assert result["verdicts"][0]["support_ids"] == ["E1", "E2"]
    assert "claims" not in client.calls[0][0]


@pytest.mark.parametrize("mutation,reason", [
    (lambda p: p["facts"][0]["citations"][0].update(quote="Alpha started in 2010."), "fabricated-or-out-of-context-quote"),
    (lambda p: p["facts"][0]["citations"][0].update(id="E99"), "unknown-citation-id"),
    (lambda p: p.update(answer_supported="true"), "answer-not-established"),
    (lambda p: p.update(facts=[]), "invalid-proof-facts"),
    (lambda p: p["facts"][0].update(citations=[]), "missing-proof-citations"),
])
def test_invalid_proof_fails_closed(mutation, reason):
    proof = copy.deepcopy(PROOF)
    mutation(proof)
    result = asyncio.run(JointEvidenceVerifier(Client(proof)).check_answer("Question", "Yes", SOURCES))
    assert not result["accepted"] and result["reason"] == reason


def test_ambiguous_ids_and_quotes_outside_visible_context():
    result = asyncio.run(JointEvidenceVerifier(Client(PROOF)).check_answer("Question", "Yes", [SOURCES[0], SOURCES[0]]))
    assert result["reason"] == "ambiguous-evidence-ids"
    result = asyncio.run(JointEvidenceVerifier(Client(PROOF), context_chars=10).check_answer("Question", "Yes", SOURCES))
    assert not result["accepted"]


def test_planner_budget_dedup_and_question_only():
    client = Client({"queries": ["Original question", "Alpha start date", "alpha start date", "Beta start date", "third extra query"]})
    queries = asyncio.run(QueryPlanner(client).plan("Original question"))
    assert queries == ["Alpha start date", "Beta start date"]
    assert client.calls[0][0] == {"question": "Original question"}
    with pytest.raises(ValueError):
        QueryPlanner(client, 3)


class Retriever:
    def __init__(self, fresh=True):
        self.calls, self.fresh = [], fresh

    async def search(self, query, **kwargs):
        self.calls.append(query)
        prefix = query if self.fresh else "question"
        return [Evidence("same-id", f"{prefix} fact number {i}", prefix) for i in range(8)]


class Generator:
    def __init__(self, answer="", malformed=False):
        self.calls, self.answer, self.malformed = [], answer, malformed

    async def generate(self, question, evidence):
        self.calls.append(evidence)
        return {"answer": self.answer, "claims": ["Claim"] if self.answer else [],
                "_format_error": "invalid" if self.malformed else None}


class Verifier:
    def __init__(self, decision="insufficient"):
        self.calls, self.decision = [], decision

    async def check_answer(self, question, answer, evidence):
        self.calls.append(evidence)
        return JointEvidenceVerifier.rejected("test", self.decision)


def make_case(answer="", fresh=True, decision="insufficient", malformed=False):
    retriever, generator, verifier = Retriever(fresh), Generator(answer, malformed), Verifier(decision)
    planner = QueryPlanner(Client({"queries": ["Alpha start date", "Beta start date"]}))
    return GroundedEvidenceChain(retriever, generator, verifier, planner)


def test_bounded_recovery_preserves_first_and_unique_ids():
    chain = make_case()
    result = asyncio.run(chain.ask("question", "full"))
    assert result["retrieval"]["calls"] == 3
    assert len(chain.generator.calls) == 2
    assert len(result["evidence"]) == 12
    assert [e["content"] for e in result["evidence"][:8]] == [e.content for e in chain.generator.calls[0]]
    assert len({e["evidence_id"] for e in result["evidence"]}) == 12
    assert result["evidence"][8]["source"] != result["evidence"][9]["source"]


@pytest.mark.parametrize("decision", ["refuted", "conflict", "invalid"])
def test_no_recovery_to_cherry_pick_refuted_candidate(decision):
    chain = make_case(answer="Wrong", decision=decision)
    result = asyncio.run(chain.ask("question", "full"))
    assert result["abstained"] and len(chain.retriever.calls) == 1


def test_no_resampling_same_context_or_malformed_generation():
    for chain in (make_case(fresh=False), make_case(malformed=True)):
        asyncio.run(chain.ask("question", "full"))
        assert len(chain.generator.calls) == 1


def test_deduplicating_initial_context_is_not_new_information():
    chain = make_case()

    async def repeated(query, **kwargs):
        return [Evidence("same", "The same factual passage.", "source")]*8

    chain.retriever.search = repeated
    asyncio.run(chain.ask("question", "full"))
    assert len(chain.generator.calls) == 1


def test_baseline_has_no_judge_or_planner_calls():
    chain = make_case(answer="Yes")
    result = asyncio.run(chain.ask("question", "baseline"))
    assert result["answer"] == "Yes"
    assert not chain.verifier.calls and not chain.planner.client.calls
    assert canonical_evidence(SOURCES)[0].content == SOURCES[0].content
