"""Grounded Travel Memory 的 SQLAlchemy model。"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.travel.models import utc_now_naive


class TravelMemory(Base):
    """一段已结束行程的回忆，事实快照与用户/AI叙事明确分离。"""

    __tablename__ = "travel_memories"
    __table_args__ = (
        UniqueConstraint("user_uuid", "trip_uuid", name="uk_travel_memories_user_trip"),
    )

    # 数据库内部主键。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 对外暴露的回忆业务 UUID。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 回忆归属用户，用于隔离个人旅行历史。
    user_uuid: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    # 此回忆基于的已结束正式行程 UUID。
    trip_uuid: Mapped[str] = mapped_column(String(32), nullable=False)
    # 用户可编辑的回忆标题。
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    # 由领域事实生成的 JSON 快照；Agent 只能读取，不能改写原观察事实。
    fact_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    # 可编辑的叙事文本；为空代表当前只有事实回忆，没有生成故事。
    narrative: Mapped[str | None] = mapped_column(Text)
    # 最近一次刷新事实快照的时间。
    facts_refreshed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
