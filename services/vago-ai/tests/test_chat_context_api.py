"""验证 AI 对话将个人资料检索开关传递给上下文层。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import api_v1_router
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import get_current_user_uuid
from app.agent_runtime.runtime import AgentRuntimePreparation
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


def test_chat_injects_authorized_personal_context(monkeypatch) -> None:
    """测试：Web 显式授权后，对话链路收到结构化 Context 与可展示来源标签。"""
    captured: dict[str, object] = {}

    async def fake_run_agent_chat(**kwargs):
        captured.update(kwargs)
        return {
            "answer": "我会结合当前行程给出建议。",
            "sources": [],
            "model": "test-model",
            "context_labels": kwargs["context_labels"],
        }

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    async def override_current_user_uuid() -> str:
        return "context-test-user"

    app.dependency_overrides[get_current_user_uuid] = override_current_user_uuid
    monkeypatch.setattr(
        chat,
        "_prepare_agent_runtime",
        lambda *_args: AgentRuntimePreparation(
            trace_id="test", personal_context='{"currentTrip": {}}',
            context_labels=["当前行程与日程", "明确旅行偏好"], events=[],
        ),
    )
    monkeypatch.setattr(chat, "run_agent_chat", fake_run_agent_chat)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "messages": [{"role": "user", "content": "看看我今天的行程"}],
                "usePersonalContext": True,
            },
        )

    assert response.status_code == 200
    assert captured["personal_context"] == '{"currentTrip": {}}'
    assert response.json()["contextLabels"] == ["当前行程与日程", "明确旅行偏好"]


def test_stream_emits_runtime_events_before_agent_text(monkeypatch) -> None:
    """测试：Web 可先收到公开执行轨迹，再消费既有的逐字回答流。"""
    async def fake_stream_agent_chat(**_kwargs):
        yield 'data: {"type": "text", "content": "旅行建议"}\n\n'
        yield "data: [DONE]\n\n"

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    async def override_current_user_uuid() -> str:
        return "context-test-user"

    app.dependency_overrides[get_current_user_uuid] = override_current_user_uuid
    monkeypatch.setattr(
        chat,
        "_prepare_agent_runtime",
        lambda *_args: AgentRuntimePreparation(
            trace_id="test",
            personal_context=None,
            context_labels=[],
            events=[{"type": "agent.started", "label": "开始整理本轮旅行上下文"}],
        ),
    )
    monkeypatch.setattr(chat, "stream_agent_chat", fake_stream_agent_chat)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat/stream",
            json={"messages": [{"role": "user", "content": "推荐京都景点"}]},
        )

    assert response.status_code == 200
    assert response.text.index('"agent.started"') < response.text.index('"type": "text"')
