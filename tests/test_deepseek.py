import asyncio
from dataclasses import replace
import httpx
import pytest
from evidencechain.config import settings_from_env
from evidencechain.api_client import DeepSeekClient
from evidencechain.generation import DeepSeekGenerator
from evidencechain.schema import Evidence


def test_generation_and_graph_construction_contract(monkeypatch, tmp_path):
    sent = []
    async def post(self, url, **kwargs):
        sent.append(kwargs["json"])
        text = '{"answer":"Alderwick","claims":["The project launched in Alderwick."]}' if len(sent) == 1 else "entity tuple"
        return httpx.Response(200, json={"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                                         "usage": {"total_tokens": 12}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    settings = replace(settings_from_env(), llm_api_key="test", llm_model="deepseek-flash",
                       api_usage_log=str(tmp_path / "usage.jsonl"))
    async def run():
        result = await DeepSeekGenerator(settings).generate("Where?", [Evidence("e", "text", "doc")])
        graph = await DeepSeekClient(settings).complete("extract", system_prompt="tuple format", hashing_kv={})
        return result, graph
    result, graph = asyncio.run(run())
    assert result["answer"] == "Alderwick" and graph == "entity tuple"
    assert sent[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in sent[1]
    assert sent[0]["thinking"]["type"] == "disabled"
    assert len((tmp_path / "usage.jsonl").read_text().splitlines()) == 2


def test_missing_key():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        DeepSeekClient(replace(settings_from_env(), llm_api_key=""))


@pytest.mark.parametrize("purpose,expected_temperature", [("retrieval", 0.2), ("generation", 0)])
def test_truncated_completion_retries_with_larger_budget(monkeypatch, purpose, expected_temperature):
    limits = []
    temperatures = []
    async def post(self, url, **kwargs):
        limits.append(kwargs["json"]["max_tokens"])
        temperatures.append(kwargs["json"]["temperature"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "partial" if len(limits) == 1 else "complete"},
            "finish_reason": "length" if len(limits) == 1 else "stop"}]}, request=httpx.Request("POST", url))
    async def no_sleep(delay):
        pass
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    settings = replace(settings_from_env(), llm_api_key="test", api_usage_log="")
    assert asyncio.run(DeepSeekClient(settings).complete("extract", purpose=purpose)) == "complete"
    assert limits == [8192, 16384]
    assert temperatures == [0, expected_temperature]
