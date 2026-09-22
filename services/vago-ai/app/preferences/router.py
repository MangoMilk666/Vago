"""用户明确旅行偏好 HTTP API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.preferences import service
from app.preferences.schemas import TravelPreferenceResponse, TravelPreferenceUpdateRequest
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.get("/travel-preferences", response_model=ApiResponse[TravelPreferenceResponse])
def get_travel_preferences(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TravelPreferenceResponse]:
    """读取当前用户明确填写的旅行偏好。"""
    return success(service.get_preferences(db, user_uuid))


@router.put("/travel-preferences", response_model=ApiResponse[TravelPreferenceResponse])
def update_travel_preferences(
    payload: TravelPreferenceUpdateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TravelPreferenceResponse]:
    """更新当前用户明确旅行偏好。"""
    return success(service.update_preferences(db, user_uuid, payload), "旅行偏好已更新")
