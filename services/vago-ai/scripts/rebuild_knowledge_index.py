import argparse
import asyncio

from qdrant_client import models as qm
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.knowledge.models import KnowledgeSource
from app.models.schemas import ArticleStatus, IndexDocumentRequest
from app.services.embedder import embed_query
from app.services.indexer import index_document
from app.services.vector_store import _get_client, _vector_size, verify_collection_dimension


async def rebuild(target_collection: str) -> None:
    """从 MySQL 原文重建新索引；调用方决定何时切换读取目标。"""
    if not settings.rag_enabled:
        raise RuntimeError("RAG_ENABLED 未开启，无法重建索引")
    if target_collection == settings.qdrant_collection:
        raise ValueError("目标 collection 必须与当前读取的 collection 不同")
    if not target_collection.strip() or "/" in target_collection:
        raise ValueError("请提供有效的新 collection 名称")

    # 先请求真实模型，确认它实际产生的维度，再创建 collection。
    embedding = await embed_query("Vago 知识索引维度检查")
    model_dim = len(embedding)
    client = _get_client()
    if await client.collection_exists(target_collection):
        info = await client.get_collection(target_collection)
        if _vector_size(info) != model_dim:
            raise ValueError(f"目标 collection {target_collection} 已存在，但维度不是 {model_dim}")
    else:
        await client.create_collection(
            collection_name=target_collection,
            vectors_config=qm.VectorParams(size=model_dim, distance=qm.Distance.COSINE),
        )

    with SessionLocal() as db:
        sources = db.scalars(
            select(KnowledgeSource).where(
                KnowledgeSource.deleted_at.is_(None),
                KnowledgeSource.parse_status == "READY",
                KnowledgeSource.content_text.is_not(None),
            )
        ).all()
        await verify_collection_dimension(model_dim, target_collection)
        indexed = 0
        total_points = 0
        for source in sources:
            response = await index_document(IndexDocumentRequest(
                    source_uuid=source.uuid,
                    user_uuid=source.user_uuid,
                    title=source.title,
                    source_url=source.origin_url,
                    raw_content=source.content_text,
                    destinations=[source.destination] if source.destination else None,
            ), collection_name=target_collection)
            if response.status != ArticleStatus.INDEXED:
                raise RuntimeError(f"知识源 {source.uuid} 重建失败：{response.message}")
            indexed += 1
            total_points += response.chunk_count

    actual_points = (await client.count(collection_name=target_collection, exact=True)).count
    if actual_points != total_points:
        raise RuntimeError(f"目标索引数量不一致：预期 {total_points}，实际 {actual_points}")
    print(f"重建完成：{indexed} 份知识源、{actual_points} 个文本块；读取目标为 {target_collection}")


def main() -> None:
    """从命令行读取新 collection 名称，避免误覆盖当前索引。"""
    parser = argparse.ArgumentParser(description="重建个人知识向量索引到新的 Qdrant collection")
    parser.add_argument("--target-collection", required=True)
    args = parser.parse_args()
    asyncio.run(rebuild(args.target_collection))


if __name__ == "__main__":
    main()
