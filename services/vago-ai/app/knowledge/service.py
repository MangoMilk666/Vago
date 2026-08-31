"""Personal Travel Knowledge 领域服务。"""

import json
import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.knowledge.models import Guide
from app.knowledge.schemas import GuideCreateRequest, GuideResponse, GuideUpdateRequest
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


def _new_uuid() -> str:
    """生成与旧 Java fastSimpleUUID 兼容的 32 位业务 ID。"""
    return uuid4().hex


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
