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
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException
from redis import asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_BLACKLIST_KEY_PREFIX = "vago:token:bl:"

# ── Redis 异步连接池（模块级单例）───────────────────────────────────────────────
_redis_pool: Optional[aioredis.ConnectionPool] = None


async def _get_redis() -> aioredis.Redis:
    """
    从连接池获取 Redis 客户端实例。

    使用 aioredis.ConnectionPool 管理长连接，
    避免每次请求都新建 TCP 连接。
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=2,
            max_connections=20,          # 连接池上限
            retry_on_timeout=True,       # 超时自动重试
        )
    return aioredis.Redis(connection_pool=_redis_pool)


async def close_redis_pool() -> None:
    """
    关闭 Redis 连接池（在应用 shutdown 时调用）。
    释放所有长连接资源。
    """
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis 连接池已关闭")


async def get_current_user_uuid(authorization: str | None = Header(default=None)) -> str:
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
    token = authorization
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
        r = await _get_redis()
        if await r.exists(bl_key):
            raise HTTPException(status_code=401, detail="令牌已失效，请重新登录")
    except HTTPException:
        raise
    except Exception as exc:
        # Redis 连接失败时降级放行（不因缓存不可用中断业务）
        logger.warning("Redis 黑名单检查失败，降级放行: %s", exc)

    user_uuid: str | None = payload.get("userUuid")
    if not user_uuid:
        raise HTTPException(status_code=401, detail="令牌缺少用户标识")

    return user_uuid
