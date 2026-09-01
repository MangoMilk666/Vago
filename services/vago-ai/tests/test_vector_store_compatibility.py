"""验证 KnowledgeSource 与 legacy article payload 的向量兼容边界。"""

import asyncio

from app.services import vector_store


def test_document_upsert_cleans_old_chunks_and_keeps_legacy_payload(monkeypatch):
    """测试：重建资料时应先删除旧 chunks，并为 Java 兼容窗口保留 article_id。"""
    deleted: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self) -> None:
            self.points = []

        async def upsert(self, *, collection_name, points, wait) -> None:
            assert collection_name
            assert wait is True
            self.points = points

    fake_client = FakeClient()

    async def fake_delete_document_chunks(user_uuid: str, source_uuid: str) -> int:
        deleted.append((user_uuid, source_uuid))
        return 3

    monkeypatch.setattr(vector_store, "delete_document_chunks", fake_delete_document_chunks)
    monkeypatch.setattr(vector_store, "_get_client", lambda: fake_client)

    async def scenario() -> None:
        written = await vector_store.upsert_document_chunks(
            user_uuid="source-user",
            source_uuid="source-uuid",
            title="旅行笔记",
            chunks=["第一段", "第二段"],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            destinations=["京都"],
            categories=["TIPS"],
        )
        assert written == 2

    asyncio.run(scenario())

    assert deleted == [("source-user", "source-uuid")]
    assert [point.payload["source_uuid"] for point in fake_client.points] == ["source-uuid", "source-uuid"]
    assert [point.payload["article_id"] for point in fake_client.points] == ["source-uuid", "source-uuid"]
