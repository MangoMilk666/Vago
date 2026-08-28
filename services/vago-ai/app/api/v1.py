"""Vago FastAPI 后端的 v1 API 聚合路由。"""

from fastapi import APIRouter

from app.routers import ai, articles, chat

api_v1_router = APIRouter()
# 这里保持现有外部路径不变，只把注册位置收拢到 /api/v1 聚合路由下。
api_v1_router.include_router(ai.router, prefix="/ai", tags=["AI 行程规划"])
api_v1_router.include_router(articles.router, prefix="/articles", tags=["攻略库 RAG"])
api_v1_router.include_router(chat.router, prefix="/ai/chat", tags=["AI 对话"])
