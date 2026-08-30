"""Trip / Plan / Itinerary 的 SQLAlchemy model。

Phase 3 先按现有 MySQL DDL 建模，保证 Java 侧历史数据可以被 FastAPI 直接复用。
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now_naive() -> datetime:
    """生成兼容 MySQL DATETIME 的 UTC naive 时间。"""
    return datetime.now(UTC).replace(tzinfo=None)


class Trip(Base):
    """正式行程表。"""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(200))
    cover_image_key: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Plan(Base):
    """旅行计划草稿表。"""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    budget_currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    converted_trip_uuid: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class ItineraryDay(Base):
    """每日行程主表。"""

    __tablename__ = "itinerary_days"

    REF_TYPE_TRIP = 1
    REF_TYPE_PLAN = 2

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    ref_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    ref_type: Mapped[int] = mapped_column(nullable=False)
    day_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_index: Mapped[int] = mapped_column(nullable=False)
    transportation: Mapped[str | None] = mapped_column(String(200))
    accommodation: Mapped[str | None] = mapped_column(String(300))
    meal_breakfast: Mapped[str | None] = mapped_column(String(200))
    meal_lunch: Mapped[str | None] = mapped_column(String(200))
    meal_dinner: Mapped[str | None] = mapped_column(String(200))
    budget_day: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )


class ItinerarySpot(Base):
    """每日景点 / 打卡点表。"""

    __tablename__ = "itinerary_spots"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    day_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[int] = mapped_column(default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
