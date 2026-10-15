"""旅行足迹领域服务：校验行程归属后持久化移动端事实记录。"""

from datetime import UTC, date, datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.footprints.models import TravelFootprint
from app.footprints.schemas import (
    CheckinCreateRequest,
    CheckinResponse,
    CheckinUpdateRequest,
    LocationSampleResponse,
    LocationSyncRequest,
    LocationSyncResponse,
    TravelFootprintResponse,
)
from app.travel.models import Trip, utc_now_naive


AUTO_GPS = "AUTO_GPS"
MANUAL_CHECKIN = "MANUAL_CHECKIN"
# 自动 GPS 贴近用户主动确认地点时没有额外旅行价值，因此避免写入冗余样本。
MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS = 15.0
# 两次用户主动打卡的阈值更大，减少 GPS 漂移造成的重复地点记录。
MINIMUM_CHECKIN_DISTANCE_METERS = 30.0
AGENT_MAX_RECENT_FOOTPRINTS = 5
AGENT_MAX_DATE_RANGE_FOOTPRINTS = 20


def _new_uuid() -> str:
    """生成与现有业务表一致的 32 位 UUID。"""
    return uuid4().hex


def _get_owned_trip(db: Session, user_uuid: str, trip_uuid: str) -> Trip:
    """读取当前用户未删除的正式行程。
    若无法读取抛出异常"""
    trip = db.scalar(
        select(Trip).where(
            Trip.uuid == trip_uuid,
            Trip.user_uuid == user_uuid,
            Trip.deleted_at.is_(None),
        )
    )
    # 分支条件：行程不存在、已删除或不属于当前用户时，统一不暴露其存在状态。
    if trip is None:
        raise AppException("行程不存在或无权访问", status_code=404, code="TRIP_NOT_FOUND")
    return trip


