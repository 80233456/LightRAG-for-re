"""Optional DeepSeek API adapter used by graph extraction and QA generation.

API keys are loaded from the user's runtime environment, never committed.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import time
import httpx


class IncompleteCompletion(ValueError):
    pass


class DeepSeekClient:
    def __init__(self, settings):
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for DeepSeek")
        self.settings = settings

    async def complete(self, prompt, system_prompt=None, history_messages=None,
                       purpose="retrieval", response_format=None, **kwargs):
        messages = list(history_messages or [])
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.settings.llm_model, "messages": messages,
                "stream": False, "temperature": 0, "max_tokens": 8192,
                "thinking": {"type": "disabled"}}
        if response_format or kwargs.get("keyword_extraction"):
            body["response_format"] = response_format or {"type": "json_object"}
        started = time.perf_counter()
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
                    response = await client.post(
                        self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                        headers={"Authorization": "Bearer " + self.settings.llm_api_key},
                        json=body)
                if response.status_code in (408, 429) or response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code >= 400:
                    raise ValueError(f"DeepSeek HTTP {response.status_code}; check provider account/configuration")
                data = response.json()
                choice = data["choices"][0]
                content = choice["message"].get("content")
                incomplete = choice.get("finish_reason") == "length" or not content
                if self.settings.api_usage_log:
                    path = Path(self.settings.api_usage_log)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    record = {"time": time.time(), "purpose": purpose,
                              "stage": os.getenv("EXPERIMENT_STAGE", "unspecified"),
                              "model": data.get("model"), "usage": data.get("usage"),
                              "completion_status": "incomplete" if incomplete else "complete",
                              "finish_reason": choice.get("finish_reason"),
                              "attempts": attempt + 1,
                              "latency_ms": round((time.perf_counter()-started)*1000, 2)}
                    with path.open("a", encoding="utf-8") as out:
                        out.write(json.dumps(record) + "\n")
                if incomplete:
                    if purpose != "generation":
                        body["temperature"] = 0.2
                        if attempt == 0:
                            messages.insert(0, {"role": "system", "content":
                                "Produce compact output. Do not repeat identical entries."})
                    if choice.get("finish_reason") == "length":
                        body["max_tokens"] = min(body["max_tokens"] * 2, 32768)
                    raise IncompleteCompletion("DeepSeek returned empty or truncated content")
                return content
            except (httpx.TimeoutException, httpx.NetworkError,
                    httpx.HTTPStatusError, IncompleteCompletion):
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** (attempt + 1))
        raise RuntimeError("unreachable")
