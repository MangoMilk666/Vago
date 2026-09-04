"""Vago FastAPI 后端的 v1 API 聚合路由。"""

from fastapi import APIRouter

from app.auth import router as auth_router
from app.footprints import router as footprints_router
from app.knowledge import router as knowledge_router
from app.routers import ai, chat
from app.travel import router as travel_router
from app.users import router as users_router

api_v1_router = APIRouter()
# 这里保持现有外部路径不变，只把注册位置收拢到 /api/v1 聚合路由下。
api_v1_router.include_router(ai.router, prefix="/ai", tags=["AI 行程规划"])
api_v1_router.include_router(chat.router, prefix="/ai/chat", tags=["AI 对话"])

# Phase 2 新增 Python 侧认证/用户接口，同时保留 Java 时代 /user 前缀作为兼容入口。
api_v1_router.include_router(auth_router.router, prefix="/auth", tags=["认证"])
api_v1_router.include_router(auth_router.router, prefix="/user", tags=["认证兼容"])
api_v1_router.include_router(users_router.router, prefix="/users", tags=["用户"])
api_v1_router.include_router(users_router.router, prefix="/user", tags=["用户兼容"])

# Phase 3 迁移 Trip / Plan / Itinerary，暂不迁移 Guides / Collections。
api_v1_router.include_router(travel_router.router, prefix="/travel", tags=["旅行核心"])

# Phase 4 将个人攻略重定位为 Personal Travel Knowledge，discover/like 仍留在 Java。
api_v1_router.include_router(knowledge_router.router, prefix="/knowledge", tags=["个人旅行知识"])

# Phase 8 的足迹 API 由移动端采集并同步，服务端保存长期事实数据。
api_v1_router.include_router(footprints_router.router, prefix="/footprints", tags=["旅行足迹"])
