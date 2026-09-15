"""旅行足迹 HTTP API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.footprints import service
from app.footprints.schemas import (
    CheckinCreateRequest,
    CheckinResponse,
    CheckinUpdateRequest,
    LocationSampleResponse,
    LocationSyncRequest,
    LocationSyncResponse,
    TravelObservationResponse,
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


@router.get("/trips/{trip_uuid}/observations", response_model=ApiResponse[list[TravelObservationResponse]])
def list_trip_observations(
    trip_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[TravelObservationResponse]]:
    """读取统一旅行空间观察流，供新版 iOS 同时构建路线与打卡标记。"""
    return success(service.list_trip_observations(db, user_uuid, trip_uuid))


@router.get("/trips/{trip_uuid}/checkins", response_model=ApiResponse[list[CheckinResponse]])
def list_trip_checkins(
    trip_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[CheckinResponse]]:
    """读取指定行程的已保存手动打卡，用于客户端地图渲染。"""
    return success(service.list_trip_checkins(db, user_uuid, trip_uuid))


@router.post("/checkins", response_model=ApiResponse[CheckinResponse])
def create_checkin(
    payload: CheckinCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[CheckinResponse]:
    """创建一次用户主动打卡。"""
    return success(service.create_checkin(db, user_uuid, payload), "打卡成功")


@router.post("/observations/checkins", response_model=ApiResponse[TravelObservationResponse])
def create_checkin_observation(
    payload: CheckinCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TravelObservationResponse]:
    """创建手动打卡并返回统一观察，供新版 iOS 立即合并地图。"""
    return success(service.create_checkin_observation(db, user_uuid, payload), "打卡成功")


@router.patch("/observations/checkins/{observation_uuid}", response_model=ApiResponse[TravelObservationResponse])
def update_checkin_observation(
    observation_uuid: str,
    payload: CheckinUpdateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TravelObservationResponse]:
    """更新用户主动打卡的可编辑文本，不改写已记录的空间事实。"""
    return success(service.update_checkin_observation(db, user_uuid, observation_uuid, payload), "打卡已更新")
