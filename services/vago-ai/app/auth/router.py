"""认证领域 API 路由。"""

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.schemas import (
    LoginResponse,
    PhoneLoginRequest,
    RegisterRequest,
    SmsSendRequest,
    SmsSendResponse,
    TokenPair,
    TokenRefreshRequest,
)
from app.core.database import get_db
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.post("/sms/send", response_model=ApiResponse[SmsSendResponse])
async def send_sms(payload: SmsSendRequest) -> ApiResponse[SmsSendResponse]:
    """发送手机号验证码。"""
    return success(await service.send_sms_code(payload.phone), "验证码已发送")


@router.post("/login/phone", response_model=ApiResponse[LoginResponse])
async def login_phone(
    payload: PhoneLoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[LoginResponse]:
    """手机号验证码登录。"""
    return success(await service.login_by_phone(db, payload.phone, payload.code), "登录成功")


@router.post("/register", response_model=ApiResponse[LoginResponse])
async def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[LoginResponse]:
    """手机号注册。"""
    return success(
        await service.register_by_phone(db, payload.phone, payload.code, payload.nickname),
        "注册成功",
    )


@router.post("/token/refresh", response_model=ApiResponse[TokenPair])
async def refresh_token(
    payload: TokenRefreshRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[TokenPair]:
    """刷新访问令牌。"""
    return success(await service.refresh_token(db, payload.refresh_token), "令牌已刷新")


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    payload: TokenRefreshRequest | None = None,
    authorization: str | None = Header(default=None),
) -> ApiResponse[None]:
    """退出登录并让当前 token 失效。"""
    await service.logout(authorization, payload.refresh_token if payload else None)
    return success(None, "已退出登录")


@router.post("/login/oauth", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def login_oauth() -> ApiResponse[None]:
    """OAuth 登录暂未迁移，保留路径用于前端切流前的显式提示。"""
    return ApiResponse(code=501, message="OAuth 登录尚未迁移到 FastAPI", data=None)
