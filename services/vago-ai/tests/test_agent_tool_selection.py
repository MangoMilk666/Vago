"""验证 Phase 10.1 的 prompt-aware 确定性工具选择策略。"""

from app.agent_runtime.selection import ToolSelectionPolicy


def test_general_question_selects_no_personal_tool() -> None:
    """测试：通用目的地问题不因用户已授权就读取个人数据。"""
    plan = ToolSelectionPolicy().select(
        "推荐京都适合秋天去的景点",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ()
    assert plan.intent == "general"
    assert plan.allow_rag_search is True


def test_current_trip_question_selects_only_trip_context() -> None:
    """测试：当前行程问题不应顺带读取足迹、偏好或回忆。"""
    plan = ToolSelectionPolicy().select(
        "我当前行程还剩什么安排？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_trip",)
    assert plan.allow_rag_search is True


def test_live_travel_question_keeps_trip_dependency_order() -> None:
    """测试：实时足迹必须先取得当前 Trip，随后才能安全读取对应观察。"""
    plan = ToolSelectionPolicy().select(
        "我今天走过哪里，足迹有记录吗？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_trip", "get_recent_footprint")


def test_personal_history_and_preference_selects_related_tools() -> None:
    """测试：个性化推荐只读取历史与明确偏好，不读取实时 GPS。"""
    plan = ToolSelectionPolicy().select(
        "结合我的旅行历史和旅行习惯，推荐下次去哪里？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_trip", "get_user_preferences")


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

    assert follow_up_plan.tool_names == ("get_current_trip",)
    assert standalone_plan.tool_names == ()


def test_disabled_authorization_overrides_matching_prompt() -> None:
    """测试：授权关闭是硬边界，意图命中也不得返回领域工具。"""
    plan = ToolSelectionPolicy().select(
        "我今天的足迹和打卡记录怎么样？",
        use_personal_context=False,
        use_rag=True,
    )

    assert plan.tool_names == ()


def test_current_itinerary_keeps_rag_available_for_agent_choice() -> None:
    """测试：当前日程读取结构化事实，但用户授权后仍保留 RAG 工具供 Agent 按需选择。"""
    plan = ToolSelectionPolicy().select(
        "当前的日程呢？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ("get_current_trip",)
    assert plan.allow_rag_search is True


def test_personal_document_question_keeps_rag_available() -> None:
    """测试：用户询问已保存资料时，保留 LangChain RAG 工具。"""
    plan = ToolSelectionPolicy().select(
        "我保存的京都攻略里有什么餐厅推荐？",
        use_personal_context=True,
        use_rag=True,
    )

    assert plan.tool_names == ()
    assert plan.allow_rag_search is True
