"""验证向量查询在发送到 Qdrant 前校验维度。"""

import asyncio

import pytest

from app.config import settings
from app.services import embedder


def test_embed_query_rejects_dimension_mismatch(monkeypatch) -> None:
    """测试：Embedding Provider 返回维度不匹配时，不应继续发送 Qdrant 检索。"""
    class FakeEmbeddings:
        async def create(self, **_kwargs):
            item = type("EmbeddingItem", (), {"embedding": [0.1] * 1024})()
            return type("EmbeddingResponse", (), {"data": [item]})()

    class FakeClient:
        embeddings = FakeEmbeddings()

    monkeypatch.setattr(settings, "embedding_dim", 1536)
    monkeypatch.setattr(embedder, "_get_client", lambda: FakeClient())

    with pytest.raises(ValueError, match="Embedding 维度不匹配"):
        asyncio.run(embedder.embed_query("当前日程"))
