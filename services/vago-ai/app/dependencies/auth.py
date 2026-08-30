"""
JWT 身份验证依赖（FastAPI Depends）。

前端直连 Python 时使用，校验流程与 Java JwtTokenUserInterceptor 完全一致：
  1. 从请求头读取 token（header name 由 settings.jwt_token_name 配置）
  2. 用 HMAC-HS256 + 共享密钥验证签名及过期时间
  3. 检查 Redis 黑名单（key = vago:token:bl:{md5(token)}，退出登录后写入）
  4. 提取 payload 中的 userUuid 字段并返回

设计为轻量 Depends，只挂载到 chat router，不影响 articles / ai 内部路由。

Redis 使用 asyncio 连接池管理连接，避免每次请求新建连接。
"""

import hashlib
import logging

import jwt
from fastapi import Depends, HTTPException, Request

from app.config import settings
from app.core.redis import close_redis_pool, get_redis_client

logger = logging.getLogger(__name__)

_BLACKLIST_KEY_PREFIX = "vago:token:bl:"


def _resolve_token(request: Request) -> str | None:
    """按配置读取 token header，并兼容 Swagger 常见的 Bearer 前缀。"""
    token = request.headers.get(settings.jwt_token_name) or request.headers.get("authorization")
    # 分支条件：请求头带 Bearer 前缀时，只取后面的原始 token。
    if token and token.lower().startswith("bearer "):
        return token[7:]
    return token


async def get_current_user_uuid(request: Request) -> str:
    """
    提取并验证 JWT，返回当前用户 UUID。

    作为 FastAPI Depends 注入 chat 路由，替代原 Java JWT 拦截器职责。

    参数:
        authorization: 请求头中的 token（Header name 由配置决定，默认 authorization）。

    返回:
        str — 当前用户 UUID（payload.userUuid）。

    异常:
        HTTPException(401) — token 缺失 / 签名无效 / 已过期 / 在黑名单中。
    """
    token = _resolve_token(request)
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

    # 检查黑名单（退出登录后 Java 侧会将 md5(token) 写入 Redis）
    try:
        token_hash = hashlib.md5(token.encode()).hexdigest()
        bl_key = f"{_BLACKLIST_KEY_PREFIX}{token_hash}"
        r = await get_redis_client()
        # 分支条件：token 哈希命中 Redis 黑名单时，说明用户已退出登录。
        if await r.exists(bl_key):
            raise HTTPException(status_code=401, detail="令牌已失效，请重新登录")
    except HTTPException:
        raise
    except Exception as exc:
        # Redis 连接失败时降级放行（不因缓存不可用中断业务）
        logger.warning("Redis 黑名单检查失败，降级放行: %s", exc)

    user_uuid: str | None = payload.get("userUuid")
    # 分支条件：JWT payload 缺少 userUuid 时，无法建立用户级数据隔离。
    if not user_uuid:
        raise HTTPException(status_code=401, detail="令牌缺少用户标识")

    return user_uuid
