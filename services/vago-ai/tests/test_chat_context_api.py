"""验证 AI 对话将个人资料检索开关传递给上下文层。"""

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import api_v1_router
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import get_current_user_uuid
from app.agent_runtime.runtime import AgentRuntimePreparation
from app.models.schemas import ChatMessage, ChatRequest
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


def test_chat_keeps_rag_available_for_structured_context_question(monkeypatch) -> None:
    """测试：结构化日程读取后，用户授权的 RAG 工具仍可由 LLM 按需选择。"""
    captured: dict[str, object] = {}

    async def fake_run_agent_chat(**kwargs):
        captured.update(kwargs)
        return {"answer": "今天暂无日程", "sources": [], "model": "test-model"}

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
            trace_id="test", personal_context='{"currentTrip": {}}', context_labels=["当前行程与日程"], events=[],
            allow_rag_search=True,
        ),
    )
    monkeypatch.setattr(chat, "run_agent_chat", fake_run_agent_chat)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "messages": [{"role": "user", "content": "当前的日程呢？"}],
                "usePersonalContext": True,
                "useRag": True,
            },
        )

    assert response.status_code == 200
    assert captured["use_rag"] is True


def test_stream_emits_clarification_before_completion() -> None:
    """测试：真实 LangGraph 对未明确范围的问题先发送澄清，再结束 SSE。"""
    async def collect() -> str:
        response = await chat.chat_stream(
            ChatRequest(
                messages=[ChatMessage(role="user", content="我以前在哪里打卡过？")],
                usePersonalContext=True, useRag=False,
            ),
            db=None,
            user_uuid="context-test-user",
        )
        return "".join([chunk async for chunk in response.body_iterator])

    response_text = asyncio.run(collect())
    assert response_text.index('"agent.clarification"') < response_text.index('"type": "text"')
    assert response_text.endswith("data: [DONE]\n\n")
