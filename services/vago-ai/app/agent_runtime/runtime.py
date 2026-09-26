"""Phase 10.2.1 的只读 Think-Execute-Observe Runtime。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent_runtime.registry import AgentTool, ToolRegistry
from app.agent_runtime.selection import (
    CURRENT_ACTIVE_TRIP_REFERENCE,
    CURRENT_DATE_REFERENCE,
    ToolCall,
    ToolSelectionPlan,
    ToolSelectionPolicy,
)
from app.footprints import service as footprint_service
from app.memory import service as memory_service
from app.personal_context.schemas import PersonalContextPreview
from app.personal_context.service import format_context_for_agent
from app.preferences import service as preference_service
from app.travel import service as travel_service

logger = logging.getLogger(__name__)

# 普通问题的首次读取预算；后续读取必须由已获得的 Observation 或确定性计划证明必要性。
INITIAL_READ_BUDGET = 3
# 单轮总读取预算，防止复杂问题把 Personal Context 扩大为无界事实抓取。
MAX_TOTAL_READ_STEPS = 6


@dataclass(frozen=True)
class AgentRuntimePreparation:
    """LLM 调用前的公开执行事件与本轮已授权上下文快照。"""

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
            AgentTool("get_current_active_trip", "正在读取当前进行中的行程", _get_current_active_trip),
            AgentTool("get_trip_itinerary_by_date", "正在读取指定日期日程", _get_trip_itinerary_by_date),
            AgentTool("get_recent_trips", "正在读取最近行程", _get_recent_trips),
            AgentTool("get_footprint_summary_by_trip", "正在读取指定行程足迹", _get_footprint_summary_by_trip),
            AgentTool("get_checkins_by_trip", "正在读取指定行程打卡", _get_checkins_by_trip),
            AgentTool("get_recent_footprint_summaries", "正在读取最近足迹行程", _get_recent_footprint_summaries),
            AgentTool("get_recent_checkins", "正在读取最近打卡", _get_recent_checkins),
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
        """执行有界的只读 Observation 链，并组装本轮 Prompt Context。"""
        trace_id = uuid4().hex
        events: list[dict[str, str]] = [_event("agent.started", "开始整理本轮旅行上下文", trace_id=trace_id)]
        state = _new_runtime_state()
        selection_plan = self._select_plan(prompt, recent_user_messages, use_personal_context, use_rag)

        # 如果未授权或本轮问题无需个人事实，直接进入通用建议，空工具计划是正常结果。
        if not selection_plan.tool_calls:
            events.append(_event("agent.status", _no_tool_status(use_personal_context, use_rag), trace_id=trace_id))
            return AgentRuntimePreparation(trace_id, None, [], events, selection_plan.allow_rag_search)

        events.append(_event("agent.status", "正在读取与本轮问题相关的旅行信息", trace_id=trace_id))
        read_count = 0
        continuation_announced = False
        pending_calls = list(selection_plan.tool_calls)

        while pending_calls and read_count < MAX_TOTAL_READ_STEPS:
            tool_call = pending_calls.pop(0)
            # 如果已经用完初始预算，后续调用必须是确定性计划选中的必要读取，并向客户端公开续读状态。
            if read_count >= INITIAL_READ_BUDGET and not continuation_announced:
                continuation_announced = True
                events.append(_event(
                    "agent.status", "已完成初始资料读取，正在根据已获得的信息补充必要事实",
                    trace_id=trace_id,
                ))

            tool_events, executed = self._execute_tool_call(db, user_uuid, state, tool_call, trace_id)
            events.extend(tool_events)
            if executed:
                read_count += 1

        # 如果候选工具超过总读取预算，明确说明本轮信息边界，而不是静默遗漏。
        if pending_calls:
            events.append(_event(
                "agent.status", "已达到本轮读取总预算，将基于已获得的事实提供保守建议",
                trace_id=trace_id,
            ))

        return _build_preparation(trace_id, state, events, selection_plan.allow_rag_search)

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
        """边执行边发送 Runtime 事件，避免工具轨迹在客户端被压缩为同一帧。"""
        trace_id = uuid4().hex
        state = _new_runtime_state()
        selection_plan = self._select_plan(prompt, recent_user_messages, use_personal_context, use_rag)
        yield AgentRuntimeProgress(_event("agent.started", "开始整理本轮旅行上下文", trace_id=trace_id))

        # 如果未授权或本轮问题无需个人事实，直接进入通用 LLM 对话，不读取领域事实。
        if not selection_plan.tool_calls:
            yield AgentRuntimeProgress(_event("agent.status", _no_tool_status(use_personal_context, use_rag), trace_id=trace_id))
            yield AgentRuntimePreparation(trace_id, None, [], [], selection_plan.allow_rag_search)
            return

        yield AgentRuntimeProgress(_event("agent.status", "正在读取与本轮问题相关的旅行信息", trace_id=trace_id))
        events: list[dict[str, str]] = []
        read_count = 0
        continuation_announced = False
        pending_calls = list(selection_plan.tool_calls)

        while pending_calls and read_count < MAX_TOTAL_READ_STEPS:
            tool_call = pending_calls.pop(0)
            # 如果已经用完初始预算，先让客户端获知此后的调用是基于前序 Observation 的受控续读。
            if read_count >= INITIAL_READ_BUDGET and not continuation_announced:
                continuation_announced = True
                continuation_event = _event(
                    "agent.status", "已完成初始资料读取，正在根据已获得的信息补充必要事实",
                    trace_id=trace_id,
                )
                events.append(continuation_event)
                yield AgentRuntimeProgress(continuation_event)

            # 如果前序 Observation 未确认当前进行中 Trip，跳过依赖该 Trip 的tools调用，不伪造工具执行事件。
            if _requires_current_active_trip(tool_call) and _active_trip_uuid(state) is None:
                skipped_event = _event(
                    "agent.status", _dependency_unavailable_status(tool_call.name), trace_id=trace_id,
                )
                events.append(skipped_event)
                yield AgentRuntimeProgress(skipped_event)
                continue

            tool = self._registry.get(tool_call.name)
            started_event = _event("tool.started", tool.label, tool=tool.name, trace_id=trace_id)
            events.append(started_event)
            yield AgentRuntimeProgress(started_event)
            await _yield_to_event_loop()
            try:
                arguments = _resolve_tool_arguments(tool_call, state)
                output = tool.handler(db, user_uuid, state, arguments)
                _store_tool_output(state, tool.name, output)
                completed_event = _event(
                    "tool.completed", _summary_for_tool(tool.name, output), tool=tool.name, trace_id=trace_id,
                )
                events.append(completed_event)
                yield AgentRuntimeProgress(completed_event)
            except Exception as exc:
                # 如果单一领域工具失败，把失败作为公开 Observation，继续处理其他已授权工具。
                logger.warning("[agent_runtime] tool failed trace=%s tool=%s error=%s", trace_id, tool.name, exc)
                failed_event = _event(
                    "tool.failed", f"{tool.label.replace('正在', '')}暂时不可用，已继续处理", tool=tool.name, trace_id=trace_id,
                )
                events.append(failed_event)
                yield AgentRuntimeProgress(failed_event)
            read_count += 1
            await _yield_to_event_loop()

        # 如果候选工具超过总读取预算，流式事件同样公开信息边界。
        if pending_calls:
            budget_event = _event(
                "agent.status", "已达到本轮读取总预算，将基于已获得的事实提供保守建议",
                trace_id=trace_id,
            )
            events.append(budget_event)
            yield AgentRuntimeProgress(budget_event)

        preparation = _build_preparation(trace_id, state, events, selection_plan.allow_rag_search)
        yield AgentRuntimeProgress(preparation.events[-1])
        yield preparation

    def _execute_tool_call(
        self,
        db: Session,
        user_uuid: str,
        state: dict[str, Any],
        tool_call: ToolCall,
        trace_id: str,
    ) -> tuple[list[dict[str, str]], bool]:
        """执行一个同步 ToolCall；返回公开事件与是否实际占用读取预算。"""
        # 如果前序 Observation 未确认当前进行中 Trip，跳过依赖该 Trip 的调用。
        if _requires_current_active_trip(tool_call) and _active_trip_uuid(state) is None:
            return [_event("agent.status", _dependency_unavailable_status(tool_call.name), trace_id=trace_id)], False

        tool = self._registry.get(tool_call.name)
        events = [_event("tool.started", tool.label, tool=tool.name, trace_id=trace_id)]
        try:
            arguments = _resolve_tool_arguments(tool_call, state)
            output = tool.handler(db, user_uuid, state, arguments)
            _store_tool_output(state, tool.name, output)
            events.append(_event(
                "tool.completed", _summary_for_tool(tool.name, output), tool=tool.name, trace_id=trace_id,
            ))
        except Exception as exc:
            # 如果单一领域工具失败，失败 Observation 不阻断其他候选工具。
            logger.warning("[agent_runtime] tool failed trace=%s tool=%s error=%s", trace_id, tool.name, exc)
            events.append(_event(
                "tool.failed", f"{tool.label.replace('正在', '')}暂时不可用，已继续处理", tool=tool.name, trace_id=trace_id,
            ))
        return events, True

    def _select_plan(
        self,
        prompt: str,
        recent_user_messages: tuple[str, ...],
        use_personal_context: bool,
        use_rag: bool,
    ) -> ToolSelectionPlan:
        """授权决定可读取范围，确定性 Policy 决定候选 ToolCall。"""
        return self._selection_policy.select(
            prompt,
            recent_user_messages=recent_user_messages,
            use_personal_context=use_personal_context,
            use_rag=use_rag,
        )


def _no_tool_status(use_personal_context: bool, use_rag: bool) -> str:
    """区分用户未授权与问题无需读取，避免客户端把正常零工具误解为故障。"""
    # 如果旅行和个人资料授权均关闭，明确告知本轮没有可读取上下文。
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


def _get_current_active_trip(db: Session, user_uuid: str, _: dict[str, Any], __: dict[str, Any]) -> dict[str, Any] | None:
    """读取当前唯一进行中 Trip 的基础事实。"""
    return travel_service.get_agent_current_active_trip(db, user_uuid)


def _get_trip_itinerary_by_date(
    db: Session,
    user_uuid: str,
    _: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    """按明确 Trip UUID 与日期读取单日 itinerary。"""
    return travel_service.get_agent_trip_itinerary_by_date(
        db,
        user_uuid,
        str(arguments["tripUuid"]),
        date.fromisoformat(str(arguments["date"])),
    )


def _get_recent_trips(db: Session, user_uuid: str, _: dict[str, Any], arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """按服务端定义的创建时间倒序读取有限 Trip 摘要。"""
    return travel_service.get_agent_recent_trips(db, user_uuid, _read_limit(arguments))


def _get_footprint_summary_by_trip(
    db: Session,
    user_uuid: str,
    _: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """按明确 Trip UUID 读取自动 GPS 聚合摘要。"""
    return footprint_service.get_agent_footprint_summary_by_trip(db, user_uuid, str(arguments["tripUuid"]))


def _get_checkins_by_trip(
    db: Session,
    user_uuid: str,
    _: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """按明确 Trip UUID 读取有限手动打卡摘要。"""
    return footprint_service.get_agent_checkins_by_trip(
        db,
        user_uuid,
        str(arguments["tripUuid"]),
        _read_limit(arguments),
    )


def _get_recent_footprint_summaries(
    db: Session,
    user_uuid: str,
    _: dict[str, Any],
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    """按 Observation 时间倒序读取最近有足迹的 Trip 摘要。"""
    return footprint_service.get_agent_recent_footprint_summaries(db, user_uuid, _read_limit(arguments))


def _get_recent_checkins(
    db: Session,
    user_uuid: str,
    _: dict[str, Any],
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    """按 Observation 时间倒序读取最近的有限手动打卡。"""
    return footprint_service.get_agent_recent_checkins(db, user_uuid, _read_limit(arguments))


def _get_preferences(db: Session, user_uuid: str, _: dict[str, Any], __: dict[str, Any]) -> dict[str, Any]:
    """读取用户明确确认的偏好，不读取模型推断的信号。"""
    return preference_service.get_agent_preference_context(db, user_uuid)


def _get_memories(db: Session, user_uuid: str, _: dict[str, Any], __: dict[str, Any]) -> list[dict[str, Any]]:
    """读取 grounded Travel Memory 摘要。"""
    return memory_service.get_agent_memory_context(db, user_uuid)


def _read_limit(arguments: dict[str, Any], default: int = 3) -> int:
    """解析工具参数中的 limit；Domain Service 仍承担最终上限校验。"""
    value = arguments.get("limit", default)
    # 如果参数不是整数，回退到小的默认读取范围，避免异常扩大查询。
    return value if isinstance(value, int) else default


def _resolve_tool_arguments(tool_call: ToolCall, state: dict[str, Any]) -> dict[str, Any]:
    """把 Plan 中的安全引用解析为本轮 Observation 与当前日期的实际参数。"""
    arguments = dict(tool_call.arguments)
    # 如果工具参数引用当前进行中 Trip，用前序 Observation 的 UUID 替换该引用。
    if arguments.get("tripUuid") == CURRENT_ACTIVE_TRIP_REFERENCE:
        arguments["tripUuid"] = _active_trip_uuid(state)
    # 如果工具参数引用当前日期，在 Runtime 内生成日期，避免客户端传入隐式日期范围。
    if arguments.get("date") == CURRENT_DATE_REFERENCE:
        arguments["date"] = date.today().isoformat()
    return arguments


def _store_tool_output(state: dict[str, Any], tool_name: str, output: Any) -> None:
    """将工具 Observation 放入 Runtime State，供后续工具和 Prompt 使用。"""
    # 如果读取当前行程，只更新当前 Trip Observation，不覆盖近期 Trip 摘要。
    if tool_name == "get_current_active_trip":
        state["travelContext"]["currentTrip"] = output
    # 如果读取最近 Trip，只更新最近 Trip Observation，不污染当前行程事实。
    elif tool_name == "get_recent_trips":
        state["travelContext"]["travelHistory"] = output or []
    # 如果读取指定日期日程，将它独立保存，避免把日程伪装为 Trip 静态字段。
    elif tool_name == "get_trip_itinerary_by_date":
        state["todayItinerary"] = output
    # 如果读取当前 Trip 的 GPS 或打卡摘要，按明确字段保存。
    elif tool_name == "get_footprint_summary_by_trip":
        state["liveObservations"]["currentTripFootprint"] = output or {}
    elif tool_name == "get_checkins_by_trip":
        state["liveObservations"]["currentTripCheckins"] = (output or {}).get("recentCheckins", [])
    # 如果读取最近空间事实，保留它们与当前行程空间事实的来源边界。
    elif tool_name == "get_recent_footprint_summaries":
        state["liveObservations"]["recentFootprintSummaries"] = output or []
    elif tool_name == "get_recent_checkins":
        state["liveObservations"]["recentCheckins"] = output or []
    elif tool_name == "get_user_preferences":
        state["preferences"] = output or {}
    elif tool_name == "get_travel_memories":
        state["memories"] = output or []


def _active_trip_uuid(state: dict[str, Any]) -> str | None:
    """从当前行程 Observation 中提取后续按 Trip 工具可使用的 UUID。"""
    current_trip = state["travelContext"].get("currentTrip")
    return current_trip.get("uuid") if current_trip else None


def _requires_current_active_trip(tool_call: ToolCall) -> bool:
    """判断一个 ToolCall 是否引用前序当前进行中 Trip Observation。"""
    return tool_call.arguments.get("tripUuid") == CURRENT_ACTIVE_TRIP_REFERENCE


def _dependency_unavailable_status(tool_name: str) -> str:
    """生成不泄露内部状态的依赖未满足提示。"""
    labels = {
        "get_trip_itinerary_by_date": "当前没有进行中的行程，跳过指定日期日程读取",
        "get_footprint_summary_by_trip": "当前没有进行中的行程，跳过当前行程足迹读取",
        "get_checkins_by_trip": "当前没有进行中的行程，跳过当前行程打卡读取",
    }
    return labels[tool_name]


def _build_preparation(
    trace_id: str,
    state: dict[str, Any],
    events: list[dict[str, str]],
    allow_rag_search: bool,
) -> AgentRuntimePreparation:
    """将本轮 Observation 转为 Prompt Context 与最终准备事件。"""
    context = _to_context_preview(state)
    events.append(_event("agent.status", "已完成上下文整理，正在生成旅行建议", trace_id=trace_id))
    return AgentRuntimePreparation(
        trace_id=trace_id,
        personal_context=format_context_for_agent(context),
        context_labels=context.labels,
        events=events,
        allow_rag_search=allow_rag_search,
    )


def _to_context_preview(state: dict[str, Any]) -> PersonalContextPreview:
    """把已观察的领域结果转换为统一 Context 对象，不引入新的数据存储。"""
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
    # 如果本轮实际读取过指定日期日程，即使该日没有安排也保留上下文来源标识。
    if today_itinerary:
        labels.append("指定日期日程")
    # 如果本轮实际读取到最近 Trip，才标注旅行历史。
    if travel_history:
        labels.append("最近旅行记录")
    # 如果本轮读取到真实 GPS 或打卡观察，才标注近期旅行观察。
    if _has_live_observations(live_observations):
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


def _has_live_observations(live_observations: dict[str, Any] | None) -> bool:
    """判断 Live Context 是否包含至少一项真实空间观察，而不是空摘要占位。"""
    if not live_observations:
        return False
    footprint = live_observations.get("currentTripFootprint", {})
    return bool(
        footprint.get("automaticSampleCount", 0)
        or live_observations.get("currentTripCheckins")
        or live_observations.get("recentFootprintSummaries")
        or live_observations.get("recentCheckins")
    )


def _summary_for_tool(tool_name: str, output: Any) -> str:
    """生成不含 GPS 原始坐标与内部数据结构的简短执行结果。"""
    # 如果读取的是当前进行中 Trip，根据是否存在结果说明当前行程状态。
    if tool_name == "get_current_active_trip":
        return "已读取当前进行中的行程" if output else "当前没有进行中的行程"
    # 如果读取的是指定日期日程，根据 dayIndex 区分有日程与空安排。
    if tool_name == "get_trip_itinerary_by_date":
        return "已读取指定日期日程" if output and output.get("dayIndex") else "指定日期没有日程安排"
    # 如果读取的是最近 Trip，根据结果列表说明是否存在旅行记录。
    if tool_name == "get_recent_trips":
        return "已读取最近旅行记录" if output else "暂无旅行记录"
    # 如果读取的是指定 Trip 的足迹，根据自动采样数量说明是否存在 GPS 事实。
    if tool_name == "get_footprint_summary_by_trip":
        return "已读取指定行程足迹摘要" if output and output.get("automaticSampleCount") else "指定行程暂无 GPS 足迹"
    # 如果读取的是指定 Trip 的打卡，根据有限打卡列表说明是否存在用户主动记录。
    if tool_name == "get_checkins_by_trip":
        return "已读取指定行程打卡" if output and output.get("recentCheckins") else "指定行程暂无手动打卡"
    # 如果读取的是最近足迹 Trip，根据摘要列表说明是否存在空间观察。
    if tool_name == "get_recent_footprint_summaries":
        return "已读取最近足迹行程" if output else "暂无足迹记录"
    # 如果读取的是最近手动打卡，根据结果列表说明是否存在主动记录。
    if tool_name == "get_recent_checkins":
        return "已读取最近打卡" if output else "暂无手动打卡"
    # 如果读取的是明确偏好，根据已确认字段判断是否可用于个性化建议。
    if tool_name == "get_user_preferences":
        return "已读取明确旅行偏好" if output and output.get("hasExplicitPreference") else "尚未设置明确旅行偏好"
    # 如果读取的是 Travel Memory，根据摘要列表说明是否存在 grounded 回忆。
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
