"""Opt-in corpus-only corrective QA with explicit parent-corpus and reranker paths."""
import argparse
import asyncio
import json

from evidencechain.config import settings_from_env
from evidencechain.factory import make_corrective_chain


async def run(args):
    chain = await make_corrective_chain(settings_from_env(), args.corpus, args.reranker)
    try:
        print(json.dumps(await chain.ask(args.question, args.variant), ensure_ascii=False, indent=2))
    finally:
        await chain.retriever.graph.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('question')
    parser.add_argument('--corpus', required=True)
    parser.add_argument('--reranker', required=True)
    parser.add_argument('--variant', choices=['context_only', 'verify', 'full'], default='full')
    asyncio.run(run(parser.parse_args()))
