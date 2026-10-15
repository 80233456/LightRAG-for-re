import asyncio
import copy
import json

import pytest

from evidencechain.corrective import CorrectiveEvidenceChain, merge_preserving_context
from evidencechain.facet_verifier import FacetEvidenceVerifier, FacetPlanner, EvidenceAnswerGenerator, answers_agree
from evidencechain.parent_retrieval import ParentCorpusIndex, ParentDocument, reciprocal_rank_fusion, corpus_documents
from evidencechain.schema import Evidence


class Client:
    def __init__(self, data):
        self.data, self.calls = data, []

    async def complete(self, prompt, **kwargs):
        self.calls.append((json.loads(prompt), kwargs))
        return json.dumps(self.data)


EVIDENCE = [Evidence('A', 'Talven launched in 2019.', 'doc/a'), Evidence('B', 'Mireva launched in 2022.', 'doc/b')]
PREDICTION = {'answer': 'Yes', 'facts': [{'statement': 'Talven started first.', 'source_ids': ['A', 'B']}], 'format_error': None}
AUDIT = {'decision': 'supported', 'answer_supported': True,
         'facts': [{'statement': 'Talven launched in 2019.', 'source_ids': ['A']},
                   {'statement': 'Mireva launched in 2022.', 'source_ids': ['B']}],
         'inference': {'operation': 'temporal', 'conclusion': 'Yes.'}, 'missing_facets': [], 'reason': '2019 precedes 2022'}


def test_atomic_facts_can_support_implicit_temporal_relation():
    result = asyncio.run(FacetEvidenceVerifier(Client(AUDIT)).check('Before?', ['Talven date', 'Mireva date'], PREDICTION, EVIDENCE))
    assert result['accepted']
    assert result['verdicts'][0]['citations'][0]['quote'] == EVIDENCE[0].content
    assert result['verdicts'][0]['citations'][0]['quote_origin'] == 'program-copied-source-passage'


@pytest.mark.parametrize('candidate,conclusion,expected', [
    ('No', 'No, both reports agree.', True), ('Yes', 'Yes: the source supports it.', True),
    ('No', 'Yes, they disagree.', False), ('No', 'The answer might be No.', False),
    ('No', 'No one can tell.', False), ('No', 'No doubt the answer is Yes.', False),
    ('Google', 'The company is Google.', False), ('Google', 'Google.', True),
])
def test_short_answer_polarity_parser(candidate, conclusion, expected):
    assert answers_agree(candidate, conclusion) is expected


def test_supported_with_missing_facet_is_not_approved():
    data = copy.deepcopy(AUDIT)
    data['missing_facets'] = [0]
    result = asyncio.run(FacetEvidenceVerifier(Client(data)).check('Question', ['Facet'], PREDICTION, EVIDENCE))
    assert not result['accepted'] and result['decision'] == 'insufficient'


def test_author_is_corpus_metadata_not_inferred_from_question():
    doc = corpus_documents([{'title': 'Article', 'author': 'Actual Author', 'body': 'A factual paragraph.'}])[0]
    assert 'Author: Actual Author' in doc.header


def test_valid_eight_source_fact_is_allowed_and_not_silently_truncated():
    evidence = [Evidence(f'P{i}', f'Factual paragraph number {i}.', f'doc/{i}') for i in range(8)]
    data = copy.deepcopy(AUDIT)
    data['facts'] = [{'statement': 'A joint factual chain.', 'source_ids': [e.evidence_id for e in evidence]}]
    result = asyncio.run(FacetEvidenceVerifier(Client(data)).check('Question', ['Facet'], PREDICTION, evidence))
    assert result['accepted'] and len(result['verdicts'][0]['support_ids']) == 8


@pytest.mark.parametrize('change,reason', [
    (lambda d: d['facts'][0].update(source_ids=['FAKE']), 'unknown-proof-source'),
    (lambda d: d.update(answer_supported='true'), 'answer-not-supported'),
    (lambda d: d['inference'].update(conclusion='No'), 'inference-answer-mismatch'),
    (lambda d: d['inference'].update(operation='guess'), 'inference-answer-mismatch'),
    (lambda d: d.update(facts=[]), 'invalid-proof-facts'),
])
def test_invalid_fact_proofs_are_not_approved(change, reason):
    data = copy.deepcopy(AUDIT)
    change(data)
    result = asyncio.run(FacetEvidenceVerifier(Client(data)).check('Question', ['Fact'], PREDICTION, EVIDENCE))
    assert not result['accepted'] and result['reason'] == reason


def test_planner_has_no_candidate_or_gold_input_and_is_bounded():
    client = Client({'facets': ['First factual need', 'Second factual need', 'Third factual need', 'Fourth factual need', 'Fifth ignored']})
    result = asyncio.run(FacetPlanner(client).plan('Question'))
    assert len(result) == 4 and client.calls[0][0] == {'question': 'Question'}


