"""
Qdrant 向量数据库操作模块（Vector Store）。

所有对 Qdrant 的读写操作封装于此，对上层（indexer / router）屏蔽底层细节。

设计原则：
  - 使用单一 Collection（vago_articles）存储全量用户数据；
  - 通过 payload 字段 user_uuid 严格隔离用户数据，
    所有查询均携带 user_uuid 过滤器，杜绝跨用户数据泄露；
  - 每个文本块（chunk）对应一个 Qdrant Point，
    Point ID 由 article_id + chunk_index 确定性生成（UUID5），
    支持幂等 upsert（重复导入同一攻略不会产生重复向量）。
"""

import uuid
from datetime import datetime, timezone

from qdrant_client import AsyncQdrantClient
from qdrant_client import models as qm

from app.config import settings
from app.models.schemas import SearchResultItem

# ─── 客户端单例 ───────────────────────────────────────────────────────────────

_qdrant_client: AsyncQdrantClient | None = None


def _get_client() -> AsyncQdrantClient:
    """
    懒加载并返回 AsyncQdrantClient 单例。

    延迟初始化避免在模块导入时建立连接，
    方便在测试环境中替换或 Mock 客户端。

    返回:
        已连接到配置 Host/Port 的 AsyncQdrantClient 实例。
    """
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
    return _qdrant_client


# ─── Collection 初始化 ────────────────────────────────────────────────────────

