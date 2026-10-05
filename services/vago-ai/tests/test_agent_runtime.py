"""验证 Phase 10.2.1 Runtime 的工具边界、预算与 Observation 链。"""

import asyncio
from typing import Any

from app.agent_runtime.registry import AgentTool, ToolRegistry
from app.agent_runtime.runtime import AgentRuntime, AgentRuntimePreparation, AgentRuntimeProgress


ALL_TOOL_NAMES = (
    "get_current_active_trip",
    "get_trip_itinerary_by_date",
    "get_recent_trips",
    "get_recent_ended_trips",
    "get_footprint_summary_by_trip",
    "get_checkins_by_trip",
    "get_recent_footprint_summaries",
    "get_recent_checkins",
    "get_user_preferences",
    "get_travel_memories",
)


def _registry(overrides: dict[str, Any]) -> ToolRegistry:
    """构造完整测试注册表，未覆盖工具默认返回空 Observation。"""
    def empty_handler(*_args: Any) -> None:
        return None

    return ToolRegistry([
        AgentTool(name, f"读取 {name}", overrides.get(name, empty_handler))
        for name in ALL_TOOL_NAMES
    ])


def test_runtime_respects_disabled_personal_context() -> None:
    """测试：关闭全部授权时，Runtime 不读取领域数据且仍返回可用准备结果。"""
    preparation = AgentRuntime().prepare(
        None,
        "user-a",
        use_personal_context=False,
        use_rag=False,
        prompt="看看我今天的行程",
    )

    assert preparation.personal_context is None
    assert preparation.context_labels == []
    assert [event["type"] for event in preparation.events] == ["agent.started", "agent.status"]


def test_runtime_continues_when_one_domain_tool_fails() -> None:
    """测试：单一领域读取失败应成为 Observation，不阻断后续可用工具。"""
    def failing_tool(*_args: Any) -> None:
        raise RuntimeError("temporary failure")

    def preference_tool(*_args: Any) -> dict[str, Any]:
        return {"hasExplicitPreference": True, "pace": "leisurely"}

    runtime = AgentRuntime(_registry({
        "get_current_active_trip": failing_tool,
        "get_user_preferences": preference_tool,
    }))
    preparation = runtime.prepare(
        None,
        "user-a",
        use_personal_context=True,
        use_rag=False,
        prompt="我这次行程和旅行习惯应该怎么安排？",
    )

    assert any(event["type"] == "tool.failed" and event["tool"] == "get_current_active_trip" for event in preparation.events)
    assert "明确旅行偏好" in preparation.context_labels


def test_runtime_streams_tool_events_in_execution_order() -> None:
    """测试：流式 Runtime 必须在工具完成时立即输出事件，而不是事后批量返回。"""
    runtime = AgentRuntime(_registry({
        "get_current_active_trip": lambda *_args: {"uuid": "trip-a"},
    }))

    async def collect() -> list[AgentRuntimeProgress | AgentRuntimePreparation]:
        return [
            item async for item in runtime.stream_prepare(
                None,
                "user-a",
                use_personal_context=True,
                use_rag=False,
                prompt="我当前行程是什么？",
            )
        ]

    updates = asyncio.run(collect())
    events = [item.event for item in updates if isinstance(item, AgentRuntimeProgress)]
    preparation = next(item for item in updates if isinstance(item, AgentRuntimePreparation))

    assert [event["type"] for event in events[:4]] == [
        "agent.started", "agent.status", "tool.started", "tool.completed",
    ]
    assert events[2]["tool"] == events[3]["tool"] == "get_current_active_trip"
    assert preparation.personal_context is not None


def test_runtime_skips_personal_tools_for_general_question() -> None:
    """测试：普通旅行知识问题在已授权状态下也应保持零领域读取。"""
    calls: list[str] = []

    def record(name: str, result: Any):
        def handler(*_args: Any) -> Any:
            calls.append(name)
            return result

        return handler

    runtime = AgentRuntime(_registry({
        "get_current_active_trip": record("get_current_active_trip", {"uuid": "trip-a"}),
    }))
    preparation = runtime.prepare(
        None,
        "user-a",
        use_personal_context=True,
        use_rag=True,
        prompt="新加坡十月天气怎么样？",
    )

    assert calls == []
    assert preparation.personal_context is None


