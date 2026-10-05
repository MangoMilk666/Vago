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
    SCENARIOS,
    _distance_meters,
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
    first = build_scenario_observations("MARINA_SANDS_BAY", 42)
    second = build_scenario_observations("MARINA_SANDS_BAY", 42)

    assert first == second
    assert {item.observation_type for item in first} == {AUTO_GPS, MANUAL_CHECKIN}
    assert len({item.tracking_segment_uuid for item in first if item.observation_type == AUTO_GPS}) == 2
    assert "LONDON" in available_locations()
    assert "TOKYO_SHIBUYA" in available_locations()
    assert "PARIS_SEINE" in available_locations()
    assert "ICELAND_REYKJAVIK" in available_locations()


def test_marina_sand_alias_resolves_to_canonical_scenario() -> None:
    """测试：首版 CLI 示例中的 Marina_Sand 别名应兼容为规范滨海湾场景。"""
    observations = build_scenario_observations("Marina_Sand_BAY", 42)

    assert observations == build_scenario_observations("MARINA_SANDS_BAY", 42)


def test_haversine_distance_matches_known_coordinate_distance() -> None:
    """测试：Haversine 距离包含平方根并正确返回约一度经度的地表距离。"""
    assert _distance_meters(0.0, 0.0, 0.0, 1.0) == pytest.approx(111_195, abs=100)


@pytest.mark.parametrize("location", [code for code in SCENARIOS if code != "CHECKIN_PROXIMITY"])
def test_regular_scenarios_generate_dense_full_day_footprints(location: str) -> None:
    """测试：普通场景默认生成足够密集、覆盖整日且符合距离限制的点位。"""
    observations = build_scenario_observations(location, 42)
    gps_points = [item for item in observations if item.observation_type == AUTO_GPS]
    checkins = [item for item in observations if item.observation_type == MANUAL_CHECKIN]

    assert len(gps_points) > 30
    assert len(checkins) == 6
    assert (gps_points[-1].occurred_at - gps_points[0].occurred_at).total_seconds() >= 7 * 60 * 60
    assert (observations[-1].occurred_at - observations[0].occurred_at).total_seconds() <= 8 * 60 * 60

    grouped_gps: dict[str, list] = {}
    for point in gps_points:
        grouped_gps.setdefault(point.tracking_segment_uuid, []).append(point)
    for segment_points in grouped_gps.values():
        for previous, current in zip(segment_points, segment_points[1:]):
            assert _distance_meters(
                previous.latitude,
                previous.longitude,
                current.latitude,
                current.longitude,
            ) >= 15

    for checkin in checkins:
        assert all(
            _distance_meters(point.latitude, point.longitude, checkin.latitude, checkin.longitude) >= 15
            for point in gps_points
        )
    for index, checkin in enumerate(checkins):
        assert all(
            _distance_meters(checkin.latitude, checkin.longitude, other.latitude, other.longitude) >= 30
            for other in checkins[index + 1:]
        )


def test_day_hours_can_be_configured_within_valid_range() -> None:
    """测试：普通场景支持调整日内跨度，越界跨度会被拒绝。"""
    observations = build_scenario_observations("LONDON", 42, day_hours=6)
    gps_points = [item for item in observations if item.observation_type == AUTO_GPS]
    assert (gps_points[-1].occurred_at - gps_points[0].occurred_at).total_seconds() >= 5 * 60 * 60
    assert (observations[-1].occurred_at - observations[0].occurred_at).total_seconds() <= 6 * 60 * 60

    with pytest.raises(ValueError, match="--day-hours"):
        build_scenario_observations("LONDON", 42, day_hours=13)


def test_seed_and_clear_only_touch_matching_run(db_session: Session) -> None:
    """测试：Seed 生成的 run 可被定向清理，不会删除真实或其他 run 的观察。"""
    db_session.add(TravelObservation(
        uuid="real-observation", client_event_uuid="ios-real-event", user_uuid="user-a", trip_uuid="trip-a",
        observation_type=AUTO_GPS, latitude=1.3, longitude=103.8, occurred_at=build_scenario_observations("CA_TAHOE", 1)[0].occurred_at.replace(tzinfo=None),
    ))
    db_session.commit()

    summary = seed_footprints(
        db_session, user_uuid="user-a", trip_uuid="trip-a", location="TOKYO_SHIBUYA",
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
