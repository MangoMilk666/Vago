"""
请求频率限制中间件（Rate Limiting Middleware）。

基于 Redis + 滑动窗口（固定窗口简化版）实现 IP 级别和用户级别的请求限流，
保护 AI 对话接口不被滥用。

限流策略：
  - IP 级别：每 IP 每分钟最多 60 次请求（已登录 + 未登录合计）
  - 用户级别：每用户每分钟最多 30 次请求（仅已登录用户）
  - 限流超标时返回 HTTP 429（Too Many Requests）
"""

import logging
import time

from fastapi import Request
from redis import asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ── 默认限制阈值 ─────────────────────────────────────────────────────────────────
IP_RATE_LIMIT = 60       # 每分钟每 IP
USER_RATE_LIMIT = 30     # 每分钟每用户
WINDOW_SECONDS = 60      # 时间窗口（秒）

# ── 全局连接池（与 auth.py 共享同一 Redis）─────────────────────────────────────
_redis_pool: aioredis.ConnectionPool | None = None


async def _get_redis() -> aioredis.Redis:
    """获取 Redis 客户端实例（使用模块级连接池）。"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=2,
            max_connections=20,
            retry_on_timeout=True,
        )
    return aioredis.Redis(connection_pool=_redis_pool)


async def close_rate_limiter_pool() -> None:
    """关闭限流器 Redis 连接池（应用 shutdown 时调用）。"""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None


def _rate_limit_key(prefix: str, identifier: str) -> str:
    """
    生成限流计数 Redis key。

    格式：vago:ratelimit:{prefix}:{identifier}:{window_start}
    窗口起始 = 当前时间戳 // WINDOW_SECONDS，实现固定窗口。
    """
    window = int(time.time()) // WINDOW_SECONDS
    return f"vago:ratelimit:{prefix}:{identifier}:{window}"


async def rate_limit_middleware(request: Request, call_next):
    """
    请求频率限制中间件。

    作为 FastAPI HTTP Middleware 使用，同时校验 IP 级别和用户级别限流。
    限流超标时返回 HTTP 429（Too Many Requests），否则继续处理请求。

    Redis 不可用时自动降级放行，不中断业务。
    """
    # ── IP 级别限流 ─────────────────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    ip_key = _rate_limit_key("ip", client_ip)

    try:
        r = await _get_redis()

        # IP 限流
        ip_count = await r.incr(ip_key)
        if ip_count == 1:
            await r.expire(ip_key, WINDOW_SECONDS + 5)

        if ip_count > IP_RATE_LIMIT:
            logger.warning("IP 限流触发: %s, count=%d", client_ip, ip_count)
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})

        # ── 用户级别限流（仅已认证请求） ────────────────────────────────────
        auth_header = request.headers.get("authorization")
        if auth_header:
            user_key = _rate_limit_key("user", auth_header[:20])
            user_count = await r.incr(user_key)
            if user_count == 1:
                await r.expire(user_key, WINDOW_SECONDS + 5)

            if user_count > USER_RATE_LIMIT:
                logger.warning("用户限流触发: token_prefix=%s..., count=%d",
                               auth_header[:12], user_count)
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})

    except Exception as exc:
        # Redis 不可用时降级放行，不中断业务
        logger.warning("限流检查失败（Redis 不可用?），降级放行: %s", exc)

    # 继续处理请求
    try:
        return await call_next(request)
    except RuntimeError as e:
        # 流式响应异常时跳过
        logger.debug("限流中间件跳过已处理的流式响应: %s", e)
        from fastapi.responses import Response
        return Response(status_code=500)
