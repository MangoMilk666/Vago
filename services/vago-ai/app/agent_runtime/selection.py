"""Phase 10.2.1 的确定性工具选择策略。

授权仅定义可读取范围；工具调用携带明确的查询参数，普通问题可返回零工具计划。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import re
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
    clarification: str | None = None

    @property
    def tool_names(self) -> tuple[str, ...]:
        """兼容日志与测试的稳定工具名视图。"""
        return tuple(call.name for call in self.tool_calls)


class ToolSelectionPolicy:
    """用确定性规则选择必要工具，不为路由本身额外消耗一次 LLM 调用。"""

    _CURRENT_TRIP_TERMS = (
        "当前行程", "当前日程", "当前的日程", "我的行程", "本次行程", "这次行程", "今天的行程", "今天行程",
    )
    _ITINERARY_TERMS = (
        "当前日程", "当前的日程", "我的日程", "今日日程", "今天安排", "今天有什么安排",
        "日程安排", "行程安排", "接下来", "还剩", "剩余", "行程里", "日程里",
    )
    _FOOTPRINT_TERMS = (
        "足迹", "我在哪", "当前位置", "现在在哪", "轨迹", "记录点", "走过", "去了哪里", "哪些地方", "什么地方",
    )
    _CHECKIN_TERMS = ("打卡", "签到")
    _PLACE_QUESTION_TERMS = ("哪里", "哪儿", "哪些地方", "什么地方", "去过什么")
    _PLACE_RECOMMENDATION_TERMS = ("值得", "推荐", "适合", "好玩的", "可以去")
    _PERSONAL_FOOTPRINT_TERMS = (
        "我的打卡", "我打卡", "我去过", "我去了", "我曾去", "我到过", "打卡过", "打卡了", "去了哪里",
        "我的足迹", "我的轨迹", "旅行历史", "历史行程", "当前行程", "本次行程", "这次行程",
        "记录",
    )
    _RECENT_TERMS = ("最近", "上次", "最近一次", "最新")
    _PREFERENCE_TERMS = (
        "旅行偏好", "我的偏好", "旅行习惯", "我的习惯", "旅行风格", "我的风格",
        "我的节奏", "根据我的", "适合我",
    )
    _HISTORY_TERMS = (
        "旅行历史", "历史行程", "上次旅行", "之前旅行", "过去旅行", "以前旅行",
        "去过的", "我曾去过",
    )
    _ENDED_TRIP_TERMS = (
        "已结束的", "已经结束的", "已结束行程", "结束的行程", "已完成的", "完成的旅行",
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
        today: date | None = None,
    ) -> ToolSelectionPlan:
        """从当前 prompt 选择工具；只有明显的追问才借用有限历史恢复指代。"""
        # 如果用户未授权旅行上下文，硬性返回零领域工具计划。
        if not use_personal_context:
            return ToolSelectionPlan(intent="general", tool_calls=(), allow_rag_search=use_rag)

        normalized_prompt = _normalize(prompt)
        reference_date = today or date.today()
        routed_text = normalized_prompt
        # 如果短追问省略当前行程等主语，才使用有限用户消息恢复指代。
        if _contains_any(normalized_prompt, self._FOLLOW_UP_TERMS):
            recent_context = " ".join(_normalize(message) for message in recent_user_messages[-3:])
            routed_text = f"{recent_context} {normalized_prompt}".strip()

        is_footprint = _contains_any(routed_text, self._FOOTPRINT_TERMS)
        is_checkins = _contains_any(routed_text, self._CHECKIN_TERMS)
        # 当前消息决定时间范围；历史里的“最近”不覆盖本轮明确的“上周/昨天”等限定。
        is_recent = _contains_any(normalized_prompt, self._RECENT_TERMS)
        is_current_trip = _contains_any(routed_text, self._CURRENT_TRIP_TERMS)
        is_itinerary = _contains_any(routed_text, self._ITINERARY_TERMS)
        is_preferences = _contains_any(routed_text, self._PREFERENCE_TERMS)
        is_history = _contains_any(routed_text, self._HISTORY_TERMS)
        is_ended_trip = _contains_any(routed_text, self._ENDED_TRIP_TERMS)
        is_memory = _contains_any(routed_text, self._MEMORY_TERMS)
        is_place_question = _contains_any(routed_text, self._PLACE_QUESTION_TERMS)
        # 追问只继承上一轮的主题；日期必须由当前消息明确给出，不能沿用上一轮的日历日。
        requested_range = _parse_date_range(prompt, reference_date)
        has_personal_date_scoped_checkins = "我" in normalized_prompt and is_checkins and requested_range is not None
        has_personal_footprint_scope = (
            _contains_any(normalized_prompt, self._PERSONAL_FOOTPRINT_TERMS)
            or has_personal_date_scoped_checkins
        )
        # 如果用户在问目的地推荐而非自己的旅行事实，不因“打卡/哪些地方”触发历史范围澄清。
        is_general_place_recommendation = (
            _contains_any(normalized_prompt, self._PLACE_RECOMMENDATION_TERMS)
            and not has_personal_footprint_scope
        )
        if is_general_place_recommendation:
            is_footprint = False
            is_checkins = False
        location_query = _extract_location_query(prompt)
        # 如果当前问题明确指定某天并询问日程，允许查询那一天；新旅行规划仍不读取现有 Trip。
        is_new_trip_planning = _contains_any(normalized_prompt, ("安排一趟", "安排一次", "规划一趟", "规划一次", "帮我规划"))
        if requested_range and requested_range[0] == requested_range[1] and _contains_any(prompt, ("日程", "行程安排")) and not is_new_trip_planning:
            is_itinerary = True

        selected: list[ToolCall] = []
        clarification: str | None = None
        # 如果问题询问最近足迹，按足迹发生时间倒序读取最近有足迹的 Trip，不依赖当前行程。
        if is_footprint and is_recent and requested_range is None:
            selected.append(_tool_call("get_recent_footprint_summaries", limit=DEFAULT_RECENT_LIMIT))
        # 如果问题询问当前足迹，先确认进行中 Trip，再按明确 Trip UUID 读取摘要。
        elif is_footprint and requested_range:
            start_date, end_date = requested_range
            selected.append(_tool_call(
                "get_footprints_by_date_range",
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                limit=20,
            ))
        elif is_footprint:
            if is_current_trip:
                selected.extend((_current_active_trip_call(), _current_trip_footprint_call()))
                # 如果用户问具体地点，同时读取命名打卡；GPS 数量本身不能证明地点。
                if is_place_question:
                    selected.append(_current_trip_checkins_call())
            else:
                clarification = "用户询问的足迹时间或行程范围不明确。请先询问日期范围或具体行程，不得用当前行程或 GPS 数量推断地点。"

        # 如果问题询问最近打卡，按 checkin点位的 时间倒序读取有限打卡，不依赖当前行程。
        if is_checkins and is_recent and requested_range is None:
            selected.append(_tool_call("get_recent_checkins", limit=DEFAULT_RECENT_LIMIT))
        # 如果问题指定日期范围，按用户所有 Trip 的发生时间筛打卡，不借用当前 Trip 或 recent top-N。
        elif is_checkins and requested_range:
            start_date, end_date = requested_range
            selected.append(_tool_call(
                "get_checkins_by_date_range",
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                locationQuery=location_query,
                limit=20,
            ))
        # 如果用户明确指向当前行程，才使用进行中 Trip 作为打卡查询范围。
        elif is_checkins and (is_current_trip or is_itinerary):
            selected.extend((_current_active_trip_call(), _current_trip_checkins_call()))
        elif is_checkins:
            clarification = "用户询问的打卡范围不明确。请先询问日期范围或具体行程；不得用当前行程或最近几条记录代替历史范围。"

        # 如果问题要求当前行程日程，先确认进行中 Trip，再按明确目标日期读取单日安排。
        if is_itinerary:
            itinerary_date = requested_range[0] if requested_range and requested_range[0] == requested_range[1] else None
            selected.extend((_current_active_trip_call(), _tool_call(
                "get_trip_itinerary_by_date",
                tripUuid=CURRENT_ACTIVE_TRIP_REFERENCE,
                date=itinerary_date.isoformat() if itinerary_date else CURRENT_DATE_REFERENCE,
            )))
        # 如果问题仅询问当前行程基础事实，避免重复加入已经作为依赖选择的工具。
        elif is_current_trip:
            selected.append(_current_active_trip_call())

        # 如果问题明确限定已结束行程，只读取历史事实，避免把未开始或进行中的 Trip 混入回答依据。
        if is_ended_trip:
            selected.append(_tool_call("get_recent_ended_trips", limit=DEFAULT_RECENT_LIMIT))
        # 如果问题涉及一般历史旅行，按 Trip 创建时间倒序读取有限摘要。
        elif is_history:
            selected.append(_tool_call("get_recent_trips", limit=DEFAULT_RECENT_LIMIT))
        # 如果问题需要个性化建议，才读取用户明确确认的偏好。
        if is_preferences:
            selected.append(_tool_call("get_user_preferences"))
        # 如果问题明确询问回忆，才读取 grounded Memory 摘要。
        if is_memory:
            selected.append(_tool_call("get_travel_memories"))

        # 如果任一请求范围仍不明确，先澄清，避免其他已选工具的部分结果被误当作完整依据。
        if clarification:
            selected.clear()

        tool_calls = tuple(_deduplicate_tool_calls(selected))
        return ToolSelectionPlan(
            intent=_intent_name(tuple(call.name for call in tool_calls)),
            tool_calls=tool_calls,
            allow_rag_search=use_rag,
            clarification=clarification,
        )


def _parse_date_range(text: str, reference_date: date) -> tuple[date, date] | None:
    """将明确的中文相对日期或年月日转换为闭区间；不能确定时返回 None。"""
    normalized = _normalize(text)
    if "上周" in normalized:
        monday = reference_date - timedelta(days=reference_date.weekday() + 7)
        return monday, monday + timedelta(days=6)

    day_offsets = (("后天", 2), ("明天", 1), ("昨天", -1), ("今天", 0))
    for term, offset in day_offsets:
        if term in normalized:
            target = reference_date + timedelta(days=offset)
            return target, target

    year_first = re.search(r"(?<!\d)(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", text)
    month_first = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})日", text)
    try:
        if year_first:
            target = date(*(int(value) for value in year_first.groups()))
            return target, target
        if month_first:
            month, day = (int(value) for value in month_first.groups())
            target = date(reference_date.year, month, day)
            return target, target
    except ValueError:
        return None
    return None


def _extract_location_query(text: str) -> str | None:
    """从常见的“在/去过某地”表述提取可用于打卡摘要过滤的地点词。"""
    match = re.search(r"(?:在|去过|去了|到过|到)\s*([A-Za-z0-9\u4e00-\u9fff·_-]+(?:\s+[A-Za-z0-9\u4e00-\u9fff·_-]+)?)", text)
    if not match:
        return None
    candidate = re.split(r"打卡|签到|哪里|哪儿|哪些|什么|哪家|哪座|旅行|旅游", match.group(1), maxsplit=1)[0].strip()
    if not candidate or candidate in {"哪里", "哪儿", "哪些", "什么"}:
        return None
    return candidate


def _current_active_trip_call() -> ToolCall:
    """返回无需参数的当前进行中 Trip 读取调用。"""
    return _tool_call("get_current_active_trip")


def _current_trip_footprint_call() -> ToolCall:
    """返回绑定前序当前 Trip 足迹的摘要调用。"""
    return _tool_call("get_footprint_summary_by_trip", tripUuid=CURRENT_ACTIVE_TRIP_REFERENCE)


def _current_trip_checkins_call() -> ToolCall:
    """返回绑定前序当前 Trip 足迹的有限打卡读取调用。"""
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
    # 如果包含最近或按 Trip 的足迹工具，归类为实时旅行问题。
    if any(name in tool_names for name in {
        "get_recent_footprint_summaries", "get_recent_checkins",
        "get_checkins_by_date_range", "get_footprints_by_date_range",
        "get_footprint_summary_by_trip", "get_checkins_by_trip",
    }):
        return "live_travel"
    # 如果包含按日期日程工具，归类为当前日程问题。
    if "get_trip_itinerary_by_date" in tool_names:
        return "current_itinerary"
    # 如果包含最近 Trip 工具，归类为旅行历史问题。
    if any(name in tool_names for name in {"get_recent_trips", "get_recent_ended_trips"}):
        return "travel_history"
    if "get_user_preferences" in tool_names:
        return "personal_preferences"
    if "get_travel_memories" in tool_names:
        return "travel_memory"
    return "current_trip"
