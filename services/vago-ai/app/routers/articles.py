"""
攻略库管理路由（Articles Router）。

提供面向 Java vago-backend 的攻略 RAG 管理接口：
  - POST   /api/v1/articles/ingest          同步入库（清洗 → 分块 → Embedding → Qdrant）
  - POST   /api/v1/articles/search          向量语义检索（供 AI 行程规划链路调用）
  - DELETE /api/v1/articles/{article_id}    从向量库删除指定攻略的全部 chunk

所有接口均同步执行（await），Java 侧可直接阻塞等待结果。
"""

import logging

from fastapi import APIRouter, HTTPException, Path, Query

from app.models.schemas import (
    DeleteArticleResponse,
    IngestRequest,
    IngestResponse,
    ArticleStatus,
    SearchRequest,
    SearchResponse,
)
from app.services.embedder import embed_query
from app.services.indexer import index_article
from app.services.vector_store import (
    count_user_articles,
    delete_article_chunks,
    search_by_user,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="攻略入库（RAG 向量化）",
    description=(
        "接收 Java 侧提交的攻略原始文本，执行完整 RAG 管道：\n"
        "文本清洗 → 元数据提取 → 语义分块 → Embedding → 写入 Qdrant。\n"
        "同步返回处理结果，Java 侧依据 status 字段更新 article 状态。\n"
        "支持幂等调用：相同 article_id 重复提交时会覆盖更新向量数据。"
    ),
)
async def ingest_article(request: IngestRequest) -> IngestResponse:
    """
    攻略向量化入库接口。

    接收来自 Java vago-backend 的攻略数据，调用 indexer.index_article
    执行完整 RAG 管道，同步返回 IngestResponse。

    本接口不会抛出 4xx/5xx（管道内部错误以 status=FAILED 形式返回），
    便于 Java 侧统一处理而无需捕获 HTTP 异常。

    参数:
        request: IngestRequest，包含 article_id、user_uuid、raw_content 等。

    返回:
        IngestResponse，status 为 INDEXED 或 FAILED。
    """
    logger.info(
        "收到入库请求 article_id=%s user=%s content_len=%d",
        request.article_id, request.user_uuid, len(request.raw_content),
    )
    return await index_article(request)


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="攻略 RAG 语义检索",
    description=(
        "将查询文本向量化后，在指定用户的私有攻略库中执行相似度检索，\n"
        "返回最相关的 top_k 个文本块，供 AI 行程规划的 RAG Prompt 构建使用。\n"
        "通过 user_uuid 字段严格隔离用户数据，不会返回其他用户的攻略内容。"
    ),
)
async def search_articles(request: SearchRequest) -> SearchResponse:
    """
    RAG 向量语义检索接口。

    将查询问题 embed_query 后，在 Qdrant 中检索 user_uuid 命名空间的文本块，
    过滤低于 score_threshold 的结果，按相似度降序返回。

    参数:
        request: SearchRequest，包含 query、user_uuid、top_k、score_threshold。

    返回:
        SearchResponse，包含命中的文本块列表及总数。

    异常:
        503 — Qdrant 或 OpenAI 服务不可用时抛出。
    """
    logger.info(
        "收到检索请求 user=%s query='%s' top_k=%d threshold=%.2f",
        request.user_uuid, request.query[:50], request.top_k, request.score_threshold,
    )
    try:
        query_embedding = await embed_query(request.query)
        results = await search_by_user(
            user_uuid=request.user_uuid,
            query_embedding=query_embedding,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )
    except Exception as exc:
        logger.error("检索失败 error=%s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"检索服务暂时不可用：{exc}") from exc

    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
    )


@router.delete(
    "/{article_id}",
    response_model=DeleteArticleResponse,
    summary="从向量库删除攻略",
    description=(
        "删除指定 article_id 在 Qdrant 中的全部文本块（chunk）。\n"
        "通常在 Java 侧软删除攻略记录后调用，保持向量库与 MySQL 数据一致。\n"
        "操作携带 user_uuid 安全校验，防止跨用户误删。"
    ),
)
async def delete_article(
    article_id: str = Path(..., description="待删除的攻略 UUID"),
    user_uuid: str = Query(..., description="所属用户 UUID，用于安全校验"),
) -> DeleteArticleResponse:
    """
    向量库攻略删除接口。

    通过 FilterSelector 按 user_uuid + article_id 批量删除 Qdrant Point，
    无需预先查询 Point ID 列表，单次网络请求完成操作。

    参数:
        article_id: URL 路径参数，目标攻略 UUID。
        user_uuid:  Query 参数，所属用户 UUID（安全隔离）。

    返回:
        DeleteArticleResponse，包含实际删除的 Point 数量。

    异常:
        503 — Qdrant 服务不可用时抛出。
    """
    logger.info("收到删除请求 article_id=%s user=%s", article_id, user_uuid)
    try:
        deleted_count = await delete_article_chunks(
            user_uuid=user_uuid,
            article_id=article_id,
        )
    except Exception as exc:
        logger.error("删除失败 article_id=%s error=%s", article_id, exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"向量库服务暂时不可用：{exc}") from exc

    msg = (
        f"成功删除 {deleted_count} 个文本块"
        if deleted_count > 0
        else "向量库中未找到该攻略，可能尚未入库或已被删除"
    )
    logger.info("删除完成 article_id=%s deleted=%d", article_id, deleted_count)

    return DeleteArticleResponse(
        article_id=article_id,
        deleted_count=deleted_count,
        message=msg,
    )


@router.get(
    "/stats/{user_uuid}",
    summary="查询用户攻略库统计",
    description="返回指定用户在向量库中的文本块（chunk）总数，用于调试和运营监控。",
)
async def get_user_stats(
    user_uuid: str = Path(..., description="目标用户 UUID"),
) -> dict:
    """
    用户攻略库统计接口。

    统计指定用户在 Qdrant 中存储的文本块总数，
    用于验证入库是否成功或排查数据异常。

    参数:
        user_uuid: 目标用户 UUID。

    返回:
        包含 user_uuid 和 total_chunks 的字典。
    """
    try:
        total = await count_user_articles(user_uuid)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"向量库服务暂时不可用：{exc}") from exc

    return {"user_uuid": user_uuid, "total_chunks": total}
