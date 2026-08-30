"""Redis 客户端管理。

remould 阶段 Redis 同时服务 JWT 黑名单、刷新 token、短信验证码和限流等短期状态，
这里集中连接池生命周期，避免不同模块各自维护连接。
"""

import logging

from redis import asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_pool: aioredis.ConnectionPool | None = None


async def get_redis_client() -> aioredis.Redis:
    """返回复用连接池的 Redis 客户端实例。"""
    global _redis_pool
    # 分支条件：当前进程还没有 Redis 连接池时，创建新的连接池。
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


async def close_redis_pool() -> None:
    """关闭 Redis 连接池，供 FastAPI lifespan 在 shutdown 阶段调用。"""
    global _redis_pool
    # 分支条件：仅当连接池已经创建时才执行断开，避免重复 shutdown。
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis 连接池已关闭")
