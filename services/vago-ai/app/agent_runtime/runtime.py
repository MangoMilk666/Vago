"""Phase 10 的最小 Think-Execute-Observe Runtime。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent_runtime.registry import AgentTool, ToolRegistry
from app.footprints import service as footprint_service
from app.memory import service as memory_service
from app.personal_context.schemas import PersonalContextPreview
from app.personal_context.service import format_context_for_agent
from app.preferences import service as preference_service
from app.travel import service as travel_service
from app.agent_runtime.selection import ToolSelectionPlan, ToolSelectionPolicy

logger = logging.getLogger(__name__)

MAX_READ_STEPS = 3


@dataclass(frozen=True)
class AgentRuntimePreparation:
    """LLM 调用前的公开执行事件与已授权上下文快照。"""

    trace_id: str
    personal_context: str | None
    context_labels: list[str]
    events: list[dict[str, str]]
    # 是否向既有 LangChain Agent 注册个人知识检索工具；默认值兼容异常降级与旧测试构造。
    allow_rag_search: bool = True


@dataclass(frozen=True)
class AgentRuntimeProgress:
    """Runtime 正在执行时可立即推送给客户端的公开事件。"""

    event: dict[str, str]


class AgentRuntime:
    """只读上下文协调器；写操作、审批与外部工具仍留待后续 Phase。"""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        selection_policy: ToolSelectionPolicy | None = None,
    ) -> None:
        self._registry = registry or ToolRegistry([
            AgentTool("get_current_trip", "正在读取当前行程", _get_current_trip),
            AgentTool("get_today_itinerary", "正在读取今日日程", _get_today_itinerary),
            AgentTool("get_recent_travel_history", "正在读取近期旅行历史", _get_recent_travel_history),
            AgentTool("get_recent_footprint", "正在查看当前行程足迹", _get_recent_footprint),
            AgentTool("get_checkins", "正在查看当前行程打卡", _get_checkins),
            AgentTool("get_user_preferences", "正在读取明确旅行偏好", _get_preferences),
            AgentTool("get_travel_memories", "正在读取旅行回忆摘要", _get_memories),
        ])
        self._selection_policy = selection_policy or ToolSelectionPolicy()

    def prepare(
        self,
        db: Session,
        user_uuid: str,
        *,
        use_personal_context: bool,
        use_rag: bool,
        prompt: str = "",
        recent_user_messages: tuple[str, ...] = (),
    ) -> AgentRuntimePreparation:
        """执行有限次只读工具调用，并将真实结果组装为本轮 Context。"""
        trace_id = uuid4().hex
        events: list[dict[str, str]] = [
            _event("agent.started", "开始整理本轮旅行上下文", trace_id=trace_id),
        ]
        state = _new_runtime_state()
        selection_plan = self._select_plan(prompt, recent_user_messages, use_personal_context, use_rag)
        tool_names = selection_plan.tool_names[:MAX_READ_STEPS]

        # 分支条件：未授权或本轮问题无需个人事实时直接进入通用建议，空工具计划是正常结果。
        if not tool_names:
            events.append(_event("agent.status", _no_tool_status(use_personal_context, use_rag), trace_id=trace_id))
            return AgentRuntimePreparation(trace_id, None, [], events, selection_plan.allow_rag_search)

        events.append(_event("agent.status", "正在读取与本轮问题相关的旅行信息", trace_id=trace_id))

        for tool_name in tool_names:
            # 如果前序 Observation 未确认进行中 Trip，跳过依赖 Trip 的工具，避免无关查询。
            if _requires_current_trip(tool_name) and _active_trip_uuid(state) is None:
                events.append(_event(
                    "agent.status", _dependency_unavailable_status(tool_name), trace_id=trace_id,
                ))
                continue
            tool = self._registry.get(tool_name)
            events.append(_event("tool.started", tool.label, tool=tool.name, trace_id=trace_id))

            # 尝试调用tool，把调用后的output存入上下文runtime state
            try:
                output = tool.handler(db, user_uuid, state)
                _store_tool_output(state, tool.name, output)
                events.append(_event(
                    "tool.completed", _summary_for_tool(tool.name, output), tool=tool.name, trace_id=trace_id,
                ))
            except Exception as exc:
                # 分支条件：tool调用失败 / 单一数据源不可用时记录失败 Observation，并继续读取其他可用领域。
                logger.warning("[agent_runtime] tool failed trace=%s tool=%s error=%s", trace_id, tool.name, exc)
                events.append(_event(
                    "tool.failed", f"{tool.label.replace('正在', '')}暂时不可用，已继续处理", tool=tool.name, trace_id=trace_id,
                ))
        # 如果候选读取超过本轮上限，明确告知仅基于已读取 Observation 作答。
        if len(selection_plan.tool_names) > MAX_READ_STEPS:
            events.append(_event("agent.status", "候选资料超过本轮读取上限，已基于已读取事实生成建议", trace_id=trace_id))

        # state对象已经存储了tool calling 的调用结果
        # 把state再组装为一个统一的context对象
        context = _to_context_preview(state)
        events.append(_event("agent.status", "已完成上下文整理，正在生成旅行建议", trace_id=trace_id))
        # 最终组装为一个 记录了agent event的 快照对象
        return AgentRuntimePreparation(
            trace_id=trace_id,
            personal_context=format_context_for_agent(context),
            context_labels=context.labels,
            events=events,
            allow_rag_search=selection_plan.allow_rag_search,
        )

    async def stream_prepare(
        self,
        db: Session,
        user_uuid: str,
        *,
        use_personal_context: bool,
        use_rag: bool,
        prompt: str = "",
        recent_user_messages: tuple[str, ...] = (),
    ) -> AsyncIterator[AgentRuntimeProgress | AgentRuntimePreparation]:
        """边执行边发送 Runtime 事件，避免快速读取在客户端被压缩为同一帧。"""
        trace_id = uuid4().hex
        state = _new_runtime_state()
        selection_plan = self._select_plan(prompt, recent_user_messages, use_personal_context, use_rag)
        tool_names = selection_plan.tool_names[:MAX_READ_STEPS]
        yield AgentRuntimeProgress(_event("agent.started", "开始整理本轮旅行上下文", trace_id=trace_id))

        # 分支条件：未授权或本轮问题无需个人事实时，直接进入通用 LLM 对话，不读取领域事实。
        if not tool_names:
            yield AgentRuntimeProgress(_event("agent.status", _no_tool_status(use_personal_context, use_rag), trace_id=trace_id))
            yield AgentRuntimePreparation(trace_id, None, [], [], selection_plan.allow_rag_search)
            return

        yield AgentRuntimeProgress(_event("agent.status", "正在读取与本轮问题相关的旅行信息", trace_id=trace_id))
        events: list[dict[str, str]] = []
        for tool_name in tool_names:
            # 如果前序 Observation 未确认进行中 Trip，直接说明依赖未满足，不发送伪造的工具调用事件。
            if _requires_current_trip(tool_name) and _active_trip_uuid(state) is None:
                yield AgentRuntimeProgress(_event(
                    "agent.status", _dependency_unavailable_status(tool_name), trace_id=trace_id,
                ))
                continue
            tool = self._registry.get(tool_name)
            started_event = _event("tool.started", tool.label, tool=tool.name, trace_id=trace_id)
            events.append(started_event)
            yield AgentRuntimeProgress(started_event)
            # 主动让出事件循环，使 ASGI 有机会将“开始调用”刷新到客户端后再做下一步读取。
            await _yield_to_event_loop()
            # 尝试调用tool，把输出结果存入state
            try:
                output = tool.handler(db, user_uuid, state)
                _store_tool_output(state, tool.name, output)
                completed_event = _event(
                    "tool.completed", _summary_for_tool(tool.name, output), tool=tool.name, trace_id=trace_id,
                )
                events.append(completed_event)
                yield AgentRuntimeProgress(completed_event)
            except Exception as exc:
                # 分支条件：tool调用失败 / 单一数据源不可用时，发送失败 Observation 并继续读取其他可用领域。
                logger.warning("[agent_runtime] tool failed trace=%s tool=%s error=%s", trace_id, tool.name, exc)
                failed_event = _event(
                    "tool.failed", f"{tool.label.replace('正在', '')}暂时不可用，已继续处理", tool=tool.name, trace_id=trace_id,
                )
                events.append(failed_event)
                yield AgentRuntimeProgress(failed_event)
            await _yield_to_event_loop()
        # 如果候选读取超过本轮上限，流式事件同样公开信息边界。
        if len(selection_plan.tool_names) > MAX_READ_STEPS:
            limit_event = _event("agent.status", "候选资料超过本轮读取上限，已基于已读取事实生成建议", trace_id=trace_id)
            events.append(limit_event)
            yield AgentRuntimeProgress(limit_event)

        # state已经存储了tools调用的输出结果
        # 再把state对象封装为统一的context对象
        context = _to_context_preview(state)
        ready_event = _event("agent.status", "已完成上下文整理，正在生成旅行建议", trace_id=trace_id)
        events.append(ready_event)
        yield AgentRuntimeProgress(ready_event)
        yield AgentRuntimePreparation(
            trace_id=trace_id,
            personal_context=format_context_for_agent(context),
            context_labels=context.labels,
            events=events,
            allow_rag_search=selection_plan.allow_rag_search,
        )

    def _select_plan(
        self,
        prompt: str,
        recent_user_messages: tuple[str, ...],
        use_personal_context: bool,
        use_rag: bool,
    ) -> ToolSelectionPlan:
        """授权决定可读取范围，确定性 Policy 决定本轮是否真的需要读取领域事实。"""
        # use_rag 仅决定既有 LangChain RAG 工具是否可注册；不在 Runtime 固定读取知识库摘要。
        plan = self._selection_policy.select(
            prompt,
            recent_user_messages=recent_user_messages,
            use_personal_context=use_personal_context,
            use_rag=use_rag,
        )
        return ToolSelectionPlan(
            intent=plan.intent,
            tool_names=plan.tool_names,
            allow_rag_search=plan.allow_rag_search,
        )


def _no_tool_status(use_personal_context: bool, use_rag: bool) -> str:
    """区分用户未授权与问题无需读取，避免客户端把正常零工具误解为故障。"""
    if not use_personal_context and not use_rag:
        return "本轮未启用个人旅行上下文"
    return "本轮问题无需读取个人旅行资料，正在生成建议"


def _new_runtime_state() -> dict[str, Any]:
    """初始化只保存本轮 Observation 的 Runtime State，不建立新的长期存储。"""
    return {
        "travelContext": {"currentTrip": None, "travelHistory": []},
        "todayItinerary": None,
        "liveObservations": {},
        "preferences": {},
        "memories": [],
        "knowledgeSummary": {},
    }


def _get_current_trip(db: Session, user_uuid: str, _: dict[str, Any]) -> dict[str, Any] | None:
    """通过 Travel Domain Service 仅读取进行中 Trip 的基础事实。"""
    return travel_service.get_agent_current_trip(db, user_uuid)


def _get_today_itinerary(db: Session, user_uuid: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """使用前序当前行程 Observation 查询今日日程。"""
    trip_uuid = _active_trip_uuid(state)
    return travel_service.get_agent_today_itinerary(db, user_uuid, trip_uuid) if trip_uuid else None


def _get_recent_travel_history(db: Session, user_uuid: str, _: dict[str, Any]) -> list[dict[str, Any]]:
    """读取有限的历史 Trip 基础摘要。"""
    return travel_service.get_agent_recent_travel_history(db, user_uuid)


def _get_recent_footprint(db: Session, user_uuid: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """仅在存在进行中行程时读取自动 GPS 摘要。"""
    trip_uuid = _active_trip_uuid(state)
    return footprint_service.get_agent_footprint_context(db, user_uuid, trip_uuid) if trip_uuid else None


def _get_checkins(db: Session, user_uuid: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """仅在存在进行中行程时读取手动打卡摘要。"""
    trip_uuid = _active_trip_uuid(state)
    return footprint_service.get_agent_checkin_context(db, user_uuid, trip_uuid) if trip_uuid else None


def _get_preferences(db: Session, user_uuid: str, _: dict[str, Any]) -> dict[str, Any]:
    """读取用户明确确认的偏好，不读取模型推断的信号。"""
    return preference_service.get_agent_preference_context(db, user_uuid)


def _get_memories(db: Session, user_uuid: str, _: dict[str, Any]) -> list[dict[str, Any]]:
    """读取 grounded Travel Memory 摘要。"""
    return memory_service.get_agent_memory_context(db, user_uuid)


def _store_tool_output(state: dict[str, Any], tool_name: str, output: Any) -> None:
    """将工具 Observation 放入 Runtime State，供后续工具和 Prompt 使用。"""
    # 如果读取当前行程，只更新该 Observation，不顺带覆盖已经读取的历史摘要。
    if tool_name == "get_current_trip":
        state["travelContext"]["currentTrip"] = output
    # 如果读取历史行程，只更新历史 Observation，不污染当前行程事实。
    elif tool_name == "get_recent_travel_history":
        state["travelContext"]["travelHistory"] = output or []
    # 如果读取今日日程，将它独立保存，避免把日程伪装为 Trip 的静态字段。
    elif tool_name == "get_today_itinerary":
        state["todayItinerary"] = output
    # 如果读取 GPS 或打卡摘要，合并为同一份 Live Context，但保留各自的数据边界。
    elif tool_name in {"get_recent_footprint", "get_checkins"}:
        state["liveObservations"].update(output or {})
    # 如果读取明确偏好，以本次 Observation 覆盖此前的空占位值。
    elif tool_name == "get_user_preferences":
        state["preferences"] = output or {}
    # 如果读取 Grounded Memory，保留有限摘要而非完整叙事。
    elif tool_name == "get_travel_memories":
        state["memories"] = output or []


def _active_trip_uuid(state: dict[str, Any]) -> str | None:
    """从当前行程 Observation 中提取后续工具允许使用的 Trip UUID。"""
    current_trip = state["travelContext"].get("currentTrip")
    return current_trip.get("uuid") if current_trip else None


def _requires_current_trip(tool_name: str) -> bool:
    """判断一个tool是否需要需要存在【一个正在进行的trip】"""
    return tool_name in {"get_today_itinerary", "get_recent_footprint", "get_checkins"}


def _dependency_unavailable_status(tool_name: str) -> str:
    """生成不泄露内部状态的依赖未满足提示。"""
    labels = {
        "get_today_itinerary": "当前没有进行中的行程，跳过今日日程读取",
        "get_recent_footprint": "当前没有进行中的行程，跳过足迹读取",
        "get_checkins": "当前没有进行中的行程，跳过打卡读取",
    }
    return labels[tool_name]


def _to_context_preview(state: dict[str, Any]) -> PersonalContextPreview:
    """把已观察的领域结果转换为统一 Context对象，不引入新的数据存储。"""
    travel_context = state["travelContext"] or {"currentTrip": None, "travelHistory": []}
    current_trip = travel_context.get("currentTrip")
    today_itinerary = state["todayItinerary"]
    travel_history = travel_context.get("travelHistory", [])
    preferences = state["preferences"] or {}
    memories = state["memories"] or []
    knowledge_summary = state["knowledgeSummary"] or {}
    live_observations = state["liveObservations"] or None
    labels: list[str] = []
    # 如果本轮实际读取到进行中 Trip，才向客户端标注当前行程上下文。
    if current_trip:
        labels.append("当前行程")
    # 如果本轮实际读取过今日日程，即使为空也保留其上下文来源标识。
    if today_itinerary:
        labels.append("今日日程")
    # 如果本轮实际读取到已结束 Trip，才标注旅行历史。
    if travel_history:
        labels.append("近期旅行历史")
    # 如果 GPS 或打卡摘要包含真实观察，才标注近期旅行观察。
    if live_observations and (
        live_observations.get("automaticSampleCount", 0) or live_observations.get("recentCheckins")
    ):
        labels.append("近期旅行观察")
    # 如果用户已明确保存偏好，才将其作为本轮上下文来源。
    if preferences.get("hasExplicitPreference"):
        labels.append("明确旅行偏好")
    # 如果存在 grounded Memory 摘要，才将其标注为本轮上下文来源。
    if memories:
        labels.append("Grounded Travel Memory")
    # 如果本轮确实拥有知识资料摘要，才标注个人知识来源。
    if knowledge_summary.get("sourceCount", 0):
        labels.append("个人知识资料摘要")
    return PersonalContextPreview(
        labels=labels,
        currentTrip=current_trip,
        todayItinerary=today_itinerary,
        travelHistory=travel_history,
        liveObservations=live_observations,
        preferences=preferences,
        memories=memories,
        knowledgeSummary=knowledge_summary,
    )


def _summary_for_tool(tool_name: str, output: Any) -> str:
    """生成不含 GPS 原始坐标与内部数据结构的简短执行结果。"""
    if tool_name == "get_current_trip":
        return "已读取当前进行中的行程" if output else "当前没有进行中的行程"
    if tool_name == "get_today_itinerary":
        return "已读取今日日程" if output and output.get("dayIndex") else "当前行程今天没有日程安排"
    if tool_name == "get_recent_travel_history":
        return "已读取近期旅行历史" if output else "暂无已结束的旅行历史"
    if tool_name == "get_recent_footprint":
        return "已读取当前行程足迹摘要" if output and output.get("automaticSampleCount") else "当前行程暂无 GPS 足迹"
    if tool_name == "get_checkins":
        return "已读取当前行程打卡" if output and output.get("recentCheckins") else "当前行程暂无手动打卡"
    if tool_name == "get_user_preferences":
        return "已读取明确旅行偏好" if output and output.get("hasExplicitPreference") else "尚未设置明确旅行偏好"
    if tool_name == "get_travel_memories":
        return "已读取旅行回忆摘要" if output else "暂无已生成的旅行回忆"
    return "已完成读取"


def _event(event_type: str, label: str, **extra: str) -> dict[str, str]:
    """统一构造可安全展示的执行事件，不包含模型推理或原始事实。"""
    return {"type": event_type, "label": label, **extra}


async def _yield_to_event_loop() -> None:
    """不添加人为等待，只让 StreamingResponse 有机会及时写出当前 SSE 事件。"""
    import asyncio

    await asyncio.sleep(0)
