"""用户领域 API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.shared.responses import ApiResponse, success
from app.users.schemas import (
    AccountCancelRequest,
    AccountCancelResponse,
    UserProfile,
    UserProfileUpdate,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from app.users.service import (
    build_profile,
    cancel_account as cancel_account_service,
    get_settings_response,
    get_user_or_raise,
    revoke_cancel_account as revoke_cancel_account_service,
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


@router.delete("/account", response_model=ApiResponse[AccountCancelResponse])
async def cancel_account(
    payload: AccountCancelRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[AccountCancelResponse]:
    """申请注销账号。"""
    return success(
        await cancel_account_service(user_uuid, payload.sms_code, db),
        "注销申请已提交，7日内可撤销",
    )


@router.post("/account/cancel-revoke", response_model=ApiResponse[None])
async def revoke_cancel_account(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[None]:
    """撤销注销申请。"""
    await revoke_cancel_account_service(user_uuid, db)
    return success(None, "注销申请已撤销，账号恢复正常")
