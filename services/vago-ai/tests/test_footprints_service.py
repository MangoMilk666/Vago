from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.exceptions import AppException
from app.footprints import service
from app.footprints.models import TravelObservation
from app.footprints.schemas import CheckinCreateRequest, LocationSyncRequest
from app.travel.models import Trip


@pytest.fixture()
def db_session() -> Session:
    """使用内存 SQLite 验证足迹领域服务，不依赖本地 MySQL。"""
    from app.footprints import models as _footprint_models  # noqa: F401
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


def _add_trip(db: Session, *, uuid: str, user_uuid: str, status: int) -> None:
    """创建测试所需的最小正式行程。"""
    now = datetime(2026, 9, 4, 12, 0, 0)
    db.add(
        Trip(
            uuid=uuid,
            user_uuid=user_uuid,
            title="测试行程",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
            status=status,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()


def test_location_sync_is_user_scoped_and_idempotent(db_session: Session):
    """测试：GPS 样本重试不重复写入，且其他用户不能读取该行程轨迹。"""
    _add_trip(db_session, uuid="trip-a", user_uuid="user-a", status=2)
    payload = LocationSyncRequest(
        tripUuid="trip-a",
        samples=[
            {
                "clientUuid": "ios-sample-1",
                "latitude": 1.3521,
                "longitude": 103.8198,
                "accuracyM": 12.5,
                "trackingSegmentUuid": "c5e49cc2-75c2-4d06-b87d-728b30b83b97",
                "recordedAt": datetime(2026, 9, 4, 4, 0, tzinfo=UTC),
            }
        ],
    )

    first = service.sync_location_samples(db_session, "user-a", payload)
    second = service.sync_location_samples(db_session, "user-a", payload)

    assert first.accepted_count == 1
    assert second.accepted_count == 0
    assert second.duplicate_count == 1
    assert db_session.query(TravelObservation).count() == 1
    locations = service.list_trip_locations(db_session, "user-a", "trip-a")
    assert len(locations) == 1
    assert locations[0].tracking_segment_uuid == "c5e49cc2-75c2-4d06-b87d-728b30b83b97"
    with pytest.raises(AppException) as exc_info:
        service.list_trip_locations(db_session, "user-b", "trip-a")
    assert exc_info.value.code == "TRIP_NOT_FOUND"


def test_checkin_requires_an_in_progress_trip(db_session: Session):
    """测试：打卡只能写入进行中行程，避免修改已结束旅行的事实记录。"""
    _add_trip(db_session, uuid="trip-not-started", user_uuid="user-a", status=1)
    payload = CheckinCreateRequest(
        tripUuid="trip-not-started",
        locationName="滨海湾花园",
        latitude=1.2816,
        longitude=103.8636,
        note="傍晚散步",
    )

    with pytest.raises(AppException) as exc_info:
        service.create_checkin(db_session, "user-a", payload)
    assert exc_info.value.code == "TRIP_NOT_IN_PROGRESS"

    db_session.query(Trip).filter(Trip.uuid == "trip-not-started").update({"status": 2})
    db_session.commit()
    checkin = service.create_checkin(db_session, "user-a", payload)

    assert checkin.location_name == "滨海湾花园"
    assert db_session.query(TravelObservation).count() == 1
    assert [item.uuid for item in service.list_trip_checkins(db_session, "user-a", "trip-not-started")] == [checkin.uuid]


def test_checkin_rejects_another_point_within_thirty_meters(db_session: Session):
    """测试：服务端拒绝同一行程中 30 米内的重复打卡，容纳真机 GPS 漂移。"""
    _add_trip(db_session, uuid="trip-nearby-checkin", user_uuid="user-a", status=2)
    first_payload = CheckinCreateRequest(
        tripUuid="trip-nearby-checkin",
        locationName="第一次打卡",
        latitude=1.3521,
        longitude=103.8198,
    )
    service.create_checkin(db_session, "user-a", first_payload)

    nearby_payload = CheckinCreateRequest(
        tripUuid="trip-nearby-checkin",
        locationName="重复打卡",
        # 约 22 米，低于 30 米领域阈值，但高于旧 15 米阈值。
        latitude=1.3523,
        longitude=103.8198,
    )
    with pytest.raises(AppException) as exc_info:
        service.create_checkin(db_session, "user-a", nearby_payload)

    assert exc_info.value.code == "CHECKIN_TOO_CLOSE"
    assert db_session.query(TravelObservation).count() == 1


def test_checkin_is_a_route_observation_and_nearby_automatic_sample_is_skipped(db_session: Session):
    """测试：打卡进入统一观察流，且服务端过滤附近自动 GPS 以覆盖多设备场景。"""
    _add_trip(db_session, uuid="trip-observations", user_uuid="user-a", status=2)
    checkin = service.create_checkin_observation(
        db_session,
        "user-a",
        CheckinCreateRequest(
            tripUuid="trip-observations",
            clientEventUuid="manual-checkin-1",
            locationName="鱼尾狮公园",
            latitude=1.2868,
            longitude=103.8545,
            trackingSegmentUuid="segment-1",
            checkedAt=datetime(2026, 9, 15, 4, 0, tzinfo=UTC),
        ),
    )
    result = service.sync_location_samples(
        db_session,
        "user-a",
        LocationSyncRequest(
            tripUuid="trip-observations",
            samples=[
                {
                    "clientUuid": "nearby-auto-sample",
                    "latitude": 1.28685,
                    "longitude": 103.8545,
                    "recordedAt": datetime(2026, 9, 15, 4, 1, tzinfo=UTC),
                },
                {
                    "clientUuid": "far-auto-sample",
                    "latitude": 1.2873,
                    "longitude": 103.8545,
                    "recordedAt": datetime(2026, 9, 15, 4, 2, tzinfo=UTC),
                },
            ],
        ),
    )

    observations = service.list_trip_observations(db_session, "user-a", "trip-observations")
    assert checkin.observation_type == "MANUAL_CHECKIN"
    assert result.accepted_count == 1
    assert result.skipped_count == 1
    assert [item.observation_type for item in observations] == ["MANUAL_CHECKIN", "AUTO_GPS"]
    assert observations[0].tracking_segment_uuid == "segment-1"


def test_checkin_event_key_is_idempotent(db_session: Session):
    """测试：用户因网络失败重试相同打卡事件时，服务端回传同一观察而不是新增一条。"""
    _add_trip(db_session, uuid="trip-checkin-retry", user_uuid="user-a", status=2)
    payload = CheckinCreateRequest(
        tripUuid="trip-checkin-retry",
        clientEventUuid="manual-checkin-retry",
        locationName="机场",
        latitude=1.3644,
        longitude=103.9915,
    )
    first = service.create_checkin_observation(db_session, "user-a", payload)
    second = service.create_checkin_observation(db_session, "user-a", payload)

    assert first.uuid == second.uuid
    assert db_session.query(TravelObservation).count() == 1
