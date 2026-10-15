import asyncio
import copy
import json

import pytest

from evidencechain.boolean_verifier import validate_logic, evaluate_logic, BooleanEvidenceVerifier, complete_documents
from evidencechain.corrective import CorrectiveEvidenceChain
from evidencechain.schema import Evidence
from evidencechain.facet_verifier import FacetPlanner


def atom(name='a1', scope='world'):
    return {'id': name, 'statement': 'Talven launched before Mireva.', 'facet': 0, 'scope': scope}


def logic(expression=None, atoms=None):
    return {'atoms': atoms or [atom()], 'expression': expression or {'atom': 'a1'}}


@pytest.mark.parametrize('op,values,expected', [
    ('and', [True, None], None), ('and', [False, None], False), ('and', [True, True], True),
    ('or', [False, None], None), ('or', [True, None], True), ('or', [False, False], False),
])
def test_three_valued_composition(op, values, expected):
    expr = {'op': op, 'args': [{'atom': 'a1'}, {'atom': 'a2'}]}
    validate_logic(logic(expr, [atom('a1'), atom('a2')]))
    result, _ = evaluate_logic(expr, dict(zip(['a1', 'a2'], values)))
    assert result is expected


def test_unknown_negation_is_unknown_not_true():
    expr = {'op': 'not', 'args': [{'atom': 'a1'}]}
    assert evaluate_logic(expr, {'a1': None})[0] is None
    assert evaluate_logic(expr, {'a1': True})[0] is False


@pytest.mark.parametrize('value', [
    logic({'op': '__import__', 'args': []}), logic({'atom': 'missing'}),
    logic({'op': 'not', 'args': []}), logic(atoms=[atom(), atom('a2')]),
])
def test_invalid_or_omitted_logic_never_executes(value):
    with pytest.raises(ValueError):
        validate_logic(value)


class Client:
    def __init__(self, result):
        self.result, self.calls = result, []

    async def complete(self, prompt, **kwargs):
        self.calls.append(json.loads(prompt))
        return json.dumps(self.result)


EVIDENCE = [Evidence('P0', 'Talven launched in 2019, and Mireva in 2022.', 'doc/a')]
PROVENANCE = {'P0': {'body_start': 0, 'body_end': len(EVIDENCE[0].content), 'body_total_chars': len(EVIDENCE[0].content)}}
PREDICTION = {'answer': 'No', 'facts': [], 'format_error': None}
TABLE = {'atoms': [{'id': 'a1', 'status': 'supported', 'basis': 'explicit', 'source_ids': ['P0'],
                    'explanation': '2019 is before 2022.'}]}


def check(table=TABLE, question_logic=None, provenance=PROVENANCE):
    client = Client(table)
    plan = {'facets': ['Launch chronology'], 'logic': question_logic or logic(), 'boolean': True}
    result = asyncio.run(BooleanEvidenceVerifier(client).check(plan, PREDICTION, EVIDENCE, provenance))
    return result, client


def test_verification_is_answer_blind_and_can_correct_wrong_polarity():
    result, client = check()
    assert result['accepted'] and result['resolved_answer'] == 'Yes'
    assert not result['candidate_accepted'] and result['answer_corrected']
    assert set(client.calls[0]) == {'claims', 'sources'}
    assert 'candidate_answer' not in json.dumps(client.calls[0])


def test_negation_is_computed_not_inferred_from_label_wording():
    result, _ = check(question_logic=logic({'op': 'not', 'args': [{'atom': 'a1'}]}))
    assert result['resolved_answer'] == 'No' and result['candidate_accepted']


@pytest.mark.parametrize('state', ['unknown', 'conflict'])
def test_unresolved_atomic_evidence_does_not_produce_answer(state):
    table = copy.deepcopy(TABLE)
    table['atoms'][0]['status'] = state
    result, _ = check(table)
    assert not result['accepted'] and 'resolved_answer' not in result


def test_unknown_citation_fails_closed():
    table = copy.deepcopy(TABLE)
    table['atoms'][0]['source_ids'] = ['FORGED']
    result, _ = check(table)
    assert not result['accepted'] and result['reason'] == 'unknown-atom-source'


def test_absence_requires_complete_report_and_never_negates_world_event():
    table = copy.deepcopy(TABLE)
    table['atoms'][0].update(status='refuted', basis='absence')
    expr = {'op': 'not', 'args': [{'atom': 'a1'}]}
    report_logic = logic(expr, [atom(scope='report_content')])
    result, _ = check(table, report_logic, {})
    assert not result['accepted']
    result, _ = check(table, report_logic, PROVENANCE)
    assert result['resolved_answer'] == 'Yes'
    result, _ = check(table, logic(expr), PROVENANCE)
    assert not result['accepted']


def test_document_coverage_must_not_have_gaps():
    evidence = [Evidence('P0', 'first', 'doc/a'), Evidence('P1', 'last', 'doc/a')]
    provenance = {'P0': {'body_start': 0, 'body_end': 5, 'body_total_chars': 20},
                  'P1': {'body_start': 10, 'body_end': 20, 'body_total_chars': 20}}
    assert not complete_documents(evidence, provenance)
    provenance['P0']['body_end'] = 10
    assert complete_documents(evidence, provenance) == {'doc/a'}


def test_pipeline_returns_resolved_boolean_not_refuted_candidate():
    class Planner:
        async def plan_structured(self, question):
            return {'facets': ['Launch chronology'], 'logic': logic(), 'boolean': True}

    class Retriever:
        async def retrieve(self, *args, **kwargs):
            return EVIDENCE, {'graph_calls': [], 'provenance': PROVENANCE}

    class Generator:
        async def generate(self, *args, **kwargs):
            return PREDICTION

    client = Client(TABLE)
    chain = CorrectiveEvidenceChain(Retriever(), client)
    chain.planner, chain.generator = Planner(), Generator()
    result = asyncio.run(chain.ask('Did Talven launch before Mireva?', 'verify'))
    assert result['candidate_answer'] == 'No' and result['answer'] == 'Yes'
    assert result['verification']['answer_corrected']
    client.calls.clear()
    result = asyncio.run(chain.ask('Did Talven launch before Mireva?', 'context_only'))
    assert result['answer'] == 'No' and not client.calls


def test_invalid_logic_preserves_valid_retrieval_facets():
    client = Client({'facets': ['First named factual need', 'Second named factual need'],
                     'logic': {'atoms': [atom()], 'expression': {'op': 'unsafe', 'args': []}}})
    plan = asyncio.run(FacetPlanner(client).plan_structured('Did the events agree?'))
    assert len(plan['facets']) == 2 and plan['logic'] is None and plan['boolean']


def test_identity_question_is_not_changed_into_boolean_selection():
    client = Client({'facets': ['A descriptive factual clue'], 'logic': logic()})
    plan = asyncio.run(FacetPlanner(client).plan_structured('Which project launched first?'))
    assert not plan['boolean'] and plan['logic'] is None
