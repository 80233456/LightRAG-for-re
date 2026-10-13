#!/usr/bin/env python3
"""Check local Ollama without leaking API credentials."""
import argparse
import json
import httpx
from evidencechain.config import settings_from_env


def main():
    s = settings_from_env()
    print("Host:", s.host)
    print("LLM:", s.llm_model, "Embedding:", s.embedding_model)
    try:
        r = httpx.get(s.host.rstrip("/") + "/api/tags", timeout=8)
        r.raise_for_status()
        names = [m.get("name") for m in r.json().get("models", [])]
        print("Available local models:", json.dumps(names, ensure_ascii=False))
        for model in (s.llm_model, s.embedding_model):
            print("OK" if any(str(x).startswith(model) for x in names) else "MISSING", model)
    except Exception as e:
        print("Ollama unreachable:", type(e).__name__, str(e)[:160])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