def test_generator_rejects_unknown_citation_and_sanitizes_missing():
    client = Client({'answer': 'Name', 'facts': [{'statement': 'A fact.', 'source_ids': ['FAKE']}]})
    result = asyncio.run(EvidenceAnswerGenerator(client).generate('Question', ['Facet'], EVIDENCE))
    assert result['format_error']
    client = Client({'answer': '', 'facts': [], 'missing_facets': None})
    result = asyncio.run(EvidenceAnswerGenerator(client).generate('Question', ['Facet'], EVIDENCE))
    assert result['missing_facets'] == [] and not result['format_error']


def test_rrf_deduplicates_each_ranking_and_is_deterministic():
    assert reciprocal_rank_fusion([['a', 'a', 'b'], ['b', 'a']])[0] == 'a'
    assert reciprocal_rank_fusion([]) == []


def test_parent_expansion_reaches_text_after_prefix_with_exact_offsets():
    body = 'Newsletter boilerplate. '*120+'Talven launched in 2019. '+'Tail. '*120
    index = ParentCorpusIndex([ParentDocument('doc/a', 'Source: Journal', body),
                               ParentDocument('doc/b', 'Source: Other', 'Mireva launched in 2022. '*10)])
    selected = index.rank_windows('Talven launched 2019', {'doc/a'}, 1)
    evidence, provenance = index.expand(selected)
    assert 'Talven launched in 2019.' in evidence[0].content
    span = provenance[evidence[0].evidence_id]
    assert evidence[0].content == 'Source: Journal\nBody:\n'+body[span['body_start']:span['body_end']]
    assert sum(len(e.content) for e in evidence) <= 64000


def test_parent_ids_must_be_unique():
    with pytest.raises(ValueError):
        ParentCorpusIndex([ParentDocument('a', '', 'Fact'), ParentDocument('a', '', 'Other')])


def test_context_merge_preserves_initial_passages_under_budget():
    extra = [Evidence('C', 'Extra fact.', 'doc/c')]
    assert merge_preserving_context(EVIDENCE, extra)[:2] == EVIDENCE
    with pytest.raises(ValueError):
        merge_preserving_context(EVIDENCE, extra, char_budget=2)


class Retriever:
    def __init__(self, fresh=True):
        self.calls, self.fresh = [], fresh

    async def retrieve(self, question, facets, extra_queries=None, seed=None):
        self.calls.append(extra_queries)
        evidence = EVIDENCE+([Evidence('C', 'New supporting fact.', 'doc/c')] if seed is not None and self.fresh else [])
        return evidence, {'graph_calls': [{'query': question}] if seed is None else [{'query': q} for q in extra_queries]}


class Planner:
    async def plan(self, question):
        return ['First factual need', 'Second factual need']


class Generator:
    def __init__(self):
        self.calls = []

    async def generate(self, question, facets, evidence, feedback=None):
        self.calls.append(feedback)
        return copy.deepcopy(PREDICTION)


class Verifier:
    def __init__(self, decision):
        self.decision = decision

    async def check(self, *args):
        return FacetEvidenceVerifier.reject('Needs repair', self.decision)


def chain(decision, fresh=True):
    result = CorrectiveEvidenceChain(Retriever(fresh), Client({}))
    result.planner, result.generator, result.verifier = Planner(), Generator(), Verifier(decision)
    return result


@pytest.mark.parametrize('decision', ['conflict', 'invalid'])
def test_conflict_or_invalid_cannot_trigger_evidence_cherry_picking(decision):
    instance = chain(decision)
    output = asyncio.run(instance.ask('Question'))
    assert len(instance.retriever.calls) == 1 and len(instance.generator.calls) == 1
    assert output['abstained']


def test_refutation_repairs_with_feedback_without_new_retrieval():
    instance = chain('refuted')
    output = asyncio.run(instance.ask('Question'))
    assert len(instance.retriever.calls) == 1 and len(instance.generator.calls) == 2
    assert instance.generator.calls[1]['decision'] == 'refuted'
    assert output['retrieval']['calls'] == 1


def test_insufficiency_is_bounded_and_keeps_initial_context():
    instance = chain('insufficient')
    output = asyncio.run(instance.ask('Question'))
    assert len(instance.retriever.calls) == 2 and len(instance.generator.calls) == 2
    assert [e['evidence_id'] for e in output['evidence'][:2]] == ['A', 'B']
    assert output['retrieval']['calls'] <= 3


def test_duplicate_only_retrieval_never_resamples_generation():
    instance = chain('insufficient', fresh=False)
    asyncio.run(instance.ask('Question'))
    assert len(instance.generator.calls) == 1
