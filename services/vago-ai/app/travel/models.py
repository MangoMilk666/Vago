"""Trip / Plan / Itinerary 的 SQLAlchemy model。

Phase 3 先按现有 MySQL DDL 建模，保证 Java 侧历史数据可以被 FastAPI 直接复用。
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now_naive() -> datetime:
    """生成兼容 MySQL DATETIME 的 UTC naive 时间。"""
    return datetime.now(UTC).replace(tzinfo=None)


class Trip(Base):
    """正式行程表。"""

    __tablename__ = "trips"

    # 数据库自增主键，仅用于内部关联。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 行程业务 UUID，对外暴露并用于 itinerary 关联。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 所属用户 UUID，用于用户级数据隔离。
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 行程标题。
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    # 行程目的地。
    destination: Mapped[str | None] = mapped_column(String(200))
    # 封面图对象存储 key。
    cover_image_key: Mapped[str | None] = mapped_column(String(500))
    # 行程开始日期。
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 行程结束日期。
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 行程状态，1=未开始，2=进行中，3=已结束。
    status: Mapped[int] = mapped_column(default=1, nullable=False)
    # 行程创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 行程最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    # 行程软删除时间；为空表示未删除。
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Plan(Base):
    """旅行计划草稿表。"""

    __tablename__ = "plans"

    # 数据库自增主键，仅用于内部关联。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 计划业务 UUID，对外暴露并用于 itinerary 关联。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 所属用户 UUID，用于用户级数据隔离。
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 计划标题。
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    # 计划目的地。
    destination: Mapped[str | None] = mapped_column(String(200))
    # 计划开始日期；草稿阶段允许为空。
    start_date: Mapped[date | None] = mapped_column(Date)
    # 计划结束日期；草稿阶段允许为空。
    end_date: Mapped[date | None] = mapped_column(Date)
    # 计划总预算。
    budget: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # 预算货币代码，默认 CNY。
    budget_currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    # 计划备注。
    notes: Mapped[str | None] = mapped_column(Text)
    # 计划转换成正式行程后的目标 Trip UUID。
    converted_trip_uuid: Mapped[str | None] = mapped_column(String(32))
    # 计划状态，0 表示草稿，1 表示已转换。
    status: Mapped[int] = mapped_column(default=0, nullable=False)
    # 计划创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 计划最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    # 计划软删除时间；为空表示未删除。
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class ItineraryDay(Base):
    """每日行程主表。"""

    __tablename__ = "itinerary_days"
    # 同一行程或计划在同一日期只保留一份日程，避免并发懒初始化产生重复 UI。
    __table_args__ = (UniqueConstraint("ref_uuid", "ref_type", "day_date", name="uk_itinerary_days_ref_date"),)

    # 关联对象类型：正式行程。
    REF_TYPE_TRIP = 1
    # 关联对象类型：旅行计划草稿。
    REF_TYPE_PLAN = 2

    # 数据库自增主键，仅用于内部关联。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 每日行程业务 UUID，用于 spots 关联。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 关联的 Trip 或 Plan UUID。
    ref_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 关联对象类型，1=Trip，2=Plan。
    ref_type: Mapped[int] = mapped_column(nullable=False)
    # 当日日期。
    day_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 第几天，1-based。
    day_index: Mapped[int] = mapped_column(nullable=False)
    # 当日交通安排。
    transportation: Mapped[str | None] = mapped_column(String(200))
    # 当日住宿安排。
    accommodation: Mapped[str | None] = mapped_column(String(300))
    # 当日早餐安排。
    meal_breakfast: Mapped[str | None] = mapped_column(String(200))
    # 当日午餐安排。
    meal_lunch: Mapped[str | None] = mapped_column(String(200))
    # 当日晚餐安排。
    meal_dinner: Mapped[str | None] = mapped_column(String(200))
    # 当日预算。
    budget_day: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # 当日备注。
    notes: Mapped[str | None] = mapped_column(Text)
    # 每日行程创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 每日行程最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )


class ItinerarySpot(Base):
    """每日景点 / 打卡点表。"""

    __tablename__ = "itinerary_spots"

    # 数据库自增主键，仅用于内部关联。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 景点/活动业务 UUID。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 所属每日行程 UUID。
    day_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 景点或活动名称。
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 景点或活动地址。
    address: Mapped[str | None] = mapped_column(String(300))
    # 类型分类，0=景点，1=餐厅，2=购物，3=娱乐，4=中转，5=其他。
    category: Mapped[int] = mapped_column(default=0, nullable=False)
    # 当日排序序号。
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    # 预计停留时长，单位为分钟。
    duration_minutes: Mapped[int | None] = mapped_column()
    # 景点或活动备注。
    notes: Mapped[str | None] = mapped_column(String(500))
    # 景点记录创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 景点记录最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
