"""Run the opt-in bounded joint-evidence strategy with configured real models."""
import argparse
import asyncio
import json

from evidencechain.config import settings_from_env
from evidencechain.factory import make_grounded_chain


async def run(args):
    chain = await make_grounded_chain(settings_from_env())
    try:
        print(json.dumps(await chain.ask(args.question, args.variant), ensure_ascii=False, indent=2))
    finally:
        await chain.retriever.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--variant", choices=["baseline", "adaptive", "verify", "full"], default="full")
    asyncio.run(run(parser.parse_args()))
