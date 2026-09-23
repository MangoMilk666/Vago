"""Phase 10.1 的确定性工具选择策略。
ToolSelectionPolicy：授权仅定义可读取范围；普通问题会返回零工具计划"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


MAX_INITIAL_READ_TOOLS = 3


@dataclass(frozen=True)
class ToolSelectionPlan:
    """本轮允许实际执行的只读领域工具计划；空工具列表是正常结果。"""

    intent: str
    tool_names: tuple[str, ...]


class ToolSelectionPolicy:
    """根据关键词匹配用户目标，选择必要领域工具，不为路由本身额外消耗一次 LLM 调用。"""

    _CURRENT_TRIP_TERMS = (
        "当前行程", "我的行程", "本次行程", "这次行程", "今天的行程", "今天行程",
        "我的日程", "今日日程", "今天安排", "今天有什么安排", "接下来", "还剩",
        "剩余", "行程里", "日程里",
    )
    _LIVE_TRAVEL_TERMS = (
        "足迹", "打卡", "我在哪", "当前位置", "现在在哪", "轨迹", "记录点",
        "走过", "去了哪里",
    )
    _PREFERENCE_TERMS = (
        "旅行偏好", "我的偏好", "旅行习惯", "我的习惯", "旅行风格", "我的风格",
        "我的节奏", "根据我的", "适合我",
    )
    _HISTORY_TERMS = (
        "旅行历史", "历史行程", "上次旅行", "之前旅行", "过去旅行", "以前旅行",
        "我去过", "我曾去过",
    )
    _MEMORY_TERMS = ("旅行回忆", "旅行记忆", "回忆", "纪念")
    _FOLLOW_UP_TERMS = ("那明天", "那今天", "还有呢", "然后呢", "继续", "刚才", "这个", "那个")

    def select(
        self,
        prompt: str,
        *,
        recent_user_messages: Sequence[str] = (),
        use_personal_context: bool,
    ) -> ToolSelectionPlan:
        """从当前 prompt 选择工具；只有明显的追问才借用有限的历史用户问题。"""
        if not use_personal_context:
            return ToolSelectionPlan(intent="general", tool_names=())

        normalized_prompt = _normalize(prompt)
        routed_text = normalized_prompt
        # 分支条件：短追问通常省略“当前行程”等主语，才使用有限历史恢复其指代，普通问题不扩大读取范围。
        if _contains_any(normalized_prompt, self._FOLLOW_UP_TERMS):
            # 最近三条用户的消息文本
            recent_context = " ".join(_normalize(message) for message in recent_user_messages[-3:])
            # 最近三条，连同当前的最新prompt
            routed_text = f"{recent_context} {normalized_prompt}".strip()

        # 判断是否和对应话题有关
        is_live_travel = _contains_any(routed_text, self._LIVE_TRAVEL_TERMS)
        is_current_trip = _contains_any(routed_text, self._CURRENT_TRIP_TERMS)
        is_preferences = _contains_any(routed_text, self._PREFERENCE_TERMS)
        is_history = _contains_any(routed_text, self._HISTORY_TERMS)
        is_memory = _contains_any(routed_text, self._MEMORY_TERMS)

        selected: list[str] = []
        # 足迹必须绑定具体 Trip，先读取当前行程只是满足工具依赖，不代表固定预取旅行历史。
        if is_live_travel:
            selected.extend(("get_current_trip", "get_recent_footprint"))
        elif is_current_trip or is_history:
            selected.append("get_current_trip")

        if is_preferences:
            selected.append("get_user_preferences")
        if is_memory:
            selected.append("get_travel_memories")

        # 保持固定、可测试的执行顺序，重复命中多个意图时不重复调用同一工具。
        tool_names = tuple(dict.fromkeys(selected))[:MAX_INITIAL_READ_TOOLS]
        return ToolSelectionPlan(intent=_intent_name(tool_names), tool_names=tool_names)


def _normalize(text: str) -> str:
    """归一化空白与大小写，避免展示层输入格式影响中文意图规则。"""
    return "".join(text.lower().split())


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    '''
    判断text文本中是否匹配任一预设的关键词
    '''
    return any(term in text for term in terms)


def _intent_name(tool_names: tuple[str, ...]) -> str:
    """为日志与未来评估提供稳定意图名，不向客户端暴露模型推理。"""
    if not tool_names:
        return "general"
    if "get_recent_footprint" in tool_names:
        return "live_travel"
    if "get_user_preferences" in tool_names:
        return "personal_preferences"
    if "get_travel_memories" in tool_names:
        return "travel_memory"
    return "current_or_history_trip"
