import asyncio
from evidencechain.factory import make_chain
from evidencechain.config import settings_from_env


def test_demo_end_to_end():
    async def run():
        chain = await make_chain(settings_from_env(), "demo", "lexical")
        await chain.retriever.add([{"id": "d", "text": "星桥项目于2023年在南京启动。"}])
        output = await chain.ask("星桥项目在哪启动？", "full")
        await chain.retriever.close()
        return output
    out = asyncio.run(run())
    assert out["answer"]
    assert out["verification"]["accepted"]
    assert out["evidence"][0]["source"] == "d"
