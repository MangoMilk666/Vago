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

    # 数据库自增主键，仅用于内部关联。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 用户业务 UUID，对外暴露并用于用户级数据隔离。
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    # 手机号，支持短信登录与账号找回。
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    # 邮箱地址，支持 OAuth 绑定和后续通知能力。
    email: Mapped[str | None] = mapped_column(String(128), unique=True)
    # 用户昵称，前端展示的主要名称。
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    # 头像对象存储 key 或历史头像标识。
    avatar_oss_key: Mapped[str | None] = mapped_column(String(512))
    # 账号套餐类型，0 表示默认免费套餐。
    plan_type: Mapped[int] = mapped_column(default=0, nullable=False)
    # 攻略/知识条目配额。
    article_quota: Mapped[int] = mapped_column(default=50, nullable=False)
    # 当日 AI 调用次数，用于轻量配额控制。
    ai_calls_today: Mapped[int] = mapped_column(default=0, nullable=False)
    # 账号状态，1 表示正常。
    status: Mapped[int] = mapped_column(default=1, nullable=False)
    # 账号创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 账号最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    # 账号软删除时间；为空表示未删除。
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class UserOauthBinding(Base):
    """对应 ``user_oauth_bindings`` 表，记录第三方账号绑定。"""

    __tablename__ = "user_oauth_bindings"
    __table_args__ = (
        UniqueConstraint("provider", "open_id", name="uk_provider_openid"),
    )

    # 数据库自增主键，仅用于内部关联。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 绑定的本地用户自增 ID。
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    # 第三方登录提供商标识，例如 github。
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # 第三方账号 open_id，用于唯一识别外部账号。
    open_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # 第三方 access token，按当前兼容逻辑保存。
    access_token: Mapped[str | None] = mapped_column(Text)
    # 第三方 access token 过期时间。
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    # 绑定创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 绑定最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )


class UserSettings(Base):
    """对应 ``user_settings`` 表，承载用户个性化偏好。"""

    __tablename__ = "user_settings"

    # 用户自增 ID，同时作为设置表主键。
    user_id: Mapped[int] = mapped_column(primary_key=True)
    # GPS 记录模式，控制旅行中定位采样策略。
    gps_mode: Mapped[int] = mapped_column(default=1, nullable=False)
    # 迷雾地图解锁半径，单位为米。
    fog_unlock_radius_m: Mapped[int] = mapped_column(default=300, nullable=False)
    # 默认可见性，0 表示私有。
    default_visibility: Mapped[int] = mapped_column(default=0, nullable=False)
    # 用户界面语言偏好。
    language: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)
    # 用户时区偏好，用于展示旅行日期和通知时间。
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    # 是否开启打卡提醒，1 表示开启。
    notification_checkin: Mapped[int] = mapped_column(default=1, nullable=False)
    # 设置最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
