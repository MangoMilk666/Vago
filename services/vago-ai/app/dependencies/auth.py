"""统一身份依赖：Web 使用 Redis Session，iOS 使用 Bearer JWT。"""

import hashlib
import logging

import jwt
from fastapi import Depends, HTTPException, Request
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.redis import close_redis_pool, get_redis_client
from app.core.database import get_db
from app.auth.web_session import COOKIE_NAME, read_web_session

logger = logging.getLogger(__name__)

_BLACKLIST_KEY_PREFIX = "vago:token:bl:"


def _resolve_token(request: Request) -> str | None:
    """按配置读取 token header，并兼容 Swagger 常见的 Bearer 前缀。"""
    token = request.headers.get(settings.jwt_token_name) or request.headers.get("authorization")
    # 分支条件：请求头带 Bearer 前缀时，只取后面的原始 token。
    if token and token.lower().startswith("bearer "):
        return token[7:]
    return token


async def get_current_user_uuid(request: Request, db: Session = Depends(get_db)) -> str:
    """
    先尊重显式 Bearer；没有认证请求头时才检查 Web Cookie。
    """
    token = _resolve_token(request)
    # 如果显式传入 Bearer，始终按 iOS JWT 校验，不在失败后退回 Cookie。
    if settings.jwt_token_name not in request.headers and "authorization" not in request.headers and COOKIE_NAME in request.cookies:
        session = await read_web_session(request, db)
        return session["userUuid"]
    # 分支条件：请求中没有任何可用 token 时，拒绝访问。
    if not token:
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    # 验证 JWT 签名和过期时间
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="令牌已过期")
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT 验证失败: %s", exc)
        raise HTTPException(status_code=401, detail="无效令牌")

    # 检查 access token 撤销状态；Redis 不可用时拒绝访问。
    try:
        token_hash = hashlib.md5(token.encode()).hexdigest()
        bl_key = f"{_BLACKLIST_KEY_PREFIX}{token_hash}"
        r = await get_redis_client()
        # 分支条件：token 哈希命中 Redis 黑名单时，说明用户已退出登录。
        if await r.exists(bl_key):
            raise HTTPException(status_code=401, detail="令牌已失效，请重新登录")
    except HTTPException:
        raise
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="令牌撤销状态暂时不可用") from exc

    user_uuid: str | None = payload.get("userUuid")
    # 分支条件：JWT payload 缺少 userUuid 时，无法建立用户级数据隔离。
    if not user_uuid:
        raise HTTPException(status_code=401, detail="令牌缺少用户标识")

    # 如果 JWT 不是访问令牌，或账号已禁用，不允许访问领域接口。
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="令牌类型错误")
    from app.users.service import ensure_user_can_login, get_user_by_uuid

    user = get_user_by_uuid(db, user_uuid)
    if user is None:
        raise HTTPException(status_code=401, detail="账号不存在")
    ensure_user_can_login(user)

    return user_uuid
