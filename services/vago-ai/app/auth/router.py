"""认证领域 API 路由。"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.schemas import (
    LoginResponse,
    OAuthLoginRequest,
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


@router.post("/login/oauth", response_model=ApiResponse[LoginResponse])
async def login_oauth(
    payload: OAuthLoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[LoginResponse]:
    """第三方 OAuth 登录。"""
    return success(
        await service.login_by_oauth(db, payload.provider, payload.auth_code, payload.redirect_uri),
        "登录成功",
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
