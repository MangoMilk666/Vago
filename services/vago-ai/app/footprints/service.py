"""旅行足迹领域服务：校验行程归属后持久化移动端事实记录。"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
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
    # 重试时真正同步到db的样本列表
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
        db.commit()
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
