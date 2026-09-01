"""Personal Travel Knowledge 领域服务。"""

import json
import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.knowledge.models import Guide, KnowledgeSource
from app.knowledge.schemas import (
    IndexStatus,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceResponse,
    KnowledgeSourceType,
    KnowledgeSourceUpdateRequest,
    ParseStatus,
    GuideCreateRequest,
    GuideResponse,
    GuideUpdateRequest,
)
from app.models.schemas import ArticleStatus, IngestRequest
from app.services.indexer import index_article
from app.services.vector_store import delete_article_chunks
from app.travel.models import utc_now_naive
from app.users.models import User

logger = logging.getLogger(__name__)

GUIDE_STATUS_DRAFT = 0
GUIDE_STATUS_PUBLISHED = 1
AI_STATUS_PENDING = 0
AI_STATUS_INDEXING = 1
AI_STATUS_INDEXED = 2
AI_STATUS_FAILED = 3


def _source_to_response(source: KnowledgeSource) -> KnowledgeSourceResponse:
    """KnowledgeSource ORM -> 不含社区字段的 API response。"""
    return KnowledgeSourceResponse(
        uuid=source.uuid,
        title=source.title,
        sourceType=source.source_type,
        originUrl=source.origin_url,
        originalFilename=source.original_filename,
        mimeType=source.mime_type,
        storageKey=source.storage_key,
        contentText=source.content_text,
        destination=source.destination,
        tags=_from_json(source.tags),
        parseStatus=source.parse_status,
        parseError=source.parse_error,
        indexStatus=source.index_status,
        indexError=source.index_error,
        createdAt=source.created_at,
        updatedAt=source.updated_at,
    )


def _get_source_or_raise(db: Session, source_uuid: str) -> KnowledgeSource:
    """读取未删除的个人知识源。"""
    source = db.scalar(
        select(KnowledgeSource).where(
            KnowledgeSource.uuid == source_uuid,
            KnowledgeSource.deleted_at.is_(None),
        )
    )
    # 分支条件：资料不存在或已经软删除时，返回新的 Knowledge 领域错误。
    if source is None:
        raise AppException("知识源不存在", status_code=404, code="KNOWLEDGE_SOURCE_NOT_FOUND")
    return source


def _ensure_source_owner(source: KnowledgeSource, user_uuid: str) -> None:
    """校验当前用户拥有该个人知识源。"""
    # 分支条件：请求用户与资料归属不一致时，禁止跨用户读取或修改。
    if source.user_uuid != user_uuid:
        raise AppException("无权访问该知识源", status_code=403, code="FORBIDDEN")


def list_sources(db: Session, user_uuid: str) -> list[KnowledgeSourceResponse]:
    """列出当前用户未删除的个人知识源。"""
    sources = db.scalars(
        select(KnowledgeSource)
        .where(KnowledgeSource.user_uuid == user_uuid, KnowledgeSource.deleted_at.is_(None))
        .order_by(KnowledgeSource.created_at.desc())
    ).all()
    return [_source_to_response(source) for source in sources]


def get_source(db: Session, user_uuid: str, source_uuid: str) -> KnowledgeSourceResponse:
    """读取当前用户自己的个人知识源详情。"""
    source = _get_source_or_raise(db, source_uuid)
    _ensure_source_owner(source, user_uuid)
    return _source_to_response(source)


