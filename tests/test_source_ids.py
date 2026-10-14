import asyncio
from types import SimpleNamespace
from evidencechain.config import settings_from_env
from evidencechain.retrievers import LightRAGRetriever


def test_nested_source_ids_do_not_collide_after_basename_normalization(monkeypatch):
    captured = []

    class FakeRag:
        async def ainsert(self, body, file_paths):
            captured.append(file_paths)

        async def aquery_data(self, query, param):
            return {"data": {"chunks": [{"content": "one", "file_path": captured[0]}]}}

    monkeypatch.setitem(__import__("sys").modules, "lightrag",
                        SimpleNamespace(QueryParam=lambda **kwargs: kwargs))
    async def run():
        retriever = LightRAGRetriever(settings_from_env())
        retriever.rag = FakeRag()
        await retriever.add([{"id": "group/a/doc", "text": "one"},
                             {"id": "group/b/doc", "text": "two"}])
        evidence = await retriever.search("one")
        assert evidence[0].source == "group/a/doc"
    asyncio.run(run())
    assert len(set(captured)) == 2
    assert all("/" not in source and "\\" not in source for source in captured)
