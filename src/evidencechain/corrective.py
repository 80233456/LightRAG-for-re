"""Bounded corrective QA; evidence insufficiency triggers repair, not silent approval."""
from __future__ import annotations

from time import perf_counter

from .facet_verifier import FacetPlanner, EvidenceAnswerGenerator, FacetEvidenceVerifier


def merge_preserving_context(first, extra, char_budget=96000, passage_budget=32):
    if sum(len(e.content) for e in first) > char_budget or len(first) > passage_budget:
        raise ValueError('Budget would discard initial evidence')
    result, seen, used = [], set(), 0
    for evidence in first+extra:
        if evidence.evidence_id in seen:
            continue
        if len(result) >= passage_budget or used+len(evidence.content) > char_budget:
            continue
        seen.add(evidence.evidence_id)
        result.append(evidence)
        used += len(evidence.content)
    return result


class CorrectiveEvidenceChain:
    def __init__(self, retriever, client):
        self.retriever = retriever
        self.planner = FacetPlanner(client)
        self.generator = EvidenceAnswerGenerator(client)
        self.verifier = FacetEvidenceVerifier(client)
        from .boolean_verifier import BooleanEvidenceVerifier
        self.boolean_verifier = BooleanEvidenceVerifier(client)

    async def verify_candidate(self, question, plan, prediction, evidence, provenance):
        if plan['boolean']:
            atomic = await self.boolean_verifier.check(plan, prediction, evidence, provenance)
            if atomic['accepted'] or atomic['decision'] == 'conflict':
                return atomic
            if atomic['decision'] == 'insufficient' or atomic['reason'] == 'invalid-boolean-plan':
                joint = await self.verifier.check(question, plan['facets'], prediction, evidence, provenance)
                joint['atomic_audit'] = atomic
                joint['verification_path'] = 'joint-facet-fallback-after-atomic-uncertainty'
                return joint
            return atomic
        return await self.verifier.check(question, plan['facets'], prediction, evidence, provenance)

    async def ask(self, question, variant='full'):
        if variant not in ('context_only', 'verify', 'full'):
            raise ValueError('Expected context_only, verify, or full')
        started = perf_counter()
        if hasattr(self.planner, 'plan_structured'):
            plan = await self.planner.plan_structured(question)
        else:
            plan = {'facets': await self.planner.plan(question), 'logic': None, 'boolean': False}
        facets = plan['facets']
        evidence, trace = await self.retriever.retrieve(question, facets)
        graph_calls = list(trace['graph_calls'])
        provenance = dict(trace.get('provenance') or {})
        prediction = await self.generator.generate(question, facets, evidence)
        verified = variant != 'context_only'

        async def verify():
            return await self.verify_candidate(question, plan, prediction, evidence, provenance)

        report = await verify() if verified else None
        attempts = [{'prediction': prediction, 'verification': report, 'retrieval': trace}]
        if (variant == 'full' and not prediction.get('format_error') and
                report['decision'] in ('insufficient', 'refuted')):
            feedback = {'candidate': prediction['answer'], 'decision': report['decision'],
                        'reason': report['reason'], 'missing_facets': report['missing_facets']}
            context_changed = False
            if report['decision'] == 'insufficient':
                missing = report['missing_facets'] or list(range(len(facets)))
                queries = [facets[i] for i in missing[:2]]
                candidate = prediction['answer'].strip()
                # A bridge entity is usable only if actually observed in retrieved text.
                observed = candidate and len(candidate) >= 3 and len(candidate.split()) <= 8 and candidate.casefold() not in ('yes', 'no')
                observed = observed and any(candidate.casefold() in item.content.casefold() for item in evidence)
                if observed:
                    queries = [query+' '+candidate for query in queries]
                extra, extra_trace = await self.retriever.retrieve(question, facets, extra_queries=queries, seed=evidence)
                graph_calls += extra_trace['graph_calls']
                provenance.update(extra_trace.get('provenance') or {})
                merged = merge_preserving_context(evidence, extra)
                context_changed = {e.evidence_id for e in merged} != {e.evidence_id for e in evidence}
                evidence = merged
                trace = extra_trace
            if context_changed or report['decision'] == 'refuted':
                prediction = await self.generator.generate(question, facets, evidence, feedback)
                report = await verify()
                attempts.append({'prediction': prediction, 'verification': report, 'retrieval': trace,
                                 'repair_feedback': feedback})
        final_answer = report.get('resolved_answer', prediction['answer']) if verified else prediction['answer']
        accepted = bool(final_answer) and not prediction.get('format_error') and (not verified or report['accepted'])
        verdicts = report['verdicts'] if accepted and report else []
        cited = list(dict.fromkeys(i for verdict in verdicts for i in verdict['support_ids']))
        return {'question': question, 'variant': variant, 'answer': final_answer if accepted else '',
                'candidate_answer': prediction['answer'], 'abstained': not accepted,
                'claims': [v['claim'] for v in verdicts] if verdicts else [f['statement'] for f in prediction['facts']],
                'citation_ids': cited, 'evidence': [e.as_dict() for e in evidence], 'facets': facets,
                'verification': report, 'attempts': attempts, 'question_plan': plan,
                'provenance': {e.evidence_id: provenance.get(e.evidence_id) for e in evidence},
                'generation_format_error': prediction.get('format_error'),
                'retrieval': {'calls': len(graph_calls), 'graph_calls': graph_calls,
                              'generation_attempts': len(attempts), 'final_context_chars': sum(len(e.content) for e in evidence),
                              'expanded_without_regeneration': trace if len(attempts) == 1 and trace is not attempts[0]['retrieval'] else None},
                'latency_ms': round((perf_counter()-started)*1000, 2)}