def create_text_source(
    db: Session,
    user_uuid: str,
    payload: KnowledgeSourceCreateRequest,
) -> KnowledgeSourceResponse:
    """创建纯文本个人知识源，不自动触发任何 RAG 索引。"""
    # 分支条件：URL 导入需要独立抓取与解析流程，本轮不接受伪装成已导入内容的 URL 请求。
    if payload.source_type != KnowledgeSourceType.TEXT:
        raise AppException("当前仅支持创建纯文本知识源", status_code=400, code="PARAM_INVALID")
    # 分支条件：纯文本来源必须在创建时提供内容，保证可独立阅读。
    if not payload.content_text:
        raise AppException("纯文本知识源不能为空", status_code=400, code="PARAM_INVALID")

    source = KnowledgeSource(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        title=payload.title,
        source_type=KnowledgeSourceType.TEXT.value,
        origin_url=None,
        mime_type="text/plain",
        content_text=payload.content_text,
        destination=payload.destination,
        tags=_to_json(payload.tags),
        parse_status=ParseStatus.READY.value,
        index_status=IndexStatus.NOT_INDEXED.value,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _source_to_response(source)


def create_file_source(
    db: Session,
    user_uuid: str,
    *,
    source_uuid: str,
    title: str,
    original_filename: str,
    mime_type: str,
    storage_key: str,
    content_text: str,
    destination: str | None = None,
    tags: list[str] | None = None,
) -> KnowledgeSourceResponse:
    """创建已完成本地解析的文件知识源。"""
    source = KnowledgeSource(
        uuid=source_uuid,
        user_uuid=user_uuid,
        title=title,
        source_type=KnowledgeSourceType.FILE.value,
        original_filename=original_filename,
        mime_type=mime_type,
        storage_key=storage_key,
        content_text=content_text,
        destination=destination,
        tags=_to_json(tags),
        parse_status=ParseStatus.READY.value,
        index_status=IndexStatus.NOT_INDEXED.value,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _source_to_response(source)


def update_source(
    db: Session,
    user_uuid: str,
    source_uuid: str,
    payload: KnowledgeSourceUpdateRequest,
) -> KnowledgeSourceResponse:
    """更新个人知识源，并使旧的可选向量索引失效。"""
    source = _get_source_or_raise(db, source_uuid)
    _ensure_source_owner(source, user_uuid)
    values = payload.model_dump(exclude_unset=True, by_alias=False)
    for field_name, value in values.items():
        # 分支条件：标签列表在 MySQL 中以 JSON 字符串保存。
        if field_name == "tags":
            source.tags = _to_json(value)
        else:
            setattr(source, field_name, value)

    # 内容或展示元数据变化后，不允许旧向量继续作为最新资料被检索。
    source.index_status = IndexStatus.NOT_INDEXED.value
    source.index_error = None
    source.updated_at = utc_now_naive()
    db.commit()
    db.refresh(source)
    return _source_to_response(source)


def delete_source(db: Session, user_uuid: str, source_uuid: str) -> str | None:
    """软删除个人知识源，并返回待异步清理的原文件 storage key。"""
    source = _get_source_or_raise(db, source_uuid)
    _ensure_source_owner(source, user_uuid)
    storage_key = source.storage_key
    now = utc_now_naive()
    source.deleted_at = now
    source.updated_at = now
    source.index_status = IndexStatus.NOT_INDEXED.value
    db.commit()
    return storage_key


def mark_source_index_pending(
    db: Session,
    user_uuid: str,
    source_uuid: str,
) -> KnowledgeSourceResponse:
    """显式请求将已解析的个人知识源交给可选索引能力处理。"""
    source = _get_source_or_raise(db, source_uuid)
    _ensure_source_owner(source, user_uuid)
    # 分支条件：还没有可用文本的来源不能进入语义索引流程。
    if source.parse_status != ParseStatus.READY.value or not source.content_text:
        raise AppException("知识源尚未解析完成，不能加入索引", status_code=400, code="PARAM_INVALID")
    source.index_status = IndexStatus.PENDING.value
    source.index_error = None
    source.updated_at = utc_now_naive()
    db.commit()
    db.refresh(source)
    return _source_to_response(source)


def _new_uuid() -> str:
    """生成与旧 Java fastSimpleUUID 兼容的 32 位业务 ID。"""
    return uuid4().hex


def new_source_uuid() -> str:
    """为文件写入 storage 前预分配知识源 UUID。"""
    return _new_uuid()


def _to_json(values: list[str] | None) -> str | None:
    """将前端列表字段序列化为旧 guides 表中的 JSON 字符串。"""
    # 分支条件：前端未传列表时，保持数据库字段为空。
    if values is None:
        return None
    return json.dumps(values, ensure_ascii=False)


def _from_json(value: str | None) -> list[str]:
    """将旧 guides 表中的 JSON 字符串反序列化为前端列表字段。"""
    # 分支条件：数据库字段为空时，对前端返回空列表。
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    # 分支条件：历史脏数据不是数组时，按空列表兜底。
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _get_guide_or_raise(db: Session, guide_uuid: str) -> Guide:
    """读取未删除知识源，不存在时返回业务错误。"""
    guide = db.scalar(select(Guide).where(Guide.uuid == guide_uuid, Guide.deleted_at.is_(None)))
    # 分支条件：知识源不存在或已软删除时，返回不存在。
    if guide is None:
        raise AppException("攻略不存在", status_code=404, code="GUIDE_NOT_FOUND")
    return guide


def _ensure_owner(guide: Guide, user_uuid: str) -> None:
    """校验知识源归属当前用户。"""
    # 分支条件：知识源归属用户与当前 JWT 用户不一致时，拒绝访问。
    if guide.user_uuid != user_uuid:
        raise AppException("无权访问该攻略", status_code=403, code="FORBIDDEN")


def _author_by_uuid(db: Session, user_uuid: str) -> User | None:
    """读取作者资料快照，用于兼容旧 GuideVO 的 author 字段。"""
    return db.scalar(select(User).where(User.uuid == user_uuid, User.deleted_at.is_(None)))


def _guide_to_response(db: Session, guide: Guide) -> GuideResponse:
    """Guide ORM -> API response。"""
    author = _author_by_uuid(db, guide.user_uuid)
    return GuideResponse(
        uuid=guide.uuid,
        title=guide.title,
        destination=guide.destination,
        coverImageKey=guide.cover_image_key,
        imageKeys=_from_json(guide.image_keys),
        content=guide.content,
        tags=_from_json(guide.tags),
        viewCount=guide.view_count,
        likeCount=guide.like_count,
        liked=None,
        status=guide.status,
        aiStatus=guide.ai_status,
        authorUuid=author.uuid if author else guide.user_uuid,
        authorNickname=author.nickname if author else None,
        authorAvatarKey=author.avatar_oss_key if author else None,
        createdAt=guide.created_at,
        updatedAt=guide.updated_at,
    )


def list_my_guides(db: Session, user_uuid: str) -> list[GuideResponse]:
    """列出当前用户自己的全部知识源。"""
    guides = db.scalars(
        select(Guide)
        .where(Guide.user_uuid == user_uuid, Guide.deleted_at.is_(None))
        .order_by(Guide.created_at.desc())
    ).all()
    return [_guide_to_response(db, guide) for guide in guides]


def get_my_guide_detail(db: Session, user_uuid: str, guide_uuid: str) -> GuideResponse:
    """读取当前用户自己的知识源详情。"""
    guide = _get_guide_or_raise(db, guide_uuid)
    _ensure_owner(guide, user_uuid)
    return _guide_to_response(db, guide)


def create_guide(db: Session, user_uuid: str, payload: GuideCreateRequest) -> GuideResponse:
    """创建个人旅行知识源。"""
    status = payload.status if payload.status is not None else GUIDE_STATUS_PUBLISHED
    guide = Guide(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        title=payload.title,
        destination=payload.destination,
        cover_image_key=payload.cover_image_key,
        image_keys=_to_json(payload.image_keys),
        content=payload.content,
        tags=_to_json(payload.tags),
        view_count=0,
        like_count=0,
        status=status,
        ai_status=AI_STATUS_PENDING if status == GUIDE_STATUS_PUBLISHED else None,
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return _guide_to_response(db, guide)


def update_guide(db: Session, user_uuid: str, guide_uuid: str, payload: GuideUpdateRequest) -> GuideResponse:
    """局部更新个人旅行知识源。"""
    guide = _get_guide_or_raise(db, guide_uuid)
    _ensure_owner(guide, user_uuid)

    values = payload.model_dump(exclude_unset=True, by_alias=False)
    for field_name, value in values.items():
        # 分支条件：列表字段需要按旧表结构序列化为 JSON 字符串。
        if field_name in {"image_keys", "tags"}:
            setattr(guide, field_name, _to_json(value))
        else:
            setattr(guide, field_name, value)

    # 分支条件：更新后是发布状态，需要重新进入索引队列。
    if guide.status == GUIDE_STATUS_PUBLISHED:
        guide.ai_status = AI_STATUS_PENDING
    else:
        # 分支条件：更新后是草稿状态，需要清空索引状态并等待向量清理。
        guide.ai_status = None

    guide.updated_at = utc_now_naive()
    db.commit()
    db.refresh(guide)
    return _guide_to_response(db, guide)


def delete_guide(db: Session, user_uuid: str, guide_uuid: str) -> bool:
    """软删除个人旅行知识源，返回是否需要清理向量库。"""
    guide = _get_guide_or_raise(db, guide_uuid)
    _ensure_owner(guide, user_uuid)
    should_delete_vectors = guide.ai_status is not None
    now = utc_now_naive()
    guide.deleted_at = now
    guide.updated_at = now
    db.commit()
    return should_delete_vectors


def mark_guide_pending(db: Session, user_uuid: str, guide_uuid: str) -> GuideResponse:
    """手动触发知识源向量化前，将状态重置为 PENDING。"""
    guide = _get_guide_or_raise(db, guide_uuid)
    _ensure_owner(guide, user_uuid)
    # 分支条件：草稿不进入个人知识库索引。
    if guide.status != GUIDE_STATUS_PUBLISHED:
        raise AppException("草稿攻略不能加入 AI 知识库", status_code=400, code="PARAM_INVALID")
    guide.ai_status = AI_STATUS_PENDING
    guide.updated_at = utc_now_naive()
    db.commit()
    db.refresh(guide)
    return _guide_to_response(db, guide)


async def index_guide_background(guide_uuid: str, user_uuid: str) -> None:
    """后台执行知识源索引，并把结果回写到 guides.ai_status。"""
    with SessionLocal() as db:
        guide = db.scalar(select(Guide).where(Guide.uuid == guide_uuid, Guide.deleted_at.is_(None)))
        # 分支条件：后台执行时知识源已被删除或归属变化，直接跳过。
        if guide is None or guide.user_uuid != user_uuid:
            return
        # 分支条件：草稿状态不应进入向量库。
        if guide.status != GUIDE_STATUS_PUBLISHED:
            return

        guide.ai_status = AI_STATUS_INDEXING
        guide.updated_at = utc_now_naive()
        db.commit()

        response = await index_article(
            IngestRequest(
                article_id=guide.uuid,
                user_uuid=guide.user_uuid,
                title=guide.title,
                source_url=None,
                raw_content=guide.content,
                destinations=[guide.destination] if guide.destination else None,
            )
        )

        guide = db.scalar(select(Guide).where(Guide.uuid == guide_uuid, Guide.deleted_at.is_(None)))
        # 分支条件：索引期间知识源被删除时，不再回写状态。
        if guide is None:
            return
        guide.ai_status = AI_STATUS_INDEXED if response.status == ArticleStatus.INDEXED else AI_STATUS_FAILED
        guide.updated_at = utc_now_naive()
        db.commit()


async def delete_guide_vectors_background(guide_uuid: str, user_uuid: str) -> None:
    """后台清理知识源对应的 Qdrant 文本块。"""
    try:
        await delete_article_chunks(user_uuid=user_uuid, article_id=guide_uuid)
    except Exception as exc:
        logger.warning("知识源向量清理失败 guide=%s error=%s", guide_uuid, exc)
