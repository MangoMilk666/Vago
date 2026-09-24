"""验证开发环境 Travel Footprint Seed 工具的确定性与安全清理边界。"""

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.devtools.seed_footprints import (
    AUTO_GPS,
    DEV_SEED_PREFIX,
    MANUAL_CHECKIN,
    available_locations,
    build_scenario_observations,
    clear_seed_run,
    seed_footprints,
)
from app.footprints.models import TravelObservation
from app.travel.models import Trip


@pytest.fixture()
def db_session() -> Session:
    """测试：使用 SQLite 验证 Seed 工具，不连接开发 MySQL。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    with session_local() as session:
        session.add(Trip(
            uuid="trip-a", user_uuid="user-a", title="测试行程", destination="新加坡",
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 5), status=2,
        ))
        session.commit()
        yield session


def test_scenario_generation_is_deterministic_and_segmented() -> None:
    """测试：相同场景和随机种子生成相同坐标、时间和分段，而非单一直线。"""
    first = build_scenario_observations("MARINA_SANDS_BAY_01", 42)
    second = build_scenario_observations("MARINA_SANDS_BAY_01", 42)

    assert first == second
    assert {item.observation_type for item in first} == {AUTO_GPS, MANUAL_CHECKIN}
    assert len({item.tracking_segment_uuid for item in first if item.observation_type == AUTO_GPS}) == 2
    assert "TOKYO_SHIBUYA_01" in available_locations()
    assert "PARIS_SEINE_01" in available_locations()
    assert "ICELAND_REYKJAVIK_01" in available_locations()


def test_marina_sand_alias_resolves_to_canonical_scenario() -> None:
    """测试：首版 CLI 示例中的 Marina_Sand 别名应兼容为规范滨海湾场景。"""
    observations = build_scenario_observations("Marina_Sand_BAY_01", 42)

    assert observations == build_scenario_observations("MARINA_SANDS_BAY_01", 42)


def test_seed_and_clear_only_touch_matching_run(db_session: Session) -> None:
    """测试：Seed 生成的 run 可被定向清理，不会删除真实或其他 run 的观察。"""
    db_session.add(TravelObservation(
        uuid="real-observation", client_event_uuid="ios-real-event", user_uuid="user-a", trip_uuid="trip-a",
        observation_type=AUTO_GPS, latitude=1.3, longitude=103.8, occurred_at=build_scenario_observations("CA_TAHOE", 1)[0].occurred_at.replace(tzinfo=None),
    ))
    db_session.commit()

    summary = seed_footprints(
        db_session, user_uuid="user-a", trip_uuid="trip-a", location="TOKYO_SHIBUYA_01",
        seed=42, run_id="tokyo-42",
    )
    created = db_session.scalars(select(TravelObservation).where(
        TravelObservation.client_event_uuid.startswith(f"{DEV_SEED_PREFIX}tokyo-42:")
    )).all()

    assert summary["observation_count"] == len(created)
    assert summary["automatic_sample_count"] > 0
    assert summary["checkin_count"] > 0

    deleted_count = clear_seed_run(db_session, user_uuid="user-a", trip_uuid="trip-a", run_id="tokyo-42")
    remaining_keys = set(db_session.scalars(select(TravelObservation.client_event_uuid)).all())

    assert deleted_count == len(created)
    assert "ios-real-event" in remaining_keys
    assert not any(key.startswith(f"{DEV_SEED_PREFIX}tokyo-42:") for key in remaining_keys)


def test_seed_rejects_trip_owned_by_another_user(db_session: Session) -> None:
    """测试：开发工具不能绕过 Trip 的用户归属校验。"""
    with pytest.raises(ValueError, match="不属于指定"):
        seed_footprints(
            db_session, user_uuid="another-user", trip_uuid="trip-a", location="CA_TAHOE",
            seed=42, run_id="tahoe-42",
        )
