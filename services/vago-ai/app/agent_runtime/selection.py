"""Phase 10.2.1 的确定性工具选择策略。

授权仅定义可读取范围；工具调用携带明确的查询参数，普通问题可返回零工具计划。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


CURRENT_ACTIVE_TRIP_REFERENCE = "$current_active_trip"
CURRENT_DATE_REFERENCE = "$current_date"
# `recent`相关tool的recent范围
DEFAULT_RECENT_LIMIT = 3


@dataclass(frozen=True)
class ToolCall:
    """一次受 allowlist 约束的领域读取；arguments 仅包含安全、结构化的查询范围。"""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSelectionPlan:
    """本轮候选只读调用计划；空调用列表是正常结果。"""

    intent: str
    tool_calls: tuple[ToolCall, ...]
    # 是否允许既有 LangChain 注册个人知识 RAG 工具；是否实际调用由 LLM 根据本轮问题决定。
    allow_rag_search: bool

    @property
    def tool_names(self) -> tuple[str, ...]:
        """兼容日志与测试的稳定工具名视图。"""
        return tuple(call.name for call in self.tool_calls)


class ToolSelectionPolicy:
    """用确定性规则选择必要工具，不为路由本身额外消耗一次 LLM 调用。"""

    _CURRENT_TRIP_TERMS = (
        "当前行程", "我的行程", "本次行程", "这次行程", "今天的行程", "今天行程",
    )
    _ITINERARY_TERMS = (
        "当前日程", "当前的日程", "我的日程", "今日日程", "今天安排", "今天有什么安排",
        "接下来", "还剩", "剩余", "行程里", "日程里", "安排",
    )
    _FOOTPRINT_TERMS = (
        "足迹", "我在哪", "当前位置", "现在在哪", "轨迹", "记录点", "走过", "去了哪里",
    )
    _CHECKIN_TERMS = ("打卡", "签到")
    _RECENT_TERMS = ("最近", "上次", "最近一次", "最新")
    _PREFERENCE_TERMS = (
        "旅行偏好", "我的偏好", "旅行习惯", "我的习惯", "旅行风格", "我的风格",
        "我的节奏", "根据我的", "适合我",
    )
    _HISTORY_TERMS = (
        "旅行历史", "历史行程", "上次旅行", "之前旅行", "过去旅行", "以前旅行",
        "去过的", "我曾去过", "已结束的",
    )
    _MEMORY_TERMS = ("旅行回忆", "旅行记忆", "回忆", "纪念")
    _FOLLOW_UP_TERMS = ("那明天", "那今天", "还有呢", "然后呢", "继续", "刚才", "这个", "那个")

    def select(
        self,
        prompt: str,
        *,
        recent_user_messages: Sequence[str] = (),
        use_personal_context: bool,
        use_rag: bool,
    ) -> ToolSelectionPlan:
        """从当前 prompt 选择工具；只有明显的追问才借用有限历史恢复指代。"""
        # 如果用户未授权旅行上下文，硬性返回零领域工具计划。
        if not use_personal_context:
            return ToolSelectionPlan(intent="general", tool_calls=(), allow_rag_search=use_rag)

        normalized_prompt = _normalize(prompt)
        routed_text = normalized_prompt
        # 如果短追问省略当前行程等主语，才使用有限用户消息恢复指代。
        if _contains_any(normalized_prompt, self._FOLLOW_UP_TERMS):
            recent_context = " ".join(_normalize(message) for message in recent_user_messages[-3:])
            routed_text = f"{recent_context} {normalized_prompt}".strip()

        is_footprint = _contains_any(routed_text, self._FOOTPRINT_TERMS)
        is_checkins = _contains_any(routed_text, self._CHECKIN_TERMS)
        is_recent = _contains_any(routed_text, self._RECENT_TERMS)
        is_current_trip = _contains_any(routed_text, self._CURRENT_TRIP_TERMS)
        is_itinerary = _contains_any(routed_text, self._ITINERARY_TERMS)
        is_preferences = _contains_any(routed_text, self._PREFERENCE_TERMS)
        is_history = _contains_any(routed_text, self._HISTORY_TERMS)
        is_memory = _contains_any(routed_text, self._MEMORY_TERMS)

        selected: list[ToolCall] = []
        # 如果问题询问最近足迹，按 Observation 时间倒序读取最近有足迹的 Trip，不依赖当前行程。
        if is_footprint and is_recent:
            selected.append(_tool_call("get_recent_footprint_summaries", limit=DEFAULT_RECENT_LIMIT))
        # 如果问题询问当前足迹，先确认进行中 Trip，再按明确 Trip UUID 读取摘要。
        elif is_footprint:
            selected.extend((_current_active_trip_call(), _current_trip_footprint_call()))

        # 如果问题询问最近打卡，按 checkin点位的 时间倒序读取有限打卡，不依赖当前行程。
        if is_checkins and is_recent:
            selected.append(_tool_call("get_recent_checkins", limit=DEFAULT_RECENT_LIMIT))
        # 如果问题询问当前打卡，先确认进行中 Trip，再按明确 Trip UUID 读取打卡。
        elif is_checkins:
            selected.extend((_current_active_trip_call(), _current_trip_checkins_call()))

        # 如果问题要求日程，先确认进行中 Trip，再按当前日期读取单日安排。
        if is_itinerary:
            selected.extend((_current_active_trip_call(), _tool_call(
                "get_trip_itinerary_by_date",
                tripUuid=CURRENT_ACTIVE_TRIP_REFERENCE,
                date=CURRENT_DATE_REFERENCE,
            )))
        # 如果问题仅询问当前行程基础事实，避免重复加入已经作为依赖选择的工具。
        elif is_current_trip:
            selected.append(_current_active_trip_call())

        # 如果问题涉及历史旅行，按 Trip 创建时间倒序读取有限摘要。
        if is_history:
            selected.append(_tool_call("get_recent_trips", limit=DEFAULT_RECENT_LIMIT))
        # 如果问题需要个性化建议，才读取用户明确确认的偏好。
        if is_preferences:
            selected.append(_tool_call("get_user_preferences"))
        # 如果问题明确询问回忆，才读取 grounded Memory 摘要。
        if is_memory:
            selected.append(_tool_call("get_travel_memories"))

        tool_calls = tuple(_deduplicate_tool_calls(selected))
        return ToolSelectionPlan(
            intent=_intent_name(tuple(call.name for call in tool_calls)),
            tool_calls=tool_calls,
            allow_rag_search=use_rag,
        )


def _current_active_trip_call() -> ToolCall:
    """返回无需参数的当前进行中 Trip 读取调用。"""
    return _tool_call("get_current_active_trip")


def _current_trip_footprint_call() -> ToolCall:
    """返回绑定前序当前 Trip Observation 的足迹摘要调用。"""
    return _tool_call("get_footprint_summary_by_trip", tripUuid=CURRENT_ACTIVE_TRIP_REFERENCE)


def _current_trip_checkins_call() -> ToolCall:
    """返回绑定前序当前 Trip Observation 的有限打卡读取调用。"""
    return _tool_call(
        "get_checkins_by_trip",
        tripUuid=CURRENT_ACTIVE_TRIP_REFERENCE,
        limit=DEFAULT_RECENT_LIMIT,
    )


def _tool_call(name: str, **arguments: Any) -> ToolCall:
    """构造稳定工具调用，避免在策略分支中散落可变字典字面量。"""
    return ToolCall(name=name, arguments=arguments)


def _deduplicate_tool_calls(calls: list[ToolCall]) -> list[ToolCall]:
    """按工具名与参数去重，保留确定性选择顺序。"""
    unique_calls: list[ToolCall] = []
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for call in calls:
        key = (call.name, tuple(sorted((name, str(value)) for name, value in call.arguments.items())))
        # 如果同一工具已携带相同参数加入计划，避免重复读取同一份事实。
        if key in seen:
            continue
        seen.add(key)
        unique_calls.append(call)
    return unique_calls


def _normalize(text: str) -> str:
    """归一化空白与大小写，避免展示层输入格式影响中文意图规则。"""
    return "".join(text.lower().split())


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    """判断文本是否匹配任一预设关键词。"""
    return any(term in text for term in terms)


def _intent_name(tool_names: tuple[str, ...]) -> str:
    """为日志与未来评估提供稳定意图名，不向客户端暴露模型推理。"""
    # 如果没有工具调用，归类为通用问题。
    if not tool_names:
        return "general"
    # 如果包含最近或按 Trip 的空间观察工具，归类为实时旅行问题。
    if any(name in tool_names for name in {
        "get_recent_footprint_summaries", "get_recent_checkins",
        "get_footprint_summary_by_trip", "get_checkins_by_trip",
    }):
        return "live_travel"
    # 如果包含按日期日程工具，归类为当前日程问题。
    if "get_trip_itinerary_by_date" in tool_names:
        return "current_itinerary"
    # 如果包含最近 Trip 工具，归类为旅行历史问题。
    if "get_recent_trips" in tool_names:
        return "travel_history"
    if "get_user_preferences" in tool_names:
        return "personal_preferences"
    if "get_travel_memories" in tool_names:
        return "travel_memory"
    return "current_trip"
