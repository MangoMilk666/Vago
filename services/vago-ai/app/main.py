"""Vago FastAPI 后端地基的应用工厂。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import close_redis_pool
from app.dependencies.rate_limit import close_rate_limiter_pool, rate_limit_middleware
from app.services.vector_store import init_collection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时准备外部资源，关闭时释放连接池。"""
    logger.info("Vago FastAPI backend starting; initializing Qdrant collection...")
    try:
        await init_collection()
        logger.info("Qdrant collection initialized")
    except Exception as exc:
        logger.warning(
            "Qdrant initialization failed (%s); vector retrieval will be unavailable",
            exc,
        )

    yield

    logger.info("Vago FastAPI backend shutting down; closing resource pools...")
    await close_redis_pool()
    await close_rate_limiter_pool()


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Vago FastAPI backend foundation:\n"
            "- Existing AI chat, SSE and RAG ingestion capabilities\n"
            "- Shared core infrastructure for auth, config, database and errors\n"
            "- Migration target for user, trip, footprint and memory domains"
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS 保持兼容：允许 Vite 前端和旧 Java 后端在迁移期继续调用。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(rate_limit_middleware)

    # 统一异常处理和 v1 路由注册都集中在应用工厂里，便于测试独立创建 app。
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["健康检查"])
    async def health() -> dict[str, str]:
        """健康检查接口，供本地开发和部署探针使用。"""
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
        }

    return app


app = create_app()
