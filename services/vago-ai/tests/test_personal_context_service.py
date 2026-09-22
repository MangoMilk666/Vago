"""验证 Phase 9 的明确偏好、Grounded Memory 与 Personal Context 边界。"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.exceptions import AppException
from app.footprints.models import TravelObservation
from app.memory import service as memory_service
from app.memory.schemas import TravelMemoryUpdateRequest
from app.personal_context.service import build_personal_context
from app.preferences import service as preference_service
from app.preferences.schemas import TravelPreferenceUpdateRequest
from app.travel.models import ItineraryDay, ItinerarySpot, Trip


@pytest.fixture()
def db_session() -> Session:
    """以 SQLite 验证跨领域 Context 组装，无需本地 MySQL。"""
    from app.footprints import models as _footprint_models  # noqa: F401
    from app.knowledge import models as _knowledge_models  # noqa: F401
    from app.memory import models as _memory_models  # noqa: F401
    from app.preferences import models as _preference_models  # noqa: F401
    from app.travel import models as _travel_models  # noqa: F401

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


def _add_trip(db: Session, *, uuid: str, user_uuid: str, status: int) -> Trip:
    """构造最小 Trip 事实，供 Memory 和 Context 测试复用。"""
    trip = Trip(
        uuid=uuid,
        user_uuid=user_uuid,
        title="新加坡周末行",
        destination="Singapore",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 3),
        status=status,
        created_at=datetime(2026, 9, 1, 0, 0),
        updated_at=datetime(2026, 9, 3, 0, 0),
    )
    db.add(trip)
    db.commit()
    return trip


def test_memory_is_grounded_in_ended_trip_facts_and_keeps_user_narrative(db_session: Session):
    """测试：Memory 仅能基于结束行程建立，刷新事实不会覆写用户叙事。"""
    trip = _add_trip(db_session, uuid="ended-trip", user_uuid="user-a", status=3)
    day = ItineraryDay(
        uuid="memory-day", ref_uuid=trip.uuid, ref_type=ItineraryDay.REF_TYPE_TRIP,
        day_date=date(2026, 9, 1), day_index=1,
        created_at=datetime(2026, 9, 1), updated_at=datetime(2026, 9, 1),
    )
    db_session.add(day)
    db_session.add(
        ItinerarySpot(
            uuid="memory-spot", day_uuid=day.uuid, name="滨海湾花园", category=0, sort_order=0,
            created_at=datetime(2026, 9, 1), updated_at=datetime(2026, 9, 1),
        )
    )
    db_session.add_all([
        TravelObservation(
            uuid="auto-observation", client_event_uuid="auto-event", user_uuid="user-a", trip_uuid=trip.uuid,
            observation_type="AUTO_GPS", latitude=1.28, longitude=103.85, occurred_at=datetime(2026, 9, 1, tzinfo=UTC),
        ),
        TravelObservation(
            uuid="manual-observation", client_event_uuid="manual-event", user_uuid="user-a", trip_uuid=trip.uuid,
            observation_type="MANUAL_CHECKIN", latitude=1.29, longitude=103.86, location_name="鱼尾狮公园",
            occurred_at=datetime(2026, 9, 2, tzinfo=UTC),
        ),
    ])
    db_session.commit()

    memory = memory_service.refresh_trip_memory(db_session, "user-a", trip.uuid)
    assert memory.facts.automatic_sample_count == 1
    assert memory.facts.itinerary_spot_names == ["滨海湾花园"]
    assert [item.location_name for item in memory.facts.checkins] == ["鱼尾狮公园"]

    updated = memory_service.update_memory(
        db_session,
        "user-a",
        memory.uuid,
        TravelMemoryUpdateRequest(narrative="雨后的海湾格外安静。"),
    )
    refreshed = memory_service.refresh_trip_memory(db_session, "user-a", trip.uuid)
    assert updated.narrative == refreshed.narrative
    assert refreshed.facts.trip_uuid == trip.uuid


def test_personal_context_respects_travel_and_knowledge_authorization(db_session: Session):
    """测试：关闭授权时，预览与 Agent 注入都不应显示被关闭类别。"""
    context = build_personal_context(
        db_session,
        "user-a",
        include_travel_context=False,
        include_personal_knowledge=False,
    )

    assert context.labels == []
    assert context.current_trip is None
    assert context.travel_history == []
    assert context.knowledge_summary == {}


def test_memory_rejects_trip_that_has_not_ended(db_session: Session):
    """测试：进行中的旅行事实仍会变化，不能被错误固化成 Memory。"""
    trip = _add_trip(db_session, uuid="active-trip", user_uuid="user-a", status=2)

    with pytest.raises(AppException) as exc_info:
        memory_service.refresh_trip_memory(db_session, "user-a", trip.uuid)

    assert exc_info.value.code == "TRIP_NOT_ENDED"


def test_personal_context_uses_user_scoped_summaries_without_raw_coordinates(db_session: Session):
    """测试：Context 组合当前行程、偏好与观察摘要，不能泄露 GPS 经纬度。"""
    trip = _add_trip(db_session, uuid="current-trip", user_uuid="user-a", status=2)
    _add_trip(db_session, uuid="other-user-trip", user_uuid="user-b", status=3)
    preference_service.update_preferences(
        db_session,
        "user-a",
        TravelPreferenceUpdateRequest(pace="leisurely", interests=["美食", "建筑"]),
    )
    db_session.add(
        TravelObservation(
            uuid="context-checkin", client_event_uuid="context-event", user_uuid="user-a", trip_uuid=trip.uuid,
            observation_type="MANUAL_CHECKIN", latitude=1.3521, longitude=103.8198, location_name="小印度",
            occurred_at=datetime(2026, 9, 2, tzinfo=UTC),
        )
    )
    db_session.commit()

    context = build_personal_context(db_session, "user-a")
    dumped = context.model_dump_json(by_alias=True)

    assert context.current_trip["uuid"] == trip.uuid
    assert context.preferences["interests"] == ["美食", "建筑"]
    assert context.live_observations["recentCheckins"][0]["locationName"] == "小印度"
    assert "明确旅行偏好" in context.labels
    assert "1.3521" not in dumped
    assert "103.8198" not in dumped
    assert "other-user-trip" not in dumped
