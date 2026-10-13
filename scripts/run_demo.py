#!/usr/bin/env python3
"""Offline smoke or real LightRAG CLI. PYTHONPATH not needed after pip install -e ."""
import argparse
import asyncio
import json
from pathlib import Path

from evidencechain.config import settings_from_env
from evidencechain.factory import make_chain
from evidencechain.pipeline import VARIANTS


def read_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("ingest", "ask"))
    p.add_argument("--backend", choices=("demo", "lightrag"), default="demo")
    p.add_argument("--docs", default="data/demo/documents.jsonl")
    p.add_argument("--question", default="星桥项目于哪一年在什么城市启动？")
    p.add_argument("--variant", choices=VARIANTS, default="full")
    p.add_argument("--verifier", choices=("lexical", "nli"), default=None)
    args = p.parse_args()
    settings = settings_from_env()
    chain = await make_chain(settings, backend=args.backend, verifier=args.verifier)
    try:
        if args.backend == "demo" or args.command == "ingest":
            await chain.retriever.add(read_jsonl(args.docs))
        if args.command == "ingest":
            print("Ingested. In real mode, persistent store located at", settings.working_dir)
        else:
            output = await chain.ask(args.question, variant=args.variant)
            print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        await chain.retriever.close()


if __name__ == "__main__":
    asyncio.run(main())
