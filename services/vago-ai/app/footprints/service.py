"""旅行空间观察领域服务：校验行程归属后持久化移动端事实记录。"""

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.footprints.models import TravelObservation
from app.footprints.schemas import (
    CheckinCreateRequest,
    CheckinResponse,
    CheckinUpdateRequest,
    LocationSampleResponse,
    LocationSyncRequest,
    LocationSyncResponse,
    TravelObservationResponse,
)
from app.travel.models import Trip, utc_now_naive
from app.travel.service import TRIP_STATUS_IN_PROGRESS


AUTO_GPS = "AUTO_GPS"
MANUAL_CHECKIN = "MANUAL_CHECKIN"
# 自动 GPS 贴近用户主动确认地点时没有额外旅行价值，因此避免写入冗余样本。
MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS = 15.0
# 两次用户主动打卡的阈值更大，减少 GPS 漂移造成的重复地点记录。
MINIMUM_CHECKIN_DISTANCE_METERS = 30.0


def _new_uuid() -> str:
    """生成与现有业务表一致的 32 位 UUID。"""
    return uuid4().hex


def _get_owned_trip(db: Session, user_uuid: str, trip_uuid: str) -> Trip:
    """读取当前用户未删除的正式行程。"""
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


def _to_observation_response(observation: TravelObservation) -> TravelObservationResponse:
    """将 ORM 事实转换为统一观察 API 契约。"""
    return TravelObservationResponse(
        uuid=observation.uuid,
        clientEventUuid=observation.client_event_uuid,
        tripUuid=observation.trip_uuid,
        observationType=observation.observation_type,
        latitude=observation.latitude,
        longitude=observation.longitude,
        accuracyM=observation.accuracy_m,
        speedMps=observation.speed_mps,
        trackingSegmentUuid=observation.tracking_segment_uuid,
        locationName=observation.location_name,
        note=observation.note,
        occurredAt=observation.occurred_at,
    )


def _to_location_response(observation: TravelObservation) -> LocationSampleResponse:
    """为旧 locations 读取入口投影自动 GPS 字段。"""
    return LocationSampleResponse(
        uuid=observation.uuid,
        clientUuid=observation.client_event_uuid,
        latitude=observation.latitude,
        longitude=observation.longitude,
        accuracyM=observation.accuracy_m,
        speedMps=observation.speed_mps,
        trackingSegmentUuid=observation.tracking_segment_uuid,
        recordedAt=observation.occurred_at,
    )


def _to_checkin_response(observation: TravelObservation) -> CheckinResponse:
    """为旧 checkins 读取入口投影用户主动打卡字段。"""
    return CheckinResponse(
        uuid=observation.uuid,
        tripUuid=observation.trip_uuid,
        locationName=observation.location_name or "未命名地点",
        latitude=observation.latitude,
        longitude=observation.longitude,
        note=observation.note,
        checkedAt=observation.occurred_at,
    )


