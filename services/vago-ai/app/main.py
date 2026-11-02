"""Vago FastAPI 后端地基的应用工厂。"""

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import close_redis_pool
from app.dependencies.rate_limit import close_rate_limiter_pool, rate_limit_middleware
from app.services.embedder import probe_embedding_dimension
from app.services.vector_store import (
    VectorDimensionMismatchError, init_collection, set_rag_ready, set_rag_unavailable,
)
from scripts.rebuild_knowledge_index import rebuild

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时准备外部资源，关闭时释放连接池。"""
    rebuild_task: asyncio.Task[None] | None = None
    set_rag_unavailable("语义索引尚未完成启动检查")
    # 分支条件：仅在部署启用 RAG capability 时初始化 Qdrant，个人知识领域不依赖该资源。
    if settings.rag_enabled:
        logger.info("Vago FastAPI backend starting; initializing Qdrant collection...")
        try:
            # 如果模型实际维度变了，先明确更新本进程的配置，再检查旧 collection。
            actual_dim = await probe_embedding_dimension()
            if actual_dim != settings.embedding_dim:
                if not settings.rebuild_rag_index_if_dim_change:
                    raise VectorDimensionMismatchError(
                        f"模型 {settings.embedding_model} 返回 {actual_dim} 维，"
                        f"EMBEDDING_DIM 配置为 {settings.embedding_dim}；RAG 已停用"
                    )
                logger.warning("模型实际维度为 %d；请将 EMBEDDING_DIM 更新为此值", actual_dim)
                settings.embedding_dim = actual_dim
            await init_collection()
            logger.info("Qdrant collection initialized")
        except VectorDimensionMismatchError as exc:
            set_rag_unavailable(str(exc))
            logger.error("个人知识索引维度不匹配：%s", exc)
            if settings.rebuild_rag_index_if_dim_change:
                from datetime import datetime, timezone

                target = f"{settings.qdrant_collection}_dim{settings.embedding_dim}_{datetime.now(timezone.utc):%Y%m%d%H%M%S}"

                async def rebuild_once() -> None:
                    """后台只重建一次；数量核对完成后才开放新的检索目标。"""
                    try:
                        await rebuild(target)
                        set_rag_ready(target)
                        logger.info("个人知识索引已切换到 %s；请将 QDRANT_COLLECTION 更新为此名称", target)
                    except Exception:
                        logger.exception("个人知识索引重建失败，RAG 保持不可用")

                rebuild_task = asyncio.create_task(rebuild_once())
        except Exception as exc:
            set_rag_unavailable(str(exc))
            logger.warning(
                "Qdrant initialization failed (%s); vector retrieval will be unavailable",
                exc,
            )
    else:
        set_rag_unavailable("当前环境未启用语义索引能力")
        logger.info("Vago FastAPI backend starting with RAG capability disabled")

    yield

    if rebuild_task is not None and not rebuild_task.done():
        rebuild_task.cancel()
        await asyncio.gather(rebuild_task, return_exceptions=True)
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

    # 仅允许已配置 Web 来源携带 Cookie；iOS Bearer 请求不依赖浏览器 CORS。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
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
