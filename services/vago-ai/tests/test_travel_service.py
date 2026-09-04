from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import AppException
from app.models.schemas import StructuredDay, StructuredPlan, StructuredSpot
from app.travel import service
from app.travel.models import ItineraryDay, ItinerarySpot, Plan, Trip
from app.travel.schemas import (
    ItineraryDayUpdateRequest,
    ItinerarySpotRequest,
    PlanCreateRequest,
    TripCreateRequest,
    TripUpdateRequest,
)


@pytest.fixture()
def db_session() -> Session:
    """用内存 SQLite 验证 travel 领域服务，不依赖本地 MySQL。"""
    from app.core.database import Base
    from app.travel import models as _models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    with SessionLocal() as session:
        yield session


def test_trip_crud_is_scoped_by_current_user(db_session: Session):
    """测试：Trip CRUD 必须按当前用户隔离。"""
    trip = service.create_trip(
        db_session,
        "user-a",
        TripCreateRequest(
            title="东京行",
            destination="Tokyo",
            startDate=date(2026, 9, 1),
            endDate=date(2026, 9, 3),
        ),
    )

    updated = service.update_trip(
        db_session,
        "user-a",
        trip.uuid,
        TripUpdateRequest(title="东京秋日行"),
    )

    assert updated.title == "东京秋日行"
    assert updated.status == service.TRIP_STATUS_NOT_STARTED

    with pytest.raises(AppException) as exc_info:
        service.get_trip_detail(db_session, "user-b", trip.uuid)

    assert exc_info.value.code == "FORBIDDEN"


def test_trip_lifecycle_allows_one_active_trip_and_locks_history(db_session: Session):
    """测试：正式行程只能依次未开始、进行中、已结束，历史行程不可编辑。"""
    first_trip = service.create_trip(
        db_session,
        "user-a",
        TripCreateRequest(title="东京行", startDate=date(2026, 9, 1), endDate=date(2026, 9, 3)),
    )
    second_trip = service.create_trip(
        db_session,
        "user-a",
        TripCreateRequest(title="大阪行", startDate=date(2026, 10, 1), endDate=date(2026, 10, 3)),
    )

    started = service.start_trip(db_session, "user-a", first_trip.uuid)
    assert started.status == service.TRIP_STATUS_IN_PROGRESS

    with pytest.raises(AppException) as active_exc:
        service.start_trip(db_session, "user-a", second_trip.uuid)
    assert active_exc.value.code == "TRIP_ALREADY_IN_PROGRESS"

    ended = service.finish_trip(db_session, "user-a", first_trip.uuid)
    assert ended.status == service.TRIP_STATUS_ENDED
    assert service.list_history_trips(db_session, "user-a")[0].uuid == first_trip.uuid

    with pytest.raises(AppException) as update_exc:
        service.update_trip(db_session, "user-a", first_trip.uuid, TripUpdateRequest(title="不应更新"))
    assert update_exc.value.code == "TRIP_ENDED"


def test_plan_convert_copies_itinerary_days_and_spots(db_session: Session):
    """测试：计划转正式行程时应复制每日安排和景点。"""
    plan = service.create_plan(
        db_session,
        "user-a",
        PlanCreateRequest(
            title="京都草稿",
            destination="Kyoto",
            startDate=date(2026, 10, 1),
            endDate=date(2026, 10, 2),
            budget=Decimal("3000.00"),
        ),
    )
    service.update_itinerary_day(
        db_session,
        "user-a",
        plan.uuid,
        ItineraryDay.REF_TYPE_PLAN,
        1,
        ItineraryDayUpdateRequest(
            transportation="JR",
            spots=[
                ItinerarySpotRequest(name="清水寺", category=0, durationMinutes=120),
                ItinerarySpotRequest(name="祇园晚餐", category=1),
            ],
        ),
    )

    trip = service.convert_plan_to_trip(db_session, "user-a", plan.uuid)
    plan_row = db_session.query(Plan).filter(Plan.uuid == plan.uuid).one()
    trip_days = service.get_itinerary_days(
        db_session,
        "user-a",
        trip.uuid,
        ItineraryDay.REF_TYPE_TRIP,
    )

    assert plan_row.status == 1
    assert plan_row.converted_trip_uuid == trip.uuid
    assert len(trip_days) == 2
    assert trip_days[0].transportation == "JR"
    assert [spot.name for spot in trip_days[0].spots] == ["清水寺", "祇园晚餐"]


def test_get_itinerary_days_lazy_initializes_missing_dates(db_session: Session):
    """测试：读取每日行程时应为缺失日期懒初始化空 day。"""
    trip = Trip(
        id=1,
        uuid="trip-uuid",
        user_uuid="user-a",
        title="首尔行",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 3),
        status=1,
        created_at=datetime(2026, 8, 31, 9, 0, 0),
        updated_at=datetime(2026, 8, 31, 9, 0, 0),
    )
    existing_day = ItineraryDay(
        id=1,
        uuid="day-uuid",
        ref_uuid="trip-uuid",
        ref_type=ItineraryDay.REF_TYPE_TRIP,
        day_date=date(2026, 11, 2),
        day_index=99,
        created_at=datetime(2026, 8, 31, 9, 0, 0),
        updated_at=datetime(2026, 8, 31, 9, 0, 0),
    )
    db_session.add_all([trip, existing_day])
    db_session.add(
        ItinerarySpot(
            id=1,
            uuid="spot-uuid",
            day_uuid="day-uuid",
            name="景福宫",
            sort_order=0,
            category=0,
            created_at=datetime(2026, 8, 31, 9, 0, 0),
            updated_at=datetime(2026, 8, 31, 9, 0, 0),
        )
    )
    db_session.commit()

    days = service.get_itinerary_days(db_session, "user-a", "trip-uuid", ItineraryDay.REF_TYPE_TRIP)

    assert [item.day_index for item in days] == [1, 2, 3]
    assert days[1].uuid == "day-uuid"
    assert days[1].spots[0].name == "景福宫"


def test_ai_structured_plan_save_uses_travel_domain(db_session: Session):
    """测试：AI 结构化行程应能直接保存到 FastAPI travel domain。"""
    structured_plan = StructuredPlan(
        title="AI 京都三日",
        destination="Kyoto",
        start_date="2026-10-01",
        end_date="2026-10-03",
        budget=3600,
        days=[
            StructuredDay(
                day_index=1,
                transportation="JR",
                spots=[
                    StructuredSpot(name="清水寺", category=0, duration_minutes=120),
                    StructuredSpot(name="祇园晚餐", category=1),
                ],
            ),
            StructuredDay(day_index=2, day_date="2026-10-02", spots=[]),
        ],
    )

    saved = service.save_structured_plan_as_draft(db_session, "user-ai", structured_plan)
    days = service.get_itinerary_days(db_session, "user-ai", saved.uuid, ItineraryDay.REF_TYPE_PLAN)

    assert saved.type == "plan"
    assert [day.day_index for day in days] == [1, 2, 3]
    assert days[0].day_date == date(2026, 10, 1)
    assert [spot.name for spot in days[0].spots] == ["清水寺", "祇园晚餐"]