def sync_location_samples(
    db: Session,
    user_uuid: str,
    payload: LocationSyncRequest,
) -> LocationSyncResponse:
    """批量写入自动 GPS 样本；按客户端 UUID 幂等并避开已有打卡。"""
    _get_owned_trip(db, user_uuid, payload.trip_uuid)
    client_uuids = [sample.client_uuid for sample in payload.samples]
    existing_uuids = set(
        db.scalars(
            select(TravelObservation.client_event_uuid).where(
                TravelObservation.user_uuid == user_uuid,
                TravelObservation.client_event_uuid.in_(client_uuids),
            )
        ).all()
    )
    existing_before_request = existing_uuids.copy()
    # 同一批次只读取一次已有打卡；当前 MVP 的单个行程打卡数量有限，无需提前引入 GIS 查询。
    checkins = db.scalars(
        select(TravelObservation).where(
            TravelObservation.user_uuid == user_uuid,
            TravelObservation.trip_uuid == payload.trip_uuid,
            TravelObservation.observation_type == MANUAL_CHECKIN,
        )
    ).all()
    new_rows: list[TravelObservation] = []
    skipped_client_uuids: set[str] = set()
    for sample in payload.samples:
        # 分支条件：客户端样本已被成功接收过时,不再写入，让移动端可安全重试整批数据。
        if sample.client_uuid in existing_uuids:
            continue
        # 分支条件：自动采样距已有用户打卡不足 15 米时不再新增冗余 GPS 事实。
        if any(
            _distance_meters(sample.latitude, sample.longitude, checkin.latitude, checkin.longitude)
            < MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS
            for checkin in checkins
        ):
            skipped_client_uuids.add(sample.client_uuid)
            continue
        new_rows.append(
            TravelObservation(
                uuid=_new_uuid(),
                client_event_uuid=sample.client_uuid,
                user_uuid=user_uuid,
                trip_uuid=payload.trip_uuid,
                observation_type=AUTO_GPS,
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
                    select(TravelObservation.client_event_uuid).where(
                        TravelObservation.user_uuid == user_uuid,
                        TravelObservation.client_event_uuid.in_(client_uuids),
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


def list_trip_observations(db: Session, user_uuid: str, trip_uuid: str) -> list[TravelObservationResponse]:
    """按实际发生时间读取一个行程的统一空间观察流。"""
    _get_owned_trip(db, user_uuid, trip_uuid)
    observations = db.scalars(
        select(TravelObservation)
        .where(TravelObservation.user_uuid == user_uuid, TravelObservation.trip_uuid == trip_uuid)
        .order_by(TravelObservation.occurred_at.asc(), TravelObservation.uuid.asc())
    ).all()
    return [_to_observation_response(observation) for observation in observations]


def list_trip_locations(db: Session, user_uuid: str, trip_uuid: str) -> list[LocationSampleResponse]:
    """兼容旧入口：只读取自动 GPS 观察。"""
    observations = [
        observation
        for observation in list_trip_observations(db, user_uuid, trip_uuid)
        if observation.observation_type == AUTO_GPS
    ]
    # 统一响应已脱离 ORM，此处保留旧字段名供未升级客户端读取。
    return [
        LocationSampleResponse(
            uuid=observation.uuid,
            clientUuid=observation.client_event_uuid,
            latitude=observation.latitude,
            longitude=observation.longitude,
            accuracyM=observation.accuracy_m,
            speedMps=observation.speed_mps,
            trackingSegmentUuid=observation.tracking_segment_uuid,
            recordedAt=observation.occurred_at,
        )
        for observation in observations
    ]


def list_trip_checkins(db: Session, user_uuid: str, trip_uuid: str) -> list[CheckinResponse]:
    """兼容旧入口：只读取用户主动打卡观察。"""
    observations = [
        observation
        for observation in list_trip_observations(db, user_uuid, trip_uuid)
        if observation.observation_type == MANUAL_CHECKIN
    ]
    return [
        CheckinResponse(
            uuid=observation.uuid,
            tripUuid=observation.trip_uuid,
            locationName=observation.location_name or "未命名地点",
            latitude=observation.latitude,
            longitude=observation.longitude,
            note=observation.note,
            checkedAt=observation.occurred_at,
        )
        for observation in observations
    ]


def create_checkin_observation(db: Session, user_uuid: str, payload: CheckinCreateRequest) -> TravelObservationResponse:
    """为进行中的行程新增一条用户主动确认的空间观察。"""
    trip = _get_owned_trip(db, user_uuid, payload.trip_uuid)
    if trip.status != TRIP_STATUS_IN_PROGRESS:
        raise AppException("仅进行中的行程可以打卡", status_code=409, code="TRIP_NOT_IN_PROGRESS")
    client_event_uuid = payload.client_event_uuid or _new_uuid()
    existing_event = db.scalar(
        select(TravelObservation).where(
            TravelObservation.user_uuid == user_uuid,
            TravelObservation.client_event_uuid == client_event_uuid,
        )
    )
    # 分支条件：同一客户端事件已经成功写入时直接回传原事实，防止网络重试产生重复打卡。
    if existing_event is not None:
        if existing_event.trip_uuid != trip.uuid or existing_event.observation_type != MANUAL_CHECKIN:
            raise AppException("打卡事件键与已有记录冲突", status_code=409, code="CHECKIN_EVENT_CONFLICT")
        return _to_observation_response(existing_event)
    existing_checkins = db.scalars(
        select(TravelObservation).where(
            TravelObservation.user_uuid == user_uuid,
            TravelObservation.trip_uuid == trip.uuid,
            TravelObservation.observation_type == MANUAL_CHECKIN,
        )
    ).all()
    # 分支条件：同一行程已有 30 米内用户打卡时拒绝创建；自动 GPS 点不参与此限制。
    if any(
        _distance_meters(payload.latitude, payload.longitude, checkin.latitude, checkin.longitude) < MINIMUM_CHECKIN_DISTANCE_METERS
        for checkin in existing_checkins
    ):
        raise AppException("和其他打卡点太近啦，请换个位置重试", status_code=409, code="CHECKIN_TOO_CLOSE")
    checked_at = payload.checked_at or datetime.now(UTC)
    checkin = TravelObservation(
        uuid=_new_uuid(),
        client_event_uuid=client_event_uuid,
        user_uuid=user_uuid,
        trip_uuid=trip.uuid,
        observation_type=MANUAL_CHECKIN,
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
    return _to_observation_response(checkin)


def create_checkin(db: Session, user_uuid: str, payload: CheckinCreateRequest) -> CheckinResponse:
    """兼容旧 POST 入口：返回传统打卡字段，但底层写入统一观察表。"""
    observation = create_checkin_observation(db, user_uuid, payload)
    return CheckinResponse(
        uuid=observation.uuid,
        tripUuid=observation.trip_uuid,
        locationName=observation.location_name or "未命名地点",
        latitude=observation.latitude,
        longitude=observation.longitude,
        note=observation.note,
        checkedAt=observation.occurred_at,
    )


def update_checkin_observation(
    db: Session,
    user_uuid: str,
    observation_uuid: str,
    payload: CheckinUpdateRequest,
) -> TravelObservationResponse:
    """更新用户主动打卡的名称与备注，不改写空间与时间事实。"""
    checkin = db.scalar(
        select(TravelObservation).where(
            TravelObservation.uuid == observation_uuid,
            TravelObservation.user_uuid == user_uuid,
            TravelObservation.observation_type == MANUAL_CHECKIN,
        )
    )
    # 分支条件：非本人的记录、自动 GPS 或不存在的 UUID 都不暴露内部差异。
    if checkin is None:
        raise AppException("打卡不存在或无权访问", status_code=404, code="CHECKIN_NOT_FOUND")
    trip = _get_owned_trip(db, user_uuid, checkin.trip_uuid)
    # 分支条件：已结束旅行保留历史回顾，但不允许再修改其用户记录文本。
    if trip.status != TRIP_STATUS_IN_PROGRESS:
        raise AppException("仅进行中的行程可以编辑打卡", status_code=409, code="TRIP_NOT_IN_PROGRESS")
    checkin.location_name = payload.location_name
    checkin.note = payload.note.strip() or None
    db.commit()
    db.refresh(checkin)
    return _to_observation_response(checkin)
