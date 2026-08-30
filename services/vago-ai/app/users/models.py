"""用户领域 SQLAlchemy model。

字段按 ``docs/database/db_schema.sql`` 中现有 MySQL 表定义建模，
Phase 2 先复用旧库结构，不引入破坏性 schema 变更。
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now_naive() -> datetime:
    """生成兼容 MySQL DATETIME 的 UTC naive 时间。"""
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    """对应 ``users`` 表，承载账号主体信息。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar_oss_key: Mapped[str | None] = mapped_column(String(512))
    plan_type: Mapped[int] = mapped_column(default=0, nullable=False)
    article_quota: Mapped[int] = mapped_column(default=50, nullable=False)
    ai_calls_today: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class UserOauthBinding(Base):
    """对应 ``user_oauth_bindings`` 表，记录第三方账号绑定。"""

    __tablename__ = "user_oauth_bindings"
    __table_args__ = (
        UniqueConstraint("provider", "open_id", name="uk_provider_openid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    open_id: Mapped[str] = mapped_column(String(128), nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )


class UserSettings(Base):
    """对应 ``user_settings`` 表，承载用户个性化偏好。"""

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    gps_mode: Mapped[int] = mapped_column(default=1, nullable=False)
    fog_unlock_radius_m: Mapped[int] = mapped_column(default=300, nullable=False)
    default_visibility: Mapped[int] = mapped_column(default=0, nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    notification_checkin: Mapped[int] = mapped_column(default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
