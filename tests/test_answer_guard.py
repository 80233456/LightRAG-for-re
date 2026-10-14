import asyncio
from evidencechain.answer_guard import answer_anchored_in_claims
from evidencechain.pipeline import EvidenceChain
from evidencechain.retrievers import DemoRetriever
from evidencechain.verifier import EvidenceVerifier, LexicalScorer


def test_correct_short_answers_and_combined_date_location():
    claim = '项目星桥于2023年在南京启动。'
    assert answer_anchored_in_claims('南京', [claim])
    assert answer_anchored_in_claims('2023年，南京', [claim])
    assert answer_anchored_in_claims('2023, 南京', [claim])


def test_wrong_answer_and_negative_mentions_blocked():
    assert not answer_anchored_in_claims('北京', ['项目星桥于2023年在南京启动。'])
    assert not answer_anchored_in_claims('Beijing', ['The project was not in Beijing, but in Nanjing.'])
    assert answer_anchored_in_claims('Nanjing', ['The project was not in Beijing, but in Nanjing.'])
    assert not answer_anchored_in_claims('北京', ['星桥项目不是在北京启动，而是在南京启动。'])
    assert not answer_anchored_in_claims('North', ['Northampton is the answer.'])
    assert not answer_anchored_in_claims('2023', ['The launch was not in 2023.'])
    assert answer_anchored_in_claims('2023', ['The project launched in 2023年.'])


class WrongAnswerGenerator:
    async def generate(self, question, evidence):
        return {'answer': '北京', 'claims': ['星桥项目于2023年在南京启动。']}


def test_end_to_end_rejects_answer_inconsistent_with_grounded_claim():
    async def run():
        retriever = DemoRetriever([{'id': 'doc', 'text': '星桥项目于2023年在南京启动。'}])
        chain = EvidenceChain(retriever, WrongAnswerGenerator(), EvidenceVerifier(LexicalScorer()))
        return await chain.ask('星桥项目在哪里启动？', 'verify')
    output = asyncio.run(run())
    assert output['answer'] == ''
    assert output['abstained']
    assert output['verification']['reason'] == 'answer-claim-mismatch'
    assert output['verification']['answer_claim_consistent'] is False
    assert output['verification']['verdicts'][0]['label'] == 'supported'
