import asyncio
import json

import pytest

from app.agent_runtime.graph import PlanningGraphRuntime
from app.agent_runtime.spec import AgentSpec, AgentSpecRegistry, planner_spec
from app.agent_runtime.runtime import AgentRuntime
from app.models.schemas import ChatMessage


def test_planner_spec_rejects_unregistered_tools() -> None:
    """测试：配置了不存在的领域工具时，Agent 不能启动。"""
    tools = AgentRuntime().registry
    spec = AgentSpec(role="planner", description="规划", allowed_tools=frozenset({"unknown_tool"}))
    with pytest.raises(ValueError, match="未注册工具"):
        AgentSpecRegistry([spec], tools)


def test_planner_spec_has_bounded_registered_tools() -> None:
    """测试：主 Agent 仅获得明确注册的只读工具与可选知识检索。"""
    tools = AgentRuntime().registry
    spec = planner_spec(tools)
    assert spec.max_read_steps == 6
    assert spec.max_model_steps == 3
    assert spec.allowed_tools == tools.names | {"search_personal_knowledge"}


def test_graph_clarifies_ambiguous_travel_history_without_model_or_database() -> None:
    """测试：不明确的历史范围由图返回澄清，结束事件完整且无需调用模型。"""
    async def collect() -> list[dict | str]:
        chunks = [
            chunk async for chunk in PlanningGraphRuntime(None, "user-a").stream(
                messages=[ChatMessage(role="user", content="我以前在哪里打卡过？")],
                use_personal_context=True, use_rag=False, conversation_uuid=None,
            )
        ]
        return [json.loads(chunk[5:].strip()) if chunk.strip() != "data: [DONE]" else "[DONE]" for chunk in chunks]

    events = asyncio.run(collect())
    assert any(event.get("type") == "agent.clarification" for event in events if isinstance(event, dict))
    assert any(event.get("type") == "text" and "日期范围" in event["content"] for event in events if isinstance(event, dict))
    numbered = [event for event in events if isinstance(event, dict)]
    assert [event["sequence"] for event in numbered] == list(range(1, len(numbered) + 1))
    assert len({event["turnUuid"] for event in numbered}) == 1
    assert numbered[-1]["type"] == "agent.completed"
    assert events[-1] == "[DONE]"


def test_graph_rejects_tool_outside_agent_whitelist() -> None:
    """测试：用户请求未授权工具时，图在执行前停止并返回公开错误。"""
    async def collect() -> list[str]:
        spec = AgentSpec(role="planner", description="仅允许偏好", allowed_tools=frozenset({"get_user_preferences"}))
        return [
            chunk async for chunk in PlanningGraphRuntime(None, "user-a", spec).stream(
                messages=[ChatMessage(role="user", content="我当前行程是什么？")],
                use_personal_context=True, use_rag=False, conversation_uuid=None,
            )
        ]

    events = asyncio.run(collect())
    assert any('"type": "error"' in event for event in events)
    assert events[-1].strip() == "data: [DONE]"