def test_runtime_reads_current_trip_before_by_trip_observations() -> None:
    """测试：当前足迹与打卡先建立 Trip Observation，再按明确 tripUuid 查询。"""
    calls: list[tuple[str, dict[str, Any]]] = []

    def current_trip(*_args: Any) -> dict[str, str]:
        calls.append(("get_current_active_trip", {}))
        return {"uuid": "trip-a"}

    def footprint(_db: Any, _user: str, _state: dict[str, Any], arguments: dict[str, Any]) -> dict[str, int]:
        calls.append(("get_footprint_summary_by_trip", arguments))
        return {"automaticSampleCount": 3}

    def checkins(_db: Any, _user: str, _state: dict[str, Any], arguments: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        calls.append(("get_checkins_by_trip", arguments))
        return {"recentCheckins": [{"locationName": "滨海湾花园"}]}

    runtime = AgentRuntime(_registry({
        "get_current_active_trip": current_trip,
        "get_footprint_summary_by_trip": footprint,
        "get_checkins_by_trip": checkins,
    }))
    runtime.prepare(
        None,
        "user-a",
        use_personal_context=True,
        use_rag=False,
        prompt="我今天的足迹和打卡记录怎么样？",
    )

    assert calls == [
        ("get_current_active_trip", {}),
        ("get_footprint_summary_by_trip", {"tripUuid": "trip-a"}),
        ("get_checkins_by_trip", {"tripUuid": "trip-a", "limit": 3}),
    ]


def test_runtime_skips_by_trip_tools_without_an_active_trip() -> None:
    """测试：当前 Trip Observation 为空时，不调用依赖当前 Trip 的工具。"""
    calls: list[str] = []

    def record(name: str, result: Any):
        def handler(*_args: Any) -> Any:
            calls.append(name)
            return result

        return handler

    runtime = AgentRuntime(_registry({
        "get_current_active_trip": record("get_current_active_trip", None),
        "get_footprint_summary_by_trip": record("get_footprint_summary_by_trip", {}),
        "get_checkins_by_trip": record("get_checkins_by_trip", {}),
    }))
    preparation = runtime.prepare(
        None,
        "user-a",
        use_personal_context=True,
        use_rag=False,
        prompt="我今天的足迹和打卡记录怎么样？",
    )

    assert calls == ["get_current_active_trip"]
    assert any("跳过当前行程足迹读取" in event["label"] for event in preparation.events)
    assert any("跳过当前行程打卡读取" in event["label"] for event in preparation.events)


def test_runtime_continues_after_initial_budget_when_more_selected_facts_are_needed() -> None:
    """测试：初始三次读取后，明确选中的历史与偏好可在总预算内继续读取。"""
    calls: list[str] = []

    def record(name: str, result: Any):
        def handler(*_args: Any) -> Any:
            calls.append(name)
            return result

        return handler

    runtime = AgentRuntime(_registry({
        "get_current_active_trip": record("get_current_active_trip", {"uuid": "trip-a"}),
        "get_footprint_summary_by_trip": record("get_footprint_summary_by_trip", {"automaticSampleCount": 2}),
        "get_checkins_by_trip": record("get_checkins_by_trip", {"recentCheckins": []}),
        "get_trip_itinerary_by_date": record("get_trip_itinerary_by_date", {"dayIndex": 1, "spots": []}),
        "get_recent_trips": record("get_recent_trips", [{"uuid": "trip-old"}]),
    }))
    preparation = runtime.prepare(
        None,
        "user-a",
        use_personal_context=True,
        use_rag=False,
        prompt="我当前日程、足迹、打卡和旅行历史是什么？",
    )

    assert calls == [
        "get_current_active_trip",
        "get_footprint_summary_by_trip",
        "get_checkins_by_trip",
        "get_trip_itinerary_by_date",
        "get_recent_trips",
    ]
    assert any("已完成初始资料读取" in event["label"] for event in preparation.events)


def test_runtime_stops_after_total_read_budget() -> None:
    """测试：候选工具超过总预算时，不执行第七次读取并公开信息边界。"""
    calls: list[str] = []

    def record(name: str, result: Any):
        def handler(*_args: Any) -> Any:
            calls.append(name)
            return result

        return handler

    runtime = AgentRuntime(_registry({
        "get_current_active_trip": record("get_current_active_trip", {"uuid": "trip-a"}),
        "get_footprint_summary_by_trip": record("get_footprint_summary_by_trip", {"automaticSampleCount": 1}),
        "get_checkins_by_trip": record("get_checkins_by_trip", {"recentCheckins": []}),
        "get_trip_itinerary_by_date": record("get_trip_itinerary_by_date", {"dayIndex": 1, "spots": []}),
        "get_recent_trips": record("get_recent_trips", [{"uuid": "trip-old"}]),
        "get_user_preferences": record("get_user_preferences", {"hasExplicitPreference": True}),
        "get_travel_memories": record("get_travel_memories", [{"title": "旧旅行"}]),
    }))
    preparation = runtime.prepare(
        None,
        "user-a",
        use_personal_context=True,
        use_rag=False,
        prompt="我当前日程、足迹、打卡、旅行历史、旅行习惯和旅行回忆是什么？",
    )

    assert len(calls) == 6
    assert "get_travel_memories" not in calls
    assert any("已达到本轮读取总预算" in event["label"] for event in preparation.events)