async def init_collection() -> None:
    """
    确保 Qdrant Collection 存在，若不存在则自动创建。

    应在应用启动时（lifespan）调用一次。
    Collection 使用 COSINE 距离度量，与 OpenAI text-embedding-3-small 匹配。
    向量维度由配置 openai_embedding_dim 决定（默认 1536）。

    幂等操作：若 Collection 已存在则跳过创建，不会抛出异常。
    """
    client = _get_client()
    try:
        await client.get_collection(settings.qdrant_collection)
    except Exception:
        # Collection 不存在，创建之
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qm.VectorParams(
                size=settings.openai_embedding_dim,
                distance=qm.Distance.COSINE,
            ),
        )


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _make_point_id(article_id: str, chunk_index: int) -> str:
    """
    生成确定性 UUID，作为 Qdrant Point 的唯一标识符。

    使用 UUID5（SHA-1 命名空间哈希）将 article_id + chunk_index
    映射到固定 UUID，保证同一 chunk 的 ID 在重复导入时不变，
    从而实现幂等 upsert（覆盖更新而非重复插入）。

    参数:
        article_id:   攻略的 UUID 字符串。
        chunk_index:  文本块的顺序索引（从 0 开始）。

    返回:
        UUID 字符串，格式如 "550e8400-e29b-41d4-a716-446655440000"。
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{article_id}:{chunk_index}"))


def _build_filter(user_uuid: str, article_id: str | None = None) -> qm.Filter:
    """
    构造 Qdrant 过滤器，始终携带 user_uuid 隔离条件。

    参数:
        user_uuid:  必选，确保数据在用户维度隔离。
        article_id: 可选，进一步过滤到单篇攻略。

    返回:
        Qdrant Filter 对象，用于 search / delete 等操作。
    """
    conditions: list[qm.FieldCondition] = [
        qm.FieldCondition(key="user_uuid", match=qm.MatchValue(value=user_uuid))
    ]
    if article_id is not None:
        conditions.append(
            qm.FieldCondition(key="article_id", match=qm.MatchValue(value=article_id))
        )
    return qm.Filter(must=conditions)


# ─── 向量库的核心 CRUD ────────────────────────────────────────────────────────────────

async def upsert_article_chunks(
    user_uuid: str,
    article_id: str,
    title: str,
    chunks: list[str],
    embeddings: list[list[float]],
    destinations: list[str],
    categories: list[str],
    source_url: str | None = None,
) -> int:
    """
    将一篇攻略的所有文本块（chunks）批量 upsert 到 Qdrant。

    每个 chunk 对应一个 Point，Point ID 由 article_id + chunk_index 确定性生成，
    支持重复导入时覆盖更新（幂等）。Payload 中存储检索和展示所需的全部元数据。

    参数:
        user_uuid:    所属用户 UUID，存入 payload 用于查询隔离。
        article_id:   攻略 UUID。
        title:        攻略标题。
        chunks:       文本块列表（已分块，顺序与 embeddings 一一对应）。
        embeddings:   对应的 embedding 向量列表。
        destinations: 目的地标签列表。
        categories:   分类标签列表（ArticleCategory 枚举值字符串）。
        source_url:   原始链接（可为 None）。

    返回:
        实际 upsert 的 Point 数量（等于 len(chunks)）。

    异常:
        qdrant_client 底层异常，由调用方处理。
    """
    assert len(chunks) == len(embeddings), "chunks 与 embeddings 长度必须一致"

    client = _get_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    points = [
        qm.PointStruct(
            id=_make_point_id(article_id, idx),
            vector=embedding,
            payload={
                "user_uuid": user_uuid,
                "article_id": article_id,
                "chunk_index": idx,
                "chunk_text": chunk,
                "title": title,
                "source_url": source_url or "",
                "destinations": destinations,
                "categories": categories,
                "indexed_at": now_iso,
            },
        )
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    await client.upsert(
        collection_name=settings.qdrant_collection,
        points=points,
        wait=True,  # 等待写入持久化完成再返回
    )

    return len(points)


async def search_by_user(
    user_uuid: str,
    query_embedding: list[float],
    top_k: int = 5,
    score_threshold: float = 0.60,
) -> list[SearchResultItem]:
    """
    在指定用户的私有攻略库中执行向量相似度检索。

    仅返回属于 user_uuid 的 Point（通过 payload filter 实现），
    确保不同用户之间的攻略数据严格隔离。

    参数:
        user_uuid:       检索范围限定为该用户。
        query_embedding: 查询文本的 embedding 向量（由 embedder.embed_query 生成）。
        top_k:           返回最相关结果的数量上限。
        score_threshold: 余弦相似度阈值，低于此值的结果被过滤，默认 0.60。

    返回:
        SearchResultItem 列表，按相似度得分降序排列。
        若无符合阈值的结果，返回空列表。
    """
    client = _get_client()

    hits = await client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_embedding,
        query_filter=_build_filter(user_uuid),
        limit=top_k,
        score_threshold=score_threshold,
        with_payload=True,
    )

    results: list[SearchResultItem] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            SearchResultItem(
                article_id=payload.get("article_id", ""),
                chunk_index=payload.get("chunk_index", 0),
                chunk_text=payload.get("chunk_text", ""),
                title=payload.get("title", ""),
                destinations=payload.get("destinations", []),
                categories=payload.get("categories", []),
                score=round(hit.score, 4),
            )
        )

    return results


async def delete_article_chunks(user_uuid: str, article_id: str) -> int:
    """
    删除指定用户的指定攻略在向量库中的全部 Point。

    通过 FilterSelector 按 user_uuid + article_id 批量删除，
    无需预先获取 Point ID 列表，避免两次网络往返。
    同时携带 user_uuid 条件，防止误删其他用户的同 article_id 数据。

    参数:
        user_uuid:  所属用户 UUID（安全隔离）。
        article_id: 待删除的攻略 UUID。

    返回:
        删除的 Point 数量（Qdrant 返回的操作结果中读取）。
        若该攻略不存在于向量库，返回 0。
    """
    client = _get_client()

    # 先查询数量（用于返回值）
    count_result = await client.count(
        collection_name=settings.qdrant_collection,
        count_filter=_build_filter(user_uuid, article_id),
        exact=True,
    )
    count = count_result.count

    if count == 0:
        return 0

    await client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=qm.FilterSelector(
            filter=_build_filter(user_uuid, article_id)
        ),
        wait=True,
    )

    return count


async def count_user_articles(user_uuid: str) -> int:
    """
    统计指定用户在向量库中的文本块总数。

    主要用于调试和运营监控，确认用户攻略库是否已成功入库。

    参数:
        user_uuid: 目标用户 UUID。

    返回:
        该用户在向量库中的 Point（文本块）总数量。
    """
    client = _get_client()
    result = await client.count(
        collection_name=settings.qdrant_collection,
        count_filter=_build_filter(user_uuid),
        exact=True,
    )
    return result.count
