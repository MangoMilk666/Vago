"""旅行足迹领域服务：校验行程归属后持久化移动端事实记录。"""

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.footprints.models import Checkin, LocationSample
from app.footprints.schemas import (
    CheckinCreateRequest,
    CheckinResponse,
    LocationSampleResponse,
    LocationSyncRequest,
    LocationSyncResponse,
)
from app.travel.models import Trip, utc_now_naive
from app.travel.service import TRIP_STATUS_IN_PROGRESS


# 过近打卡会在地图上重叠，且通常不是新的旅行事实；服务端统一约束以覆盖所有客户端。
# 最小重复打卡距离判定阈值30米
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


def sync_location_samples(
    db: Session,
    user_uuid: str,
    payload: LocationSyncRequest,
) -> LocationSyncResponse:
    """批量写入 GPS 样本；按客户端 UUID 幂等以支持离线重试。"""
    _get_owned_trip(db, user_uuid, payload.trip_uuid)
    client_uuids = [sample.client_uuid for sample in payload.samples]
    existing_uuids = set(
        db.scalars(
            select(LocationSample.client_uuid).where(
                LocationSample.user_uuid == user_uuid,
                LocationSample.client_uuid.in_(client_uuids),
            )
        ).all()
    )
    # 保留请求开始前已存在的键，发生并发写入冲突后据此重新计算本请求的结果计数。
    existing_before_request = existing_uuids.copy()
    # 重试时真正同步到 db 的样本列表。
    new_rows: list[LocationSample] = []
    for sample in payload.samples:
        # 分支条件：客户端样本已被成功接收过时，跳过写入，让移动端可安全重试整批数据。
        if sample.client_uuid in existing_uuids:
            continue
        new_rows.append(
            LocationSample(
                uuid=_new_uuid(),
                client_uuid=sample.client_uuid,
                user_uuid=user_uuid,
                trip_uuid=payload.trip_uuid,
                latitude=sample.latitude,
                longitude=sample.longitude,
                accuracy_m=sample.accuracy_m,
                speed_mps=sample.speed_mps,
                recorded_at=sample.recorded_at.astimezone(UTC).replace(tzinfo=None),
            )
        )
        existing_uuids.add(sample.client_uuid)
    if new_rows:
        db.add_all(new_rows)
        try:
            db.commit()
        except IntegrityError:
            '''
            极端情况：1）请求 A 和请求 B 同时检查数据库，都发现 clientUuid 还不存在
            2）A 先提交成功。
            3）B 再提交时，触发数据库唯一约束冲突 IntegrityError。
            4）如果不捕获，B 会收到 500，iOS 可能保留这批本地数据不断重试。
            '''
            # 分支条件：另一台设备或重试请求在本事务提交前写入同一幂等键时回滚并复查，
            # 让客户端可以安全删除已被服务端确认的批次，而不是因唯一键异常永久卡住队列。
            db.rollback()
            persisted_uuids = set(
                db.scalars(
                    select(LocationSample.client_uuid).where(
                        LocationSample.user_uuid == user_uuid,
                        LocationSample.client_uuid.in_(client_uuids),
                    )
                ).all()
            )
            # 如果并非所有点都已存在，说明这不是可安全忽略的并发重复问题，继续抛出异常，
            # 让系统暴露真实错误。
            if not set(client_uuids).issubset(persisted_uuids):
                raise
            accepted_count = len(persisted_uuids - existing_before_request)
            # 即使当前请求本身提交失败，也告诉客户端：
            # 这些点已经被服务端确认，无需继续保留在本地待传队列。
            return LocationSyncResponse(
                acceptedCount=accepted_count,
                duplicateCount=len(payload.samples) - accepted_count,
            )
    return LocationSyncResponse(
        acceptedCount=len(new_rows),
        duplicateCount=len(payload.samples) - len(new_rows),
    )


def list_trip_locations(db: Session, user_uuid: str, trip_uuid: str) -> list[LocationSampleResponse]:
    """按采样时间读取一段行程的已同步轨迹。"""
    _get_owned_trip(db, user_uuid, trip_uuid)
    samples = db.scalars(
        select(LocationSample)
        .where(LocationSample.user_uuid == user_uuid, LocationSample.trip_uuid == trip_uuid)
        .order_by(LocationSample.recorded_at.asc())
    ).all()
    return [LocationSampleResponse.model_validate(sample) for sample in samples]


def list_trip_checkins(db: Session, user_uuid: str, trip_uuid: str) -> list[CheckinResponse]:
    """按打卡时间读取行程中的用户主动记录，供地图恢复标记。"""
    _get_owned_trip(db, user_uuid, trip_uuid)
    checkins = db.scalars(
        select(Checkin)
        .where(Checkin.user_uuid == user_uuid, Checkin.trip_uuid == trip_uuid)
        .order_by(Checkin.checked_at.asc())
    ).all()
    return [CheckinResponse.model_validate(checkin) for checkin in checkins]


def create_checkin(db: Session, user_uuid: str, payload: CheckinCreateRequest) -> CheckinResponse:
    """为进行中的行程新增一条用户主动确认的打卡。"""
    trip = _get_owned_trip(db, user_uuid, payload.trip_uuid)
    # 分支条件：只有进行中行程允许创建新的手动记录，保持已结束旅行的数据可回顾但不可篡改。
    if trip.status != TRIP_STATUS_IN_PROGRESS:
        raise AppException("仅进行中的行程可以打卡", status_code=409, code="TRIP_NOT_IN_PROGRESS")
    existing_checkins = db.scalars(
        select(Checkin).where(Checkin.user_uuid == user_uuid, Checkin.trip_uuid == trip.uuid)
    ).all()
    # 分支条件：同一行程已有 30 米内打卡时拒绝创建，容纳真机 GPS 漂移并避免多端绕过客户端限制。
    if any(
        _distance_meters(payload.latitude, payload.longitude, checkin.latitude, checkin.longitude) < MINIMUM_CHECKIN_DISTANCE_METERS
        for checkin in existing_checkins
    ):
        raise AppException("和其他打卡点太近啦，请换个位置重试", status_code=409, code="CHECKIN_TOO_CLOSE")
    checked_at = payload.checked_at or datetime.now(UTC)
    checkin = Checkin(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        trip_uuid=trip.uuid,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        note=payload.note,
        checked_at=checked_at.astimezone(UTC).replace(tzinfo=None),
        created_at=utc_now_naive(),
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return CheckinResponse.model_validate(checkin)
