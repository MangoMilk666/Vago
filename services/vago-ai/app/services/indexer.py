"""
RAG 管道编排模块（Indexer）。

作为各子服务（cleaner / chunker / embedder / metadata_extractor / vector_store）
的编排层，将个人知识资料从原始文本到向量入库的全流程串联成单一调用入口。

完整管道（顺序执行）：
  1. 内容长度校验（≤ MAX_CONTENT_CHARS）
  2. 文本清洗（strip HTML / emoji / 广告词 / 空白规范化）
  3. 元数据提取（目的地 + 分类标签）
  4. 语义分块（tiktoken 计数 + 中文句边界切割）
  5. Embedding 向量化（OpenAI text-embedding-3-small，批量）
  6. 写入 Qdrant（按 user_uuid 隔离，幂等 upsert）

设计原则：
  - 单一职责：indexer 只负责编排，不包含具体实现；
  - 失败友好：任何步骤异常均被捕获，返回 FAILED 状态而非抛出 HTTP 错误；
  - 兼容窗口：旧 Java articles API 通过 index_article wrapper 继续调用本模块；
  - 可观察性：通过 logger 记录各步骤耗时和关键指标，便于生产排查。
"""

import logging
import time

from app.config import settings
from app.models.schemas import (
    ArticleCategory,
    ArticleStatus,
    IndexDocumentRequest,
    IndexDocumentResponse,
    IngestRequest,
    IngestResponse,
)
from app.services.cleaner import clean_text
from app.services.chunker import chunk_text, count_tokens
from app.services.embedder import embed_texts
from app.services.metadata_extractor import extract_metadata
from app.services.vector_store import upsert_document_chunks

logger = logging.getLogger(__name__)


async def index_document(request: IndexDocumentRequest) -> IndexDocumentResponse:
    """
    RAG 文档入库主入口：执行完整的向量化管道并返回结构化结果。

    调用方传入与具体领域实体无关的 IndexDocumentRequest，
    本函数负责编排全部子步骤，最终返回 IndexDocumentResponse。

    成功时返回 status=INDEXED、chunk_count > 0；
    任何步骤失败时返回 status=FAILED、message 包含具体错误原因，
    不会向上抛出异常（调用方只需判断 status 字段）。

    参数:
        request: 包含 source_uuid、user_uuid、raw_content 等字段的入库请求。

    返回:
        IndexDocumentResponse，包含索引状态、分块数、提取的元数据和处理消息。
    """
    t_start = time.monotonic()
    source_uuid = request.source_uuid

    try:
        # ── Step 1：内容长度校验 ────────────────────────────────────────────
        char_count = len(request.raw_content)
        if char_count > settings.max_content_chars:
            return _fail(
                source_uuid,
                f"内容过长：{char_count} 字符，上限 {settings.max_content_chars} 字符，请分批导入",
            )

        logger.info(
            "[indexer] 开始索引 source_uuid=%s user=%s chars=%d",
            source_uuid, request.user_uuid, char_count,
        )

        # ── Step 2：文本清洗 ────────────────────────────────────────────────
        t = time.monotonic()
        cleaned = clean_text(request.raw_content)
        if not cleaned:
            return _fail(source_uuid, "清洗后内容为空，请检查原始文本是否有效")
        logger.debug("[indexer] 清洗完成 %.2fs chars=%d→%d", time.monotonic() - t, char_count, len(cleaned))

        # ── Step 3：元数据提取（目的地 + 分类）─────────────────────────────
        t = time.monotonic()
        metadata = extract_metadata(cleaned, request.title)

        # 若前端已预标注目的地则优先使用，否则用 AI 提取的结果
        destinations: list[str] = request.destinations or metadata["destinations"]
        categories: list[ArticleCategory] = metadata["categories"]
        logger.debug(
            "[indexer] 元数据提取完成 %.2fs destinations=%s categories=%s",
            time.monotonic() - t, destinations, [c.value for c in categories],
        )

        # ── Step 4：语义分块 ────────────────────────────────────────────────
        t = time.monotonic()
        chunks = chunk_text(
            cleaned,
            chunk_size=settings.chunk_size_tokens,
            chunk_overlap=settings.chunk_overlap_tokens,
        )
        if not chunks:
            return _fail(source_uuid, "分块结果为空，原始内容可能过短或全为无效字符")
        logger.debug(
            "[indexer] 分块完成 %.2fs chunks=%d avg_tokens=%.0f",
            time.monotonic() - t,
            len(chunks),
            sum(count_tokens(c) for c in chunks) / len(chunks),
        )

        # ── Step 5：Embedding 向量化 ────────────────────────────────────────
        t = time.monotonic()
        embeddings = await embed_texts(chunks)
        logger.debug(
            "[indexer] Embedding 完成 %.2fs chunks=%d dim=%d",
            time.monotonic() - t, len(embeddings),
            len(embeddings[0]) if embeddings else 0,
        )

        # ── Step 6：写入 Qdrant ─────────────────────────────────────────────
        t = time.monotonic()
        upserted = await upsert_document_chunks(
            user_uuid=request.user_uuid,
            source_uuid=source_uuid,
            title=request.title,
            chunks=chunks,
            embeddings=embeddings,
            destinations=destinations,
            categories=[c.value for c in categories],
            source_url=request.source_url,
        )
        logger.debug("[indexer] Qdrant upsert 完成 %.2fs points=%d", time.monotonic() - t, upserted)

        elapsed = time.monotonic() - t_start
        logger.info(
            "[indexer] 索引成功 source_uuid=%s chunks=%d elapsed=%.2fs",
            source_uuid, upserted, elapsed,
        )

        return IndexDocumentResponse(
            source_uuid=source_uuid,
            status=ArticleStatus.INDEXED,
            chunk_count=upserted,
            destinations=destinations,
            categories=[c.value for c in categories],
            message=f"成功索引 {upserted} 个文本块，耗时 {elapsed:.1f}s",
        )

    except Exception as exc:
        elapsed = time.monotonic() - t_start
        logger.error(
            "[indexer] 索引失败 source_uuid=%s elapsed=%.2fs error=%s",
            source_uuid, elapsed, exc, exc_info=True,
        )
        return _fail(source_uuid, f"索引异常：{type(exc).__name__}: {exc}")


def _fail(source_uuid: str, message: str) -> IndexDocumentResponse:
    """
    构造 FAILED 状态的 IndexDocumentResponse，统一失败响应格式。

    参数:
        source_uuid: 失败的知识来源 UUID。
        message:     人类可读的失败原因，供调用方记录日志和展示给用户。

    返回:
        status=FAILED 的 IndexDocumentResponse，chunk_count=0，列表字段均为空。
    """
    logger.warning("[indexer] 返回失败响应 source_uuid=%s reason=%s", source_uuid, message)
    return IndexDocumentResponse(
        source_uuid=source_uuid,
        status=ArticleStatus.FAILED,
        chunk_count=0,
        destinations=[],
        categories=[],
        message=message,
    )


async def index_article(request: IngestRequest) -> IngestResponse:
    """兼容 Java articles API 的旧入口，内部委托给通用 document indexing。"""
    response = await index_document(
        IndexDocumentRequest(
            source_uuid=request.article_id,
            user_uuid=request.user_uuid,
            title=request.title,
            source_url=request.source_url,
            raw_content=request.raw_content,
            destinations=request.destinations,
        )
    )
    return IngestResponse(
        article_id=response.source_uuid,
        status=response.status,
        chunk_count=response.chunk_count,
        destinations=response.destinations,
        categories=response.categories,
        message=response.message,
    )