def _distance_meters(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """使用 Haversine 公式计算两组 WGS-84 坐标间的近似地表距离。"""
    earth_radius_meters = 6_371_000
    delta_latitude = radians(latitude_b - latitude_a)
    delta_longitude = radians(longitude_b - longitude_a)
    haversine = sin(delta_latitude / 2) ** 2 + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(delta_longitude / 2) ** 2
    return 2 * earth_radius_meters * asin(sqrt(haversine))


def _to_footprint_response(footprint: TravelFootprint) -> TravelFootprintResponse:
    """将 ORM 事实转换为统一的TravelFootprintResponse API 对象。"""
    return TravelFootprintResponse(
        uuid=footprint.uuid,
        clientEventUuid=footprint.client_event_uuid,
        tripUuid=footprint.trip_uuid,
        footprintType=footprint.footprint_type,
        observationType=footprint.footprint_type,
        latitude=footprint.latitude,
        longitude=footprint.longitude,
        accuracyM=footprint.accuracy_m,
        speedMps=footprint.speed_mps,
        trackingSegmentUuid=footprint.tracking_segment_uuid,
        locationName=footprint.location_name,
        note=footprint.note,
        occurredAt=footprint.occurred_at,
    )


def _to_location_response(footprint: TravelFootprint) -> LocationSampleResponse:
    """为旧 locations 读取入口投影自动 GPS 字段。"""
    return LocationSampleResponse(
        uuid=footprint.uuid,
        clientUuid=footprint.client_event_uuid,
        latitude=footprint.latitude,
        longitude=footprint.longitude,
        accuracyM=footprint.accuracy_m,
        speedMps=footprint.speed_mps,
        trackingSegmentUuid=footprint.tracking_segment_uuid,
        recordedAt=footprint.occurred_at,
    )


def _to_checkin_response(footprint: TravelFootprint) -> CheckinResponse:
    """为旧 checkins 读取入口投影用户主动打卡字段。"""
    return CheckinResponse(
        uuid=footprint.uuid,
        tripUuid=footprint.trip_uuid,
        locationName=footprint.location_name or "未命名地点",
        latitude=footprint.latitude,
        longitude=footprint.longitude,
        note=footprint.note,
        checkedAt=footprint.occurred_at,
    )


def sync_location_samples(
    db: Session,
    user_uuid: str,
    payload: LocationSyncRequest,
) -> LocationSyncResponse:
    """批量写入自动 GPS 样本；按客户端 UUID 幂等并避开已有打卡。"""
    _get_owned_trip(db, user_uuid, payload.trip_uuid)
    client_uuids = [sample.client_uuid for sample in payload.samples]
    # 已经写入db的数据的client_uuid
    existing_uuids = set(
        db.scalars(
            select(TravelFootprint.client_event_uuid).where(
                TravelFootprint.user_uuid == user_uuid,
                TravelFootprint.client_event_uuid.in_(client_uuids),
            )
        ).all()
    )
    existing_before_request = existing_uuids.copy()
    # 同一批次只读取一次已有打卡；当前 MVP 的单个行程打卡数量有限，无需提前引入 GIS 查询。
    checkins = db.scalars(
        select(TravelFootprint).where(
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.trip_uuid == payload.trip_uuid,
            TravelFootprint.footprint_type == MANUAL_CHECKIN,
        )
    ).all()
    new_rows: list[TravelFootprint] = []
    skipped_client_uuids: set[str] = set()
    for sample in payload.samples:
        # 分支条件：客户端样本已被成功接收过时,不再写入。
        if sample.client_uuid in existing_uuids:
            continue
        # 分支条件：自动采样距已有用户手动打卡点不足 15 米时不再新增冗余 GPS 事实。
        if any(
            _distance_meters(sample.latitude, sample.longitude, checkin.latitude, checkin.longitude)
            < MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS
            for checkin in checkins
        ):
            skipped_client_uuids.add(sample.client_uuid)
            continue
        new_rows.append(
            TravelFootprint(
                uuid=_new_uuid(),
                client_event_uuid=sample.client_uuid,
                user_uuid=user_uuid,
                trip_uuid=payload.trip_uuid,
                footprint_type=AUTO_GPS,
                latitude=sample.latitude,
                longitude=sample.longitude,
                accuracy_m=sample.accuracy_m,
                speed_mps=sample.speed_mps,
                tracking_segment_uuid=sample.tracking_segment_uuid,
                location_name=None,
                note=None,
                occurred_at=sample.recorded_at.astimezone(UTC).replace(tzinfo=None),
            )
        )
        existing_uuids.add(sample.client_uuid)
    if new_rows:
        db.add_all(new_rows)
        try:
            db.commit()
        except IntegrityError:
            # 分支条件：并发设备或重试请求先写入同一幂等键时，回滚并复查后返回可安全删除队列的结果。
            db.rollback()
            persisted_uuids = set(
                db.scalars(
                    select(TravelFootprint.client_event_uuid).where(
                        TravelFootprint.user_uuid == user_uuid,
                        TravelFootprint.client_event_uuid.in_(client_uuids),
                    )
                ).all()
            )
            expected_uuids = set(client_uuids) - skipped_client_uuids
            if not expected_uuids.issubset(persisted_uuids):
                raise
            accepted_count = len((persisted_uuids - existing_before_request) & expected_uuids)
            return LocationSyncResponse(
                acceptedCount=accepted_count,
                duplicateCount=len(payload.samples) - accepted_count - len(skipped_client_uuids),
                skippedCount=len(skipped_client_uuids),
            )
    return LocationSyncResponse(
        acceptedCount=len(new_rows),
        duplicateCount=len(payload.samples) - len(new_rows) - len(skipped_client_uuids),
        skippedCount=len(skipped_client_uuids),
    )


def list_trip_footprints(db: Session, user_uuid: str, trip_uuid: str) -> list[TravelFootprintResponse]:
    """按实际发生时间读取一个行程的统一足迹点位流。"""
    _get_owned_trip(db, user_uuid, trip_uuid)
    footprints = db.scalars(
        select(TravelFootprint)
        .where(TravelFootprint.user_uuid == user_uuid, TravelFootprint.trip_uuid == trip_uuid)
        .order_by(TravelFootprint.occurred_at.asc(), TravelFootprint.uuid.asc())
    ).all()
    return [_to_footprint_response(footprint) for footprint in footprints]


def get_agent_footprint_summary_by_trip(db: Session, user_uuid: str, trip_uuid: str) -> dict:
    """读取当前行程的自动 GPS 摘要，不向 Agent 暴露原始坐标或打卡文本。"""
    _get_owned_trip(db, user_uuid, trip_uuid)
    automatic_sample_count = db.scalar(
        select(func.count())
        .select_from(TravelFootprint)
        .where(
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.trip_uuid == trip_uuid,
            TravelFootprint.footprint_type == AUTO_GPS,
        )
    ) or 0
    return {"automaticSampleCount": automatic_sample_count}


def get_agent_checkins_by_trip(db: Session, user_uuid: str, trip_uuid: str, limit: int = 5) -> dict:
    """读取当前行程的有限手动打卡摘要，不查询自动 GPS 采样点。"""
    _get_owned_trip(db, user_uuid, trip_uuid)
    safe_limit = _agent_recent_limit(limit)
    checkins = db.scalars(
        select(TravelFootprint)
        .where(
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.trip_uuid == trip_uuid,
            TravelFootprint.footprint_type == MANUAL_CHECKIN,
        )
        .order_by(TravelFootprint.occurred_at.desc())
        .limit(safe_limit)
    ).all()
    return {
        "recentCheckins": [
            {
                "locationName": item.location_name or "未命名地点",
                "occurredAt": item.occurred_at.isoformat(),
                "note": (item.note or "")[:300] or None,
            }
            for item in checkins
        ],
    }


def get_agent_recent_footprint_summaries(db: Session, user_uuid: str, limit: int = 3) -> list[dict]:
    """按 Footprint 发生时间倒序读取最近有足迹的有限 Trip 摘要。"""
    safe_limit = _agent_recent_limit(limit)
    latest_footprint_by_trip = (
        select(
            TravelFootprint.trip_uuid.label("trip_uuid"),
            func.max(TravelFootprint.occurred_at).label("latest_footprint_at"),
        )
        .where(TravelFootprint.user_uuid == user_uuid)
        .group_by(TravelFootprint.trip_uuid)
        .subquery()
    )
    rows = db.execute(
        select(Trip, latest_footprint_by_trip.c.latest_footprint_at)
        .join(latest_footprint_by_trip, latest_footprint_by_trip.c.trip_uuid == Trip.uuid)
        .where(
            Trip.user_uuid == user_uuid,
            Trip.deleted_at.is_(None),
        )
        .order_by(latest_footprint_by_trip.c.latest_footprint_at.desc(), Trip.uuid.desc())
        .limit(safe_limit)
    ).all()
    summaries: list[dict] = []
    for trip, latest_footprint_at in rows:
        checkins = get_agent_checkins_by_trip(db, user_uuid, trip.uuid, limit=safe_limit)["recentCheckins"]
        summaries.append({
            "tripUuid": trip.uuid,
            "tripTitle": trip.title,
            "destination": trip.destination,
            "latestFootprintAt": latest_footprint_at.isoformat(),
            "manualCheckins": [
                {"locationName": item["locationName"], "occurredAt": item["occurredAt"]}
                for item in checkins
            ],
            **get_agent_footprint_summary_by_trip(db, user_uuid, trip.uuid),
        })
    return summaries


def get_agent_recent_checkins(db: Session, user_uuid: str, limit: int = 3) -> list[dict]:
    """按发生时间倒序读取最近手动打卡，limit 不依赖当前进行中 Trip。"""
    safe_limit = _agent_recent_limit(limit)
    rows = db.execute(
        select(TravelFootprint, Trip)
        .join(Trip, Trip.uuid == TravelFootprint.trip_uuid)
        .where(
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.footprint_type == MANUAL_CHECKIN,
            Trip.user_uuid == user_uuid,
            Trip.deleted_at.is_(None),
        )
        .order_by(TravelFootprint.occurred_at.desc(), TravelFootprint.uuid.desc())
        .limit(safe_limit)
    ).all()
    return [
        {
            "tripUuid": trip.uuid,
            "tripTitle": trip.title,
            "locationName": footprint.location_name or "未命名地点",
            "occurredAt": footprint.occurred_at.isoformat(),
            "note": (footprint.note or "")[:300] or None,
        }
        for footprint, trip in rows
    ]


def get_agent_checkins_by_date_range(
    db: Session,
    user_uuid: str,
    start_date: date,
    end_date: date,
    *,
    location_query: str | None = None,
    limit: int = AGENT_MAX_DATE_RANGE_FOOTPRINTS,
) -> dict:
    """读取日期范围内的有限打卡候选；没有单条城市字段时不声称地点已验证。"""
    start_at = datetime.combine(start_date, time.min)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min)
    safe_limit = max(1, min(limit, AGENT_MAX_DATE_RANGE_FOOTPRINTS))
    statement = (
        select(TravelFootprint, Trip)
        .join(Trip, Trip.uuid == TravelFootprint.trip_uuid)
        .where(
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.footprint_type == MANUAL_CHECKIN,
            TravelFootprint.occurred_at >= start_at,
            TravelFootprint.occurred_at < end_at,
            Trip.user_uuid == user_uuid,
            Trip.deleted_at.is_(None),
        )
    )
    normalized_location = (location_query or "").strip()
    rows = db.execute(
        statement.order_by(TravelFootprint.occurred_at.desc(), TravelFootprint.uuid.desc())
        .limit(safe_limit + 1)
    ).all()
    return {
        "dateRange": {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
        "locationQuery": normalized_location or None,
        "locationScopeVerified": False if normalized_location else None,
        "checkins": [
            {
                "tripTitle": trip.title,
                "tripDestinationDeclared": trip.destination,
                "locationName": footprint.location_name or "未命名地点",
                "occurredAt": footprint.occurred_at.isoformat(),
                "locationVerified": False if normalized_location else None,
            }
            for footprint, trip in rows[:safe_limit]
        ],
        "truncated": len(rows) > safe_limit,
        "groundingNote": (
            "打卡按日期范围返回候选记录；系统没有逐条打卡的城市归属，不能确认这些记录位于所询问的城市。"
            "Trip 目的地只是行程声明，不是单条打卡的位置证明。"
            if normalized_location else "结果仅按日期范围筛选，地点名称来自用户打卡记录。"
        ),
    }


def get_agent_footprints_by_date_range(
    db: Session,
    user_uuid: str,
    start_date: date,
    end_date: date,
    *,
    limit: int = AGENT_MAX_DATE_RANGE_FOOTPRINTS,
) -> dict:
    """按明确日期汇总 Trip、GPS 数量与命名打卡，不向 Agent 暴露原始坐标。"""
    start_at = datetime.combine(start_date, time.min)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min)
    safe_limit = max(1, min(limit, AGENT_MAX_DATE_RANGE_FOOTPRINTS))
    trip_rows = db.execute(
        select(
            Trip.uuid,
            Trip.title,
            Trip.destination,
            func.sum(case((TravelFootprint.footprint_type == AUTO_GPS, 1), else_=0)).label("automatic_sample_count"),
        )
        .join(TravelFootprint, TravelFootprint.trip_uuid == Trip.uuid)
        .where(
            Trip.user_uuid == user_uuid,
            Trip.deleted_at.is_(None),
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.occurred_at >= start_at,
            TravelFootprint.occurred_at < end_at,
        )
        .group_by(Trip.uuid, Trip.title, Trip.destination)
        .order_by(func.max(TravelFootprint.occurred_at).desc(), Trip.uuid.desc())
        .limit(safe_limit + 1)
    ).all()
    trips = trip_rows[:safe_limit]
    trip_uuids = [row.uuid for row in trips]
    checkin_rows = []
    if trip_uuids:
        # 如果范围内存在 GPS 足迹，只附带少量命名打卡作为地点证据，不传递 GPS 坐标。
        checkin_rows = db.execute(
            select(TravelFootprint, Trip.uuid)
            .join(Trip, Trip.uuid == TravelFootprint.trip_uuid)
            .where(
                TravelFootprint.user_uuid == user_uuid,
                TravelFootprint.trip_uuid.in_(trip_uuids),
                TravelFootprint.footprint_type == MANUAL_CHECKIN,
                TravelFootprint.occurred_at >= start_at,
                TravelFootprint.occurred_at < end_at,
                Trip.user_uuid == user_uuid,
                Trip.deleted_at.is_(None),
            )
            .order_by(TravelFootprint.occurred_at.desc(), TravelFootprint.uuid.desc())
            .limit(safe_limit + 1)
        ).all()
    checkins_truncated = len(checkin_rows) > safe_limit
    checkins_by_trip: dict[str, list[dict[str, str | None]]] = {trip_uuid: [] for trip_uuid in trip_uuids}
    for footprint, trip_uuid in checkin_rows[:safe_limit]:
        checkins_by_trip[trip_uuid].append({
            "locationName": footprint.location_name or "未命名地点",
            "occurredAt": footprint.occurred_at.isoformat(),
        })
    trips_truncated = len(trip_rows) > safe_limit
    return {
        "dateRange": {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
        "trips": [
            {
                "tripTitle": row.title,
                "destination": row.destination,
                "automaticSampleCount": int(row.automatic_sample_count or 0),
                "checkins": checkins_by_trip[row.uuid],
            }
            for row in trips
        ],
        "truncated": trips_truncated or checkins_truncated,
        "tripsTruncated": trips_truncated,
        "checkinsTruncated": checkins_truncated,
        "groundingNote": "GPS 采样数量不能证明具体到访地点；行程目的地是行程声明，不等于实际到访；确认到访的地点名称仅来自手动打卡。若结果已截断，不能将当前列表表述为完整记录。",
    }


def get_agent_footprint_context(db: Session, user_uuid: str, trip_uuid: str) -> dict:
    """兼容既有 Personal Context 预览，合并两个已拆分的 Live Context 摘要。"""
    return {
        **get_agent_footprint_summary_by_trip(db, user_uuid, trip_uuid),
        **get_agent_checkins_by_trip(db, user_uuid, trip_uuid),
    }


def _agent_recent_limit(value: int) -> int:
    """将 recent 查询的 limit 限制在 1 至配置上限，防止 Agent 无界读取事实。"""
    # 如果调用方传入非正数或过大值，统一收敛到允许的安全范围。
    return max(1, min(value, AGENT_MAX_RECENT_FOOTPRINTS))


def list_trip_locations(db: Session, user_uuid: str, trip_uuid: str) -> list[LocationSampleResponse]:
    """兼容旧入口：只读取自动 GPS 足迹点位。"""
    footprints = [
        footprint
        for footprint in list_trip_footprints(db, user_uuid, trip_uuid)
        if footprint.footprint_type == AUTO_GPS
    ]
    # 统一响应已脱离 ORM，此处保留旧字段名供未升级客户端读取。
    return [
        LocationSampleResponse(
            uuid=footprint.uuid,
            clientUuid=footprint.client_event_uuid,
            latitude=footprint.latitude,
            longitude=footprint.longitude,
            accuracyM=footprint.accuracy_m,
            speedMps=footprint.speed_mps,
            trackingSegmentUuid=footprint.tracking_segment_uuid,
            recordedAt=footprint.occurred_at,
        )
        for footprint in footprints
    ]


def list_trip_checkins(db: Session, user_uuid: str, trip_uuid: str) -> list[CheckinResponse]:
    """兼容旧入口：只读取用户主动打卡点位。"""
    footprints = [
        footprint
        for footprint in list_trip_footprints(db, user_uuid, trip_uuid)
        if footprint.footprint_type == MANUAL_CHECKIN
    ]
    return [
        CheckinResponse(
            uuid=footprint.uuid,
            tripUuid=footprint.trip_uuid,
            locationName=footprint.location_name or "未命名地点",
            latitude=footprint.latitude,
            longitude=footprint.longitude,
            note=footprint.note,
            checkedAt=footprint.occurred_at,
        )
        for footprint in footprints
    ]


def create_checkin_footprint(db: Session, user_uuid: str, payload: CheckinCreateRequest) -> TravelFootprintResponse:
    """为用户选定的自有行程新增一条用户主动确认的手动打卡足迹。"""
    trip = _get_owned_trip(db, user_uuid, payload.trip_uuid)
    client_event_uuid = payload.client_event_uuid or _new_uuid()
    existing_event = db.scalar(
        select(TravelFootprint).where(
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.client_event_uuid == client_event_uuid,
        )
    )
    # 分支条件：同一客户端事件已经成功写入时直接回传原事实，防止网络重试产生重复打卡。
    if existing_event is not None:
        if existing_event.trip_uuid != trip.uuid or existing_event.footprint_type != MANUAL_CHECKIN:
            raise AppException("打卡事件键与已有记录冲突", status_code=409, code="CHECKIN_EVENT_CONFLICT")
        return _to_footprint_response(existing_event)
    existing_checkins = db.scalars(
        select(TravelFootprint).where(
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.trip_uuid == trip.uuid,
            TravelFootprint.footprint_type == MANUAL_CHECKIN,
        )
    ).all()
    # 分支条件：同一行程已有 30 米内用户打卡时拒绝创建；自动 GPS 点不参与此限制。
    if any(
        _distance_meters(payload.latitude, payload.longitude, checkin.latitude, checkin.longitude) < MINIMUM_CHECKIN_DISTANCE_METERS
        for checkin in existing_checkins
    ):
        raise AppException("和其他打卡点太近啦，请换个位置重试", status_code=409, code="CHECKIN_TOO_CLOSE")
    checked_at = payload.checked_at or datetime.now(UTC)
    checkin = TravelFootprint(
        uuid=_new_uuid(),
        client_event_uuid=client_event_uuid,
        user_uuid=user_uuid,
        trip_uuid=trip.uuid,
        footprint_type=MANUAL_CHECKIN,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=None,
        speed_mps=None,
        tracking_segment_uuid=payload.tracking_segment_uuid,
        location_name=payload.location_name,
        note=payload.note,
        occurred_at=checked_at.astimezone(UTC).replace(tzinfo=None),
        created_at=utc_now_naive(),
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return _to_footprint_response(checkin)


def create_checkin(db: Session, user_uuid: str, payload: CheckinCreateRequest) -> CheckinResponse:
    """兼容旧 POST 入口：返回传统打卡字段，底层仍写入统一足迹表。"""
    footprint = create_checkin_footprint(db, user_uuid, payload)
    return CheckinResponse(
        uuid=footprint.uuid,
        tripUuid=footprint.trip_uuid,
        locationName=footprint.location_name or "未命名地点",
        latitude=footprint.latitude,
        longitude=footprint.longitude,
        note=footprint.note,
        checkedAt=footprint.occurred_at,
    )


def update_checkin_footprint(
    db: Session,
    user_uuid: str,
    footprint_uuid: str,
    payload: CheckinUpdateRequest,
) -> TravelFootprintResponse:
    """更新用户主动打卡的名称与备注，不改写空间与时间事实。"""
    checkin = db.scalar(
        select(TravelFootprint).where(
            TravelFootprint.uuid == footprint_uuid,
            TravelFootprint.user_uuid == user_uuid,
            TravelFootprint.footprint_type == MANUAL_CHECKIN,
        )
    )
    # 分支条件：非本人的记录、自动 GPS 或不存在的 UUID 都不暴露内部差异。
    if checkin is None:
        raise AppException("打卡不存在或无权访问", status_code=404, code="CHECKIN_NOT_FOUND")
    _get_owned_trip(db, user_uuid, checkin.trip_uuid)
    checkin.location_name = payload.location_name
    checkin.note = payload.note.strip() or None
    db.commit()
    db.refresh(checkin)
    return _to_footprint_response(checkin)
