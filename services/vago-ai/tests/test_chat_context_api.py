"""验证 AI 对话将个人资料检索开关传递给上下文层。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import api_v1_router
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import get_current_user_uuid
from app.routers import chat


def test_chat_forwards_use_rag_flag(monkeypatch) -> None:
    """测试：用户关闭个人资料检索时，路由不得默认将其重新打开。"""
    captured: dict[str, bool] = {}

    async def fake_run_agent_chat(*, user_uuid, messages, use_rag):
        captured["use_rag"] = use_rag
        return {"answer": "通用旅行建议", "sources": [], "model": "test-model"}

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    async def override_current_user_uuid() -> str:
        return "context-test-user"

    app.dependency_overrides[get_current_user_uuid] = override_current_user_uuid
    monkeypatch.setattr(chat, "run_agent_chat", fake_run_agent_chat)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "推荐京都景点"}], "useRag": False},
        )

    assert response.status_code == 200
    assert captured["use_rag"] is False
