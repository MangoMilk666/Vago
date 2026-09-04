"""KnowledgeSource 与可选语义索引能力之间的应用层适配。"""

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.knowledge.models import KnowledgeSource
from app.knowledge.schemas import IndexStatus, ParseStatus
from app.models.schemas import ArticleStatus, IndexDocumentRequest
from app.services.indexer import index_document
from app.services.vector_store import delete_document_chunks
from app.travel.models import utc_now_naive

logger = logging.getLogger(__name__)


def _mark_source_index_failed(source_uuid: str, user_uuid: str) -> None:
    """将后台任务的未预期异常回写为可供客户端查询的失败状态。"""
    with SessionLocal() as db:
        source = db.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.uuid == source_uuid,
                KnowledgeSource.deleted_at.is_(None),
            )
        )
        # 分支条件：资料已删除或不再属于该任务用户时，不覆盖其现有状态。
        if source is None or source.user_uuid != user_uuid:
            return
        source.index_status = IndexStatus.FAILED.value
        source.index_error = "语义索引服务暂不可用，请稍后重试"
        source.updated_at = utc_now_naive()
        db.commit()


async def index_source_background(source_uuid: str, user_uuid: str) -> None:
    """后台执行知识源索引；Knowledge CRUD 本身不依赖本函数。"""
    if not settings.rag_enabled:
        logger.info("RAG 已关闭，跳过知识源索引 source=%s", source_uuid)
        return

    try:
        with SessionLocal() as db:
            source = db.scalar(
                select(KnowledgeSource).where(
                    KnowledgeSource.uuid == source_uuid,
                    KnowledgeSource.deleted_at.is_(None),
                )
            )
            # 分支条件：后台任务执行前资料被删除、转移或未解析完成时，不写入向量库。
            if (
                source is None
                or source.user_uuid != user_uuid
                or source.parse_status != ParseStatus.READY.value
                or not source.content_text
            ):
                return

            source.index_status = IndexStatus.INDEXING.value
            source.index_error = None
            source.updated_at = utc_now_naive()
            db.commit()

            response = await index_document(
                IndexDocumentRequest(
                    source_uuid=source.uuid,
                    user_uuid=source.user_uuid,
                    title=source.title,
                    source_url=source.origin_url,
                    raw_content=source.content_text,
                    destinations=[source.destination] if source.destination else None,
                )
            )

            source = db.scalar(
                select(KnowledgeSource).where(
                    KnowledgeSource.uuid == source_uuid,
                    KnowledgeSource.deleted_at.is_(None),
                )
            )
            # 分支条件：索引执行期间资料被删除时，避免把已删除资料重新标记为可检索。
            if source is None:
                return
            if response.status == ArticleStatus.INDEXED:
                source.index_status = IndexStatus.INDEXED.value
                source.index_error = None
            else:
                source.index_status = IndexStatus.FAILED.value
                source.index_error = response.message[:1000]
            source.updated_at = utc_now_naive()
            db.commit()
    except Exception:
        logger.exception("知识源后台索引异常 source=%s", source_uuid)
        _mark_source_index_failed(source_uuid, user_uuid)


async def delete_source_index_background(source_uuid: str, user_uuid: str) -> None:
    """尽力清理资料对应向量；失败不影响知识源主数据的软删除。"""
    if not settings.rag_enabled:
        return
    try:
        await delete_document_chunks(user_uuid=user_uuid, source_uuid=source_uuid)
    except Exception as exc:
        logger.warning("知识源向量清理失败 source=%s error=%s", source_uuid, exc)
