"""认证领域 API 路由。"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
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
    WebLoginResponse,
    WebSessionResponse,
)
from app.auth.web_session import COOKIE_NAME, create_web_session, read_web_session, require_web_origin, revoke_web_session
from app.core.database import get_db
from app.shared.responses import ApiResponse, success

router = APIRouter()


def check_login_client(request: Request, client_type: str) -> None:
    """浏览器请求只能取得 Web Session，ios原生端请求才签发 JWT。"""
    if client_type == "web":
        require_web_origin(request)
    elif "origin" in request.headers:
        raise HTTPException(status_code=403, detail="浏览器不能申请原生端令牌")


@router.post("/sms/send", response_model=ApiResponse[SmsSendResponse])
async def send_sms(payload: SmsSendRequest) -> ApiResponse[SmsSendResponse]:
    """发送手机号验证码。"""
    return success(await service.send_sms_code(payload.phone), "验证码已发送")


@router.post("/login/phone", response_model=ApiResponse[LoginResponse | WebLoginResponse])
async def login_phone(
    payload: PhoneLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[LoginResponse | WebLoginResponse]:
    """手机号验证码登录。"""
    check_login_client(request, payload.client_type)
    result = await service.login_by_phone(
        db,
        payload.phone,
        payload.code,
        payload.client_type,
        payload.device_id,
    )
    if payload.client_type == "web":
        await create_web_session(response, result.user_info.uuid, request.cookies.get(COOKIE_NAME))
    return success(result, "登录成功")


@router.post("/register", response_model=ApiResponse[LoginResponse | WebLoginResponse])
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[LoginResponse | WebLoginResponse]:
    """手机号注册。"""
    check_login_client(request, payload.client_type)
    result = await service.register_by_phone(
        db, payload.phone, payload.code, payload.nickname, payload.client_type, payload.device_id
    )
    if payload.client_type == "web":
        await create_web_session(response, result.user_info.uuid, request.cookies.get(COOKIE_NAME))
    return success(result, "注册成功")


@router.post("/login/oauth", response_model=ApiResponse[LoginResponse | WebLoginResponse])
async def login_oauth(
    payload: OAuthLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[LoginResponse | WebLoginResponse]:
    """第三方 OAuth 登录。"""
    check_login_client(request, payload.client_type)
    result = await service.login_by_oauth(
        db, payload.provider, payload.auth_code, payload.redirect_uri, payload.client_type
    )
    if payload.client_type == "web":
        await create_web_session(response, result.user_info.uuid, request.cookies.get(COOKIE_NAME))
    return success(result, "登录成功")


@router.get("/session", response_model=ApiResponse[WebSessionResponse])
async def current_web_session(request: Request, db: Session = Depends(get_db)) -> ApiResponse[WebSessionResponse]:
    """页面重载时读取有效 Session 和 CSRF Token。"""
    session = await read_web_session(request, db)
    user = service.get_user_by_uuid(db, session["userUuid"])
    return success(WebSessionResponse(userInfo=service.build_profile(db, user), csrfToken=session["csrfToken"]))


@router.post("/token/refresh", response_model=ApiResponse[TokenPair])
async def refresh_token(
    payload: TokenRefreshRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[TokenPair]:
    """刷新访问令牌。"""
    return success(await service.refresh_token(db, payload.refresh_token), "令牌已刷新")


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    request: Request,
    response: Response,
    payload: TokenRefreshRequest | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[None]:
    """退出登录并让当前 token 失效。"""
    # 分支条件：请求体存在时携带 refreshToken 一起作废，否则只拉黑 accessToken。
    if authorization:
        refresh_token = payload.refresh_token if payload else None
        await service.logout(authorization, refresh_token)
    else:
        await read_web_session(request, db)
        await revoke_web_session(request, response)
    return success(None, "已退出登录")
