"""用户领域 API 路由。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.shared.responses import ApiResponse, success
from app.users.schemas import UserProfile, UserProfileUpdate, UserSettingsResponse, UserSettingsUpdate
from app.users.service import (
    build_profile,
    get_settings_response,
    get_user_or_raise,
    update_profile,
    update_settings,
)

router = APIRouter()


@router.get("/profile", response_model=ApiResponse[UserProfile])
def get_profile(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[UserProfile]:
    """读取当前登录用户资料。"""
    user = get_user_or_raise(db, user_uuid)
    return success(build_profile(db, user))


@router.put("/profile", response_model=ApiResponse[UserProfile])
def update_current_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[UserProfile]:
    """更新当前登录用户资料。"""
    return success(update_profile(db, user_uuid, payload), "资料已更新")


@router.get("/settings", response_model=ApiResponse[UserSettingsResponse])
def get_current_settings(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[UserSettingsResponse]:
    """读取当前用户偏好设置。"""
    return success(get_settings_response(db, user_uuid))


@router.put("/settings", response_model=ApiResponse[UserSettingsResponse])
def update_current_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[UserSettingsResponse]:
    """更新当前用户偏好设置。"""
    return success(update_settings(db, user_uuid, payload), "设置已更新")


@router.delete("/account", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def cancel_account() -> ApiResponse[None]:
    """账号注销仍由 Java 侧承接，Python 暂保留兼容路径。"""
    return ApiResponse(code=501, message="账号注销尚未迁移到 FastAPI", data=None)


@router.post("/account/cancel-revoke", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def revoke_cancel_account() -> ApiResponse[None]:
    """注销撤销仍由 Java 侧承接，Python 暂保留兼容路径。"""
    return ApiResponse(code=501, message="注销撤销尚未迁移到 FastAPI", data=None)
