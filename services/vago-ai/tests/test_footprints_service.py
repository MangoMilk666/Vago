from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.exceptions import AppException
from app.footprints import service
from app.footprints.models import TravelFootprint
from app.footprints.schemas import CheckinCreateRequest, CheckinUpdateRequest, LocationSyncRequest
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
    assert db_session.query(TravelFootprint).count() == 1
    locations = service.list_trip_locations(db_session, "user-a", "trip-a")
    assert len(locations) == 1
    assert locations[0].tracking_segment_uuid == "c5e49cc2-75c2-4d06-b87d-728b30b83b97"
    with pytest.raises(AppException) as exc_info:
        service.list_trip_locations(db_session, "user-b", "trip-a")
    assert exc_info.value.code == "TRIP_NOT_FOUND"


def test_agent_footprint_and_checkin_contexts_are_separated(db_session: Session):
    """测试：Agent 的 GPS 摘要与打卡摘要分开读取，避免无关事实一并注入。"""
    _add_trip(db_session, uuid="trip-agent-context", user_uuid="user-a", status=2)
    db_session.add_all([
        TravelFootprint(
            uuid="agent-auto", client_event_uuid="agent-auto-event", user_uuid="user-a",
            trip_uuid="trip-agent-context", footprint_type=service.AUTO_GPS,
            latitude=1.2800, longitude=103.8500, occurred_at=datetime(2026, 9, 27, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="agent-checkin", client_event_uuid="agent-checkin-event", user_uuid="user-a",
            trip_uuid="trip-agent-context", footprint_type=service.MANUAL_CHECKIN,
            latitude=1.2816, longitude=103.8636, location_name="滨海湾花园", note="傍晚散步",
            occurred_at=datetime(2026, 9, 27, 1, tzinfo=UTC),
        ),
    ])
    db_session.commit()

    footprint = service.get_agent_footprint_summary_by_trip(db_session, "user-a", "trip-agent-context")
    checkins = service.get_agent_checkins_by_trip(db_session, "user-a", "trip-agent-context")

    assert footprint == {"automaticSampleCount": 1}
    assert checkins["recentCheckins"][0]["locationName"] == "滨海湾花园"
    assert "recentCheckins" not in footprint
    assert "automaticSampleCount" not in checkins


def test_agent_recent_footprints_are_ordered_by_occurrence_and_limited(db_session: Session):
    """测试：recent 足迹和打卡按 Footprint 时间倒序读取，不依赖进行中 Trip。"""
    _add_trip(db_session, uuid="trip-older", user_uuid="user-a", status=3)
    _add_trip(db_session, uuid="trip-newer", user_uuid="user-a", status=1)
    db_session.add_all([
        TravelFootprint(
            uuid="older-auto", client_event_uuid="older-auto-event", user_uuid="user-a",
            trip_uuid="trip-older", footprint_type=service.AUTO_GPS,
            latitude=1.2800, longitude=103.8500, occurred_at=datetime(2026, 9, 20, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="newer-auto", client_event_uuid="newer-auto-event", user_uuid="user-a",
            trip_uuid="trip-newer", footprint_type=service.AUTO_GPS,
            latitude=1.2900, longitude=103.8600, occurred_at=datetime(2026, 9, 25, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="newer-checkin", client_event_uuid="newer-checkin-event", user_uuid="user-a",
            trip_uuid="trip-newer", footprint_type=service.MANUAL_CHECKIN,
            latitude=1.2910, longitude=103.8610, location_name="最近打卡", occurred_at=datetime(2026, 9, 26, tzinfo=UTC),
        ),
    ])
    db_session.commit()

    recent_footprints = service.get_agent_recent_footprint_summaries(db_session, "user-a", limit=1)
    recent_checkins = service.get_agent_recent_checkins(db_session, "user-a", limit=1)

    assert [item["tripUuid"] for item in recent_footprints] == ["trip-newer"]
    assert recent_footprints[0]["automaticSampleCount"] == 1
    assert recent_footprints[0]["manualCheckins"][0]["locationName"] == "最近打卡"
    assert recent_checkins == [{
        "tripUuid": "trip-newer", "tripTitle": "测试行程", "locationName": "最近打卡",
        "occurredAt": "2026-09-26T00:00:00", "note": None,
    }]


def test_agent_checkins_by_date_return_city_unverified_candidates(db_session: Session):
    """测试：城市缺少单条打卡归属字段时返回日期候选并明确未验证，不误收也不漏报。"""
    _add_trip(db_session, uuid="trip-tokyo", user_uuid="user-a", status=3)
    _add_trip(db_session, uuid="trip-kyoto", user_uuid="user-a", status=1)
    db_session.query(Trip).filter(Trip.uuid == "trip-tokyo").update({"title": "东京自由行", "destination": "东京"})
    db_session.query(Trip).filter(Trip.uuid == "trip-kyoto").update({"destination": "京都"})
    db_session.add_all([
        TravelFootprint(
            uuid=f"tokyo-{day.isoformat()}", client_event_uuid=f"tokyo-event-{day.isoformat()}", user_uuid="user-a",
            trip_uuid="trip-tokyo", footprint_type=service.MANUAL_CHECKIN,
            latitude=35.6, longitude=139.7,
            location_name="浅草寺" if day.day == 28 else f"东京地点{day.day}",
            occurred_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
        )
        for day in (date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1))
    ] + [
        TravelFootprint(
            uuid="kyoto-checkin", client_event_uuid="kyoto-event", user_uuid="user-a",
            trip_uuid="trip-kyoto", footprint_type=service.MANUAL_CHECKIN,
            latitude=35.0, longitude=135.7, location_name="京都车站",
            occurred_at=datetime(2026, 10, 2, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="tokyo-trip-kyoto-checkin", client_event_uuid="tokyo-trip-kyoto-event", user_uuid="user-a",
            trip_uuid="trip-tokyo", footprint_type=service.MANUAL_CHECKIN,
            latitude=35.0, longitude=135.7, location_name="京都车站",
            occurred_at=datetime(2026, 10, 3, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="tokyo-trip-unnamed-checkin", client_event_uuid="tokyo-trip-unnamed-event", user_uuid="user-a",
            trip_uuid="trip-tokyo", footprint_type=service.MANUAL_CHECKIN,
            latitude=35.0, longitude=135.7, location_name=None,
            occurred_at=datetime(2026, 10, 3, 1, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="tokyo-outside-week", client_event_uuid="tokyo-outside-event", user_uuid="user-a",
            trip_uuid="trip-tokyo", footprint_type=service.MANUAL_CHECKIN,
            latitude=35.6, longitude=139.7, location_name="东京周末", occurred_at=datetime(2026, 10, 5, tzinfo=UTC),
        ),
    ])
    db_session.commit()

    result = service.get_agent_checkins_by_date_range(
        db_session,
        "user-a",
        date(2026, 9, 28),
        date(2026, 10, 4),
        location_query="东京",
    )

    assert len(result["checkins"]) == 7
    names = [item["locationName"] for item in result["checkins"]]
    assert "浅草寺" in names
    assert names.count("京都车站") == 2
    assert "未命名地点" in names
    assert result["locationScopeVerified"] is False
    assert all(item["locationVerified"] is False for item in result["checkins"])
    assert "Trip 目的地只是行程声明" in result["groundingNote"]
    assert result["truncated"] is False


def test_agent_observation_date_range_marks_checkin_truncation_at_limit(db_session: Session):
    """测试：同一 Trip 内 20 条完整、21 条超限时正确返回地点列表截断状态。"""
    _add_trip(db_session, uuid="trip-checkin-limit", user_uuid="user-a", status=3)
    db_session.query(Trip).filter(Trip.uuid == "trip-checkin-limit").update({"title": "地点上限测试"})
    db_session.add_all([
        TravelFootprint(
            uuid=f"checkin-{day}-{index}",
            client_event_uuid=f"checkin-event-{day}-{index}",
            user_uuid="user-a",
            trip_uuid="trip-checkin-limit",
            footprint_type=service.MANUAL_CHECKIN,
            latitude=1.0,
            longitude=103.0,
            location_name=f"地点{index}",
            occurred_at=datetime(2026, 10, day, 8, index % 60, tzinfo=UTC),
        )
        for day, count in ((5, 20), (6, 21))
        for index in range(count)
    ])
    db_session.commit()

    complete = service.get_agent_footprints_by_date_range(
        db_session, "user-a", date(2026, 10, 5), date(2026, 10, 5),
    )
    truncated = service.get_agent_footprints_by_date_range(
        db_session, "user-a", date(2026, 10, 6), date(2026, 10, 6),
    )

    assert len(complete["trips"][0]["checkins"]) == 20
    assert complete["checkinsTruncated"] is False
    assert complete["truncated"] is False
    assert len(truncated["trips"][0]["checkins"]) == 20
    assert truncated["checkinsTruncated"] is True
    assert truncated["truncated"] is True
    assert "不能将当前列表表述为完整记录" in truncated["groundingNote"]


def test_agent_observation_date_range_returns_named_evidence_without_coordinates(db_session: Session):
    """测试：按日期汇总 GPS 数量和打卡地点，不向 Agent 暴露原始坐标。"""
    _add_trip(db_session, uuid="trip-footprint-date", user_uuid="user-a", status=3)
    _add_trip(db_session, uuid="trip-gps-only", user_uuid="user-a", status=3)
    db_session.query(Trip).filter(Trip.uuid == "trip-footprint-date").update({"title": "含打卡旅行"})
    db_session.query(Trip).filter(Trip.uuid == "trip-gps-only").update({"title": "仅 GPS 旅行"})
    db_session.add_all([
        TravelFootprint(
            uuid="date-auto-1", client_event_uuid="date-auto-event-1", user_uuid="user-a",
            trip_uuid="trip-footprint-date", footprint_type=service.AUTO_GPS,
            latitude=1.28, longitude=103.85, occurred_at=datetime(2026, 10, 5, 8, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="date-auto-2", client_event_uuid="date-auto-event-2", user_uuid="user-a",
            trip_uuid="trip-footprint-date", footprint_type=service.AUTO_GPS,
            latitude=1.29, longitude=103.86, occurred_at=datetime(2026, 10, 5, 9, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="date-checkin", client_event_uuid="date-checkin-event", user_uuid="user-a",
            trip_uuid="trip-footprint-date", footprint_type=service.MANUAL_CHECKIN,
            latitude=1.30, longitude=103.87, location_name="滨海湾花园",
            occurred_at=datetime(2026, 10, 5, 10, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="outside-auto", client_event_uuid="outside-auto-event", user_uuid="user-a",
            trip_uuid="trip-footprint-date", footprint_type=service.AUTO_GPS,
            latitude=1.31, longitude=103.88, occurred_at=datetime(2026, 10, 4, 23, tzinfo=UTC),
        ),
        TravelFootprint(
            uuid="gps-only-auto", client_event_uuid="gps-only-event", user_uuid="user-a",
            trip_uuid="trip-gps-only", footprint_type=service.AUTO_GPS,
            latitude=1.32, longitude=103.89, occurred_at=datetime(2026, 10, 5, 11, tzinfo=UTC),
        ),
    ])
    db_session.commit()

    result = service.get_agent_footprints_by_date_range(
        db_session, "user-a", date(2026, 10, 5), date(2026, 10, 5),
    )

    trip_summaries = {item["tripTitle"]: item for item in result["trips"]}
    assert trip_summaries["含打卡旅行"]["automaticSampleCount"] == 2
    assert trip_summaries["含打卡旅行"]["checkins"][0]["locationName"] == "滨海湾花园"
    assert trip_summaries["仅 GPS 旅行"]["automaticSampleCount"] == 1
    assert trip_summaries["仅 GPS 旅行"]["checkins"] == []
    assert "groundingNote" in result
    assert "latitude" not in str(result)
    assert "longitude" not in str(result)

    empty = service.get_agent_footprints_by_date_range(
        db_session, "user-a", date(2026, 10, 6), date(2026, 10, 6),
    )
    assert empty["trips"] == []


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
    assert db_session.query(TravelFootprint).count() == 1
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
    assert db_session.query(TravelFootprint).count() == 1


def test_checkin_is_a_route_observation_and_nearby_automatic_sample_is_skipped(db_session: Session):
    """测试：打卡进入统一足迹流，且服务端过滤附近自动 GPS 以覆盖多设备场景。"""
    _add_trip(db_session, uuid="trip-footprints", user_uuid="user-a", status=2)
    checkin = service.create_checkin_footprint(
        db_session,
        "user-a",
        CheckinCreateRequest(
            tripUuid="trip-footprints",
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
            tripUuid="trip-footprints",
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

    footprints = service.list_trip_footprints(db_session, "user-a", "trip-footprints")
    assert checkin.footprint_type == "MANUAL_CHECKIN"
    assert result.accepted_count == 1
    assert result.skipped_count == 1
    assert [item.footprint_type for item in footprints] == ["MANUAL_CHECKIN", "AUTO_GPS"]
    assert footprints[0].tracking_segment_uuid == "segment-1"


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
    first = service.create_checkin_footprint(db_session, "user-a", payload)
    second = service.create_checkin_footprint(db_session, "user-a", payload)

    assert first.uuid == second.uuid
    assert db_session.query(TravelFootprint).count() == 1


def test_checkin_update_only_changes_user_text_for_in_progress_trip(db_session: Session):
    """测试：编辑打卡只能改名称与备注，坐标和发生时间仍是不可变旅行事实。"""
    _add_trip(db_session, uuid="trip-checkin-edit", user_uuid="user-a", status=2)
    created = service.create_checkin_footprint(
        db_session,
        "user-a",
        CheckinCreateRequest(
            tripUuid="trip-checkin-edit",
            clientEventUuid="manual-checkin-edit",
            locationName="旧名称",
            latitude=1.3521,
            longitude=103.8198,
            note="旧备注",
            checkedAt=datetime(2026, 9, 15, 4, 0, tzinfo=UTC),
        ),
    )
    updated = service.update_checkin_footprint(
        db_session,
        "user-a",
        created.uuid,
        CheckinUpdateRequest(locationName="新名称", note=""),
    )

    assert updated.location_name == "新名称"
    assert updated.note is None
    assert updated.latitude == 1.3521
    assert updated.occurred_at == created.occurred_at

    db_session.query(Trip).filter(Trip.uuid == "trip-checkin-edit").update({"status": 3})
    db_session.commit()
    with pytest.raises(AppException) as exc_info:
        service.update_checkin_footprint(
            db_session,
            "user-a",
            created.uuid,
            CheckinUpdateRequest(locationName="不应修改"),
        )
    assert exc_info.value.code == "TRIP_NOT_IN_PROGRESS"
