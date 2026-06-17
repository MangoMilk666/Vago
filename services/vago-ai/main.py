"""
Vago AI 服务入口（FastAPI Application）。

负责：
  - 注册所有路由（AI 行程规划 + 攻略库 RAG 管理）
  - 配置 CORS（允许 Java vago-backend 和 Vite 前端调用）
  - 应用生命周期管理（lifespan）：启动时初始化 Qdrant Collection

启动命令：
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.dependencies.auth import close_redis_pool
from app.dependencies.rate_limit import rate_limit_middleware, close_rate_limiter_pool
from app.routers import ai, articles, chat
from app.services.vector_store import init_collection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期上下文管理器。

    Startup 阶段：
      - 初始化 Qdrant Collection（若不存在则自动创建）
      - 确保向量库就绪后再开始接收请求

    Shutdown 阶段：
      - 关闭 Redis 连接池（JWT 黑名单 + 限流器）
    """
    logger.info("Vago AI 服务启动中，正在初始化 Qdrant Collection...")
    try:
        await init_collection()
        logger.info("Qdrant Collection 初始化成功，服务就绪")
    except Exception as exc:
        logger.warning(
            "Qdrant 初始化失败（%s），服务将继续启动，但向量检索功能不可用",
            exc,
        )
    yield
    logger.info("Vago AI 服务关闭，清理资源中...")
    await close_redis_pool()
    await close_rate_limiter_pool()


app = FastAPI(
    title="Vago AI Service",
    description=(
        "叠迹 AI 服务：\n"
        "- **攻略 RAG 管道**：文本清洗 → 语义分块 → Embedding → Qdrant 向量存储\n"
        "- **向量检索**：用户私有攻略库语义检索，供行程规划链路调用\n"
        "- **AI 对话**：RAG Agent 对话，支持流式（SSE）和非流式两种模式"
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# 重构后前端直连 Python（chat 接口），需要允许 Vite Dev Server 跨域。
# Java vago-backend 的内部调用（articles ingest/delete）不走浏览器，不受 CORS 限制。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite Dev Server（前端直连 chat 接口）
        "http://localhost:8080",   # Java vago-backend（内部调用 articles 接口）
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 请求频率限制 ──────────────────────────────────────────────────────────────
# 对所有路由启用 IP 级别和用户级别的限流，防止滥用。
# 限流基于 Redis 固定窗口实现，Redis 不可用时自动降级放行。
app.middleware("http")(rate_limit_middleware)

# ── 路由注册 ──────────────────────────────────────────────────────────────────
# chat 路由前缀改为 /api/v1/ai/chat，与 Java 暴露的路径保持一致，
# Nginx / Vite Proxy 可按前缀直接路由到 Python，无需路径重写。
app.include_router(ai.router,       prefix="/api/v1/ai",       tags=["AI 行程规划"])
app.include_router(articles.router, prefix="/api/v1/articles", tags=["攻略库 RAG"])
app.include_router(chat.router,     prefix="/api/v1/ai/chat",  tags=["AI 对话"])


@app.get("/health", tags=["健康检查"])
async def health():
    """
    健康检查接口，供 K8s liveness probe 或监控系统轮询。

    返回:
        服务名称和状态字段。
    """
    return {"status": "ok", "service": "vago-ai", "version": "0.3.0"}
