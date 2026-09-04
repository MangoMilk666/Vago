"""旅行足迹 HTTP API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.footprints import service
from app.footprints.schemas import (
    CheckinCreateRequest,
    CheckinResponse,
    LocationSampleResponse,
    LocationSyncRequest,
    LocationSyncResponse,
)
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.post("/location-samples/sync", response_model=ApiResponse[LocationSyncResponse])
def sync_location_samples(
    payload: LocationSyncRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[LocationSyncResponse]:
    """接收 iOS 离线缓冲的一批 GPS 采样。"""
    return success(service.sync_location_samples(db, user_uuid, payload), "轨迹同步成功")


@router.get("/trips/{trip_uuid}/locations", response_model=ApiResponse[list[LocationSampleResponse]])
def list_trip_locations(
    trip_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[LocationSampleResponse]]:
    """读取指定行程的已同步 GPS 轨迹。"""
    return success(service.list_trip_locations(db, user_uuid, trip_uuid))


@router.post("/checkins", response_model=ApiResponse[CheckinResponse])
def create_checkin(
    payload: CheckinCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[CheckinResponse]:
    """创建一次用户主动打卡。"""
    return success(service.create_checkin(db, user_uuid, payload), "打卡成功")
