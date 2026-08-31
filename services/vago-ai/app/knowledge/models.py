"""个人旅行知识源 SQLAlchemy model。

Phase 4 先复用旧 ``guides`` 表承载 Knowledge Source，避免引入破坏性 schema 变更。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.travel.models import utc_now_naive


class Guide(Base):
    """对应 ``guides`` 表，Phase 4 重定位为个人旅行知识源。"""

    __tablename__ = "guides"

    # 数据库自增主键，仅用于内部关联。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 攻略/知识源业务 UUID，对外暴露并用于向量库 article_id。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 所属用户 UUID，用于 MySQL 与 Qdrant 双重隔离。
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 知识源标题。
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    # 目的地标签或地点描述。
    destination: Mapped[str | None] = mapped_column(String(200))
    # 封面图对象存储 key。
    cover_image_key: Mapped[str | None] = mapped_column(String(500))
    # 图片列表 JSON 字符串。
    image_keys: Mapped[str | None] = mapped_column(Text)
    # 攻略/资料正文。
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 标签列表 JSON 字符串。
    tags: Mapped[str | None] = mapped_column(String(500))
    # 历史浏览量；个人知识链路暂不主动增长。
    view_count: Mapped[int] = mapped_column(default=0, nullable=False)
    # 历史点赞数；Phase 4 不迁移点赞语义，仅兼容返回。
    like_count: Mapped[int] = mapped_column(default=0, nullable=False)
    # 状态，0=草稿，1=已发布/可索引。
    status: Mapped[int] = mapped_column(default=1, nullable=False)
    # RAG 向量化状态，NULL=草稿未索引，0=PENDING，1=INDEXING，2=INDEXED，3=FAILED。
    ai_status: Mapped[int | None] = mapped_column(Integer)
    # 知识源创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 知识源最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    # 知识源软删除时间；为空表示未删除。
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
