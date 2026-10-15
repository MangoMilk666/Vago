"""验证 Phase 10.2.1 的参数化确定性工具选择策略。"""

from datetime import date

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
        "我当前行程的足迹有记录吗？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_active_trip", "get_footprint_summary_by_trip")
    assert plan.tool_calls[1].arguments == {"tripUuid": CURRENT_ACTIVE_TRIP_REFERENCE}


def test_current_place_question_also_reads_named_checkins() -> None:
    """测试：当前行程的地点回答需要命名打卡作为地点证据，不能只读取 GPS 数量。"""
    plan = ToolSelectionPolicy().select(
        "我当前行程去了哪些地方？",
        use_personal_context=True,
        use_rag=False,
    )

    assert plan.tool_names == (
        "get_current_active_trip",
        "get_footprint_summary_by_trip",
        "get_checkins_by_trip",
    )


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


def test_ended_trip_place_question_clarifies_without_partial_trip_list() -> None:
    """测试：已结束行程的地点范围不明时先澄清，不用 Trip 列表猜测到访地点。"""
    plan = ToolSelectionPolicy().select(
        "我已经结束的行程，去了哪些地方？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_calls == ()
    assert plan.clarification is not None


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
    assert follow_up_plan.tool_calls[1].arguments["date"] == "2026-10-07"
    assert standalone_plan.tool_calls == ()


def test_explicit_date_and_relative_date_select_the_requested_itinerary_day() -> None:
    """测试：日程目标日期从当前问题解析，不能继承历史中的今天。"""
    policy = ToolSelectionPolicy()
    tomorrow = policy.select(
        "那明天呢？",
        recent_user_messages=("看看我今天的行程安排",),
        use_personal_context=True,
        use_rag=False,
        today=date(2026, 10, 6),
    )
    explicit_date = policy.select(
        "看看我 2026年10月9日 的日程",
        use_personal_context=True,
        use_rag=False,
        today=date(2026, 10, 6),
    )

    assert tomorrow.tool_calls[-1].arguments["date"] == "2026-10-07"
    assert explicit_date.tool_calls[-1].arguments["date"] == "2026-10-09"


def test_historical_checkin_query_uses_date_and_location_scope() -> None:
    """测试：历史打卡按用户指定的日期和地点查询，不依赖当前行程或最近几条。"""
    plan = ToolSelectionPolicy().select(
        "我上周在东京打卡了哪里？",
        use_personal_context=True,
        use_rag=False,
        today=date(2026, 10, 6),
    )

    assert plan.tool_names == ("get_checkins_by_date_range",)
    assert plan.tool_calls[0].arguments == {
        "startDate": "2026-09-28",
        "endDate": "2026-10-04",
        "locationQuery": "东京",
        "limit": 20,
    }


def test_ambiguous_historical_checkin_requests_clarification_without_fallback() -> None:
    """测试：没有日期或明确当前行程时，不把当前 Trip 冒充历史检索范围。"""
    plan = ToolSelectionPolicy().select(
        "我以前在哪里打卡过？",
        use_personal_context=True,
        use_rag=False,
    )

    assert plan.tool_calls == ()
    assert plan.clarification is not None


def test_generic_destination_planning_does_not_read_current_itinerary() -> None:
    """测试：泛用安排京都旅行不因“安排”一词读取现有日程。"""
    plan = ToolSelectionPolicy().select(
        "请帮我安排一趟京都旅行",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_calls == ()


def test_generic_place_checkin_recommendation_does_not_request_personal_history() -> None:
    """测试：泛用目的地打卡推荐不是个人历史查询，不应触发澄清或领域工具。"""
    for prompt in ("京都有哪些地方值得打卡？", "京都最近有哪些地方值得打卡？"):
        plan = ToolSelectionPolicy().select(
            prompt,
            use_personal_context=True,
            use_rag=False,
        )

        assert plan.tool_calls == ()
        assert plan.clarification is None


def test_personal_historical_checkin_still_uses_date_and_place_scope() -> None:
    """测试：通用推荐豁免不影响明确的个人历史打卡查询。"""
    plan = ToolSelectionPolicy().select(
        "我上周在京都打卡了哪里？",
        use_personal_context=True,
        use_rag=False,
        today=date(2026, 10, 6),
    )

    assert plan.tool_names == ("get_checkins_by_date_range",)
    assert plan.tool_calls[0].arguments["locationQuery"] == "京都"


def test_personal_historical_checkin_recommendation_overrides_generic_recommendation() -> None:
    """测试：第一人称、日期和打卡共同限定个人历史时，推荐词不能关闭个人读取。"""
    plan = ToolSelectionPolicy().select(
        "我上周在东京打卡的地方，推荐哪个给朋友？",
        use_personal_context=True,
        use_rag=False,
        today=date(2026, 10, 6),
    )

    assert plan.tool_names == ("get_checkins_by_date_range",)
    assert plan.tool_calls[0].arguments == {
        "startDate": "2026-09-28",
        "endDate": "2026-10-04",
        "locationQuery": "东京",
        "limit": 20,
    }


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
