"""验证 Phase 10.2.1 的参数化确定性工具选择策略。"""

from app.agent_runtime.selection import (
    CURRENT_ACTIVE_TRIP_REFERENCE,
    CURRENT_DATE_REFERENCE,
    ToolSelectionPolicy,
)


def test_general_question_selects_no_personal_tool() -> None:
    """测试：通用目的地问题不因用户已授权就读取个人数据。"""
    plan = ToolSelectionPolicy().select(
        "推荐京都适合秋天去的景点",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_calls == ()
    assert plan.intent == "general"
    assert plan.allow_rag_search is True


def test_current_itinerary_uses_explicit_trip_and_date_references() -> None:
    """测试：当前日程必须先取进行中 Trip，再以显式引用查询指定日期。"""
    plan = ToolSelectionPolicy().select(
        "我当前行程还剩什么安排？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_active_trip", "get_trip_itinerary_by_date")
    assert plan.tool_calls[1].arguments == {
        "tripUuid": CURRENT_ACTIVE_TRIP_REFERENCE,
        "date": CURRENT_DATE_REFERENCE,
    }


def test_current_footprint_uses_explicit_trip_reference() -> None:
    """测试：当前足迹依赖进行中 Trip，不再使用含混的 recent 工具名。"""
    plan = ToolSelectionPolicy().select(
        "我今天走过哪里，足迹有记录吗？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_active_trip", "get_footprint_summary_by_trip")
    assert plan.tool_calls[1].arguments == {"tripUuid": CURRENT_ACTIVE_TRIP_REFERENCE}


def test_recent_footprint_uses_limit_without_active_trip_dependency() -> None:
    """测试：最近足迹按 Observation 倒序读取有限 Trip，不依赖当前进行中 Trip。"""
    plan = ToolSelectionPolicy().select(
        "最近的足迹记录是什么？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_recent_footprint_summaries",)
    assert plan.tool_calls[0].arguments == {"limit": 3}


def test_personal_history_and_preference_selects_limited_recent_trips() -> None:
    """测试：个性化推荐只读取有限最近 Trip 与明确偏好，不读取实时 GPS。"""
    plan = ToolSelectionPolicy().select(
        "结合我的旅行历史和旅行习惯，推荐下次去哪里？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_recent_trips", "get_user_preferences")
    assert plan.tool_calls[0].arguments == {"limit": 3}


def test_ended_trip_question_selects_only_ended_trip_history() -> None:
    """测试：用户询问已经结束的行程时，只读取状态为已结束的有限 Trip。"""
    plan = ToolSelectionPolicy().select(
        "我已经结束的行程，去了哪些地方？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.intent == "travel_history"
    assert plan.tool_names == ("get_recent_ended_trips",)
    assert plan.tool_calls[0].arguments == {"limit": 3}


def test_follow_up_uses_recent_user_context_only_when_needed() -> None:
    """测试：短追问可继承最近用户问题的指代，普通新问题不会扩大读取范围。"""
    policy = ToolSelectionPolicy()

    follow_up_plan = policy.select(
        "那明天呢？",
        recent_user_messages=("看看我今天的行程安排",),
        use_personal_context=True,
        use_rag=True,
    )
    standalone_plan = policy.select(
        "推荐东京美食",
        recent_user_messages=("看看我今天的行程安排",),
        use_personal_context=True,
        use_rag=True,
    )

    assert follow_up_plan.tool_names == ("get_current_active_trip", "get_trip_itinerary_by_date")
    assert standalone_plan.tool_calls == ()


def test_disabled_authorization_overrides_matching_prompt() -> None:
    """测试：授权关闭是硬边界，意图命中也不得返回领域工具。"""
    plan = ToolSelectionPolicy().select(
        "我今天的足迹和打卡记录怎么样？",
        use_personal_context=False,
        use_rag=True,
    )

    assert plan.tool_calls == ()


def test_current_itinerary_keeps_rag_available_for_agent_choice() -> None:
    """测试：结构化日程读取不关闭已授权的 RAG 按需能力。"""
    plan = ToolSelectionPolicy().select(
        "当前的日程呢？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_active_trip", "get_trip_itinerary_by_date")
    assert plan.allow_rag_search is True
