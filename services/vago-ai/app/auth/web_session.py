"""Web Cookie Session 的创建、验证和撤销。"""

import hashlib
import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.redis import get_redis_client
from app.users.service import ensure_user_can_login, get_user_by_uuid

SESSION_PREFIX = "vago:web:session:"
COOKIE_NAME = "__Host-vago_session" if settings.use_secure_web_cookie() else "vago_session"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _session_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{hashlib.sha256(session_id.encode()).hexdigest()}"


def _allowed_origins(request: Request) -> set[str]:
    """仅信任明确配置的 Web 来源和当前 API 的同源地址。"""
    own_origin = f"{request.url.scheme}://{request.url.netloc}"
    return {origin.rstrip("/") for origin in settings.cors_origins} | {own_origin}


def require_web_origin(request: Request) -> None:
    """检查 Web 状态变更请求的 Origin，拒绝跨站登录和写入。"""
    origin = request.headers.get("origin")
    if origin is None or origin.rstrip("/") not in _allowed_origins(request):
        raise HTTPException(status_code=403, detail="请求来源未获允许")


async def create_web_session(response: Response, user_uuid: str, old_session_id: str | None = None) -> None:
    """登录后轮换会话标识，旧会话立即失效。"""
    redis = await get_redis_client()
    if old_session_id:
        await redis.delete(_session_key(old_session_id))
    session_id = secrets.token_urlsafe(32)
    now = int(datetime.now(timezone.utc).timestamp())
    session = {
        "userUuid": user_uuid,
        "createdAt": now,
        "lastActiveAt": now,
        "absoluteExpiresAt": now + settings.web_session_absolute_seconds,
        "csrfToken": secrets.token_urlsafe(32),
    }
    await redis.setex(_session_key(session_id), min(settings.web_session_idle_seconds, settings.web_session_absolute_seconds), json.dumps(session))
    response.set_cookie(
        COOKIE_NAME, session_id, max_age=settings.web_session_absolute_seconds,
        path="/", secure=settings.use_secure_web_cookie(), httponly=True, samesite="lax",
    )


async def read_web_session(request: Request, db: Session, *, check_csrf: bool = True) -> dict:
    """从 Redis 验证空闲、绝对过期和账号状态；写请求额外验证 CSRF。"""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        raise HTTPException(status_code=401, detail="未登录")
    redis = await get_redis_client()
    try:
        raw = await redis.get(_session_key(session_id))
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="登录会话暂时不可用") from exc
    if raw is None:
        raise HTTPException(status_code=401, detail="会话已失效")
    session = json.loads(raw)
    now = int(datetime.now(timezone.utc).timestamp())
    if now >= session["absoluteExpiresAt"] or now - session["lastActiveAt"] >= settings.web_session_idle_seconds:
        await redis.delete(_session_key(session_id))
        raise HTTPException(status_code=401, detail="会话已过期")
    user = get_user_by_uuid(db, session["userUuid"])
    if user is None:
        await redis.delete(_session_key(session_id))
        raise HTTPException(status_code=401, detail="账号不存在")
    try:
        ensure_user_can_login(user)
    except AppException:
        await redis.delete(_session_key(session_id))
        raise
    if check_csrf and request.method in UNSAFE_METHODS:
        require_web_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(supplied, session["csrfToken"]):
            raise HTTPException(status_code=403, detail="CSRF 校验失败")
    session["lastActiveAt"] = now
    ttl = min(settings.web_session_idle_seconds, session["absoluteExpiresAt"] - now)
    try:
        await redis.setex(_session_key(session_id), ttl, json.dumps(session))
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="登录会话暂时不可用") from exc
    return session


async def revoke_web_session(request: Request, response: Response) -> None:
    """删除服务端记录，并以创建时相同的属性清除 Cookie。"""
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        redis = await get_redis_client()
        await redis.delete(_session_key(session_id))
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.use_secure_web_cookie(), httponly=True, samesite="lax")
