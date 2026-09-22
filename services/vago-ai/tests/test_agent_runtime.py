"""验证 Phase 10 Runtime 的工具边界、授权和失败降级。"""

import asyncio

from app.agent_runtime.registry import AgentTool, ToolRegistry
from app.agent_runtime.runtime import AgentRuntime, AgentRuntimePreparation, AgentRuntimeProgress


def test_runtime_respects_disabled_personal_context() -> None:
    """关闭全部授权时，Runtime 不读取领域数据且仍返回可用准备结果。"""
    runtime = AgentRuntime()

    preparation = runtime.prepare(
        None,
        "user-a",
        use_personal_context=False,
        use_rag=False,
    )

    assert preparation.personal_context is None
    assert preparation.context_labels == []
    assert [event["type"] for event in preparation.events] == ["agent.started", "agent.status"]


def test_runtime_continues_when_one_domain_tool_fails() -> None:
    """单一领域读取失败应成为 Observation，不阻断后续可用工具。"""
    def failing_tool(_db, _user_uuid, _state):
        raise RuntimeError("temporary failure")

    def preference_tool(_db, _user_uuid, _state):
        return {"hasExplicitPreference": True, "pace": "leisurely"}

    runtime = AgentRuntime(ToolRegistry([
        AgentTool("get_current_trip", "读取行程", failing_tool),
        AgentTool("get_recent_footprint", "读取足迹", lambda *_: None),
        AgentTool("get_user_preferences", "读取偏好", preference_tool),
        AgentTool("get_travel_memories", "读取回忆", lambda *_: []),
    ]))

    preparation = runtime.prepare(
        None,
        "user-a",
        use_personal_context=True,
        use_rag=False,
    )

    assert any(event["type"] == "tool.failed" and event["tool"] == "get_current_trip" for event in preparation.events)
    assert "明确旅行偏好" in preparation.context_labels
    assert preparation.personal_context is not None


def test_runtime_streams_tool_events_in_execution_order() -> None:
    """测试：流式 Runtime 必须在工具完成时立即输出事件，而不是事后批量返回。"""
    runtime = AgentRuntime(ToolRegistry([
        AgentTool("get_current_trip", "读取行程", lambda *_: {"currentTrip": None, "travelHistory": []}),
        AgentTool("get_recent_footprint", "读取足迹", lambda *_: None),
        AgentTool("get_user_preferences", "读取偏好", lambda *_: {"hasExplicitPreference": False}),
        AgentTool("get_travel_memories", "读取回忆", lambda *_: []),
    ]))

    async def collect():
        return [
            item async for item in runtime.stream_prepare(
                None,
                "user-a",
                use_personal_context=True,
                use_rag=False,
            )
        ]

    updates = asyncio.run(collect())
    events = [item.event for item in updates if isinstance(item, AgentRuntimeProgress)]
    preparation = next(item for item in updates if isinstance(item, AgentRuntimePreparation))

    assert [event["type"] for event in events[:4]] == [
        "agent.started", "agent.status", "tool.started", "tool.completed",
    ]
    assert events[2]["tool"] == events[3]["tool"] == "get_current_trip"
    assert preparation.personal_context is not None
