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

from app.routers import ai, articles
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
      - 当前无需特殊清理，预留扩展点
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
    logger.info("Vago AI 服务关闭")


app = FastAPI(
    title="Vago AI Service",
    description=(
        "叠迹 AI 服务：\n"
        "- **攻略 RAG 管道**：文本清洗 → 语义分块 → Embedding → Qdrant 向量存储\n"
        "- **向量检索**：用户私有攻略库语义检索，供行程规划链路调用\n"
        "- **AI 行程规划**：RAG + LLM 生成定制化行程草稿（开发中）"
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# ── CORS（允许 Java vago-backend 和 Vite 开发服务器跨域调用）─────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",   # Java vago-backend
        "http://localhost:5173",   # Vite Dev Server
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──────────────────────────────────────────────────────────────────
app.include_router(ai.router,       prefix="/api/v1/ai",       tags=["AI 行程规划"])
app.include_router(articles.router, prefix="/api/v1/articles", tags=["攻略库 RAG"])


@app.get("/health", tags=["健康检查"])
async def health():
    """
    健康检查接口，供 K8s liveness probe 或监控系统轮询。

    返回:
        服务名称和状态字段。
    """
    return {"status": "ok", "service": "vago-ai", "version": "0.2.0"}
