"""
Vago AI 服务入口
Python FastAPI —— 负责 AI 行程规划、RAG 攻略检索等智能功能
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ai

app = FastAPI(
    title="Vago AI Service",
    description="叠迹 AI 服务：行程规划、攻略 RAG 检索、足迹分析",
    version="0.1.0",
)

# ── CORS（允许 Java 后端和前端调用）──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",   # Java vago-backend
        "http://localhost:5173",   # Vite 前端
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──────────────────────────────────────────────────────────────────
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI 功能"])


@app.get("/health", tags=["健康检查"])
def health():
    return {"status": "ok", "service": "vago-ai"}
