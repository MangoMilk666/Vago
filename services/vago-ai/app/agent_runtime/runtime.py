"""Phase 10 的最小 Think-Execute-Observe Runtime。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent_runtime.registry import AgentTool, ToolRegistry
from app.footprints import service as footprint_service
from app.knowledge import service as knowledge_service
from app.memory import service as memory_service
from app.personal_context.schemas import PersonalContextPreview
from app.personal_context.service import format_context_for_agent
from app.preferences import service as preference_service
from app.travel import service as travel_service

logger = logging.getLogger(__name__)

MAX_READ_STEPS = 5


@dataclass(frozen=True)
class AgentRuntimePreparation:
    """LLM 调用前的公开执行事件与已授权上下文快照。"""

    trace_id: str
    personal_context: str | None
    context_labels: list[str]
    events: list[dict[str, str]]


class AgentRuntime:
    """只读上下文协调器；写操作、审批与外部工具仍留待后续 Phase。"""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or ToolRegistry([
            AgentTool("get_current_trip", "正在读取当前行程与近期历史", _get_travel_context),
            AgentTool("get_recent_footprint", "正在查看近期旅行足迹", _get_live_observations),
            AgentTool("get_user_preferences", "正在读取明确旅行偏好", _get_preferences),
            AgentTool("get_travel_memories", "正在读取旅行回忆摘要", _get_memories),
            AgentTool("get_personal_knowledge_summary", "正在确认个人资料范围", _get_knowledge_summary),
        ])

    def prepare(
        self,
        db: Session,
        user_uuid: str,
        *,
        use_personal_context: bool,
        use_rag: bool,
    ) -> AgentRuntimePreparation:
        """执行有限次只读工具调用，并将真实结果组装为本轮 Context。"""
        trace_id = uuid4().hex
        events: list[dict[str, str]] = [
            _event("agent.started", "开始整理本轮旅行上下文", trace_id=trace_id),
        ]
        state: dict[str, Any] = {
            "travelContext": {"currentTrip": None, "travelHistory": []},
            "liveObservations": None,
            "preferences": {},
            "memories": [],
            "knowledgeSummary": {},
        }
        tool_names = _select_read_tools(use_personal_context, use_rag)

        # 分支条件：用户未授权任何个人数据时，保留通用对话但不执行任何领域读取。
        if not tool_names:
            events.append(_event("agent.status", "本轮未启用个人旅行上下文", trace_id=trace_id))
            return AgentRuntimePreparation(trace_id, None, [], events)

        events.append(_event("agent.status", "正在获取已授权的旅行信息", trace_id=trace_id))

        for index, tool_name in enumerate(tool_names[:MAX_READ_STEPS], start=1):
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
            if index == MAX_READ_STEPS:
                events.append(_event("agent.status", "已达到本轮读取上限，开始生成建议", trace_id=trace_id))

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
        )


def _select_read_tools(use_personal_context: bool, use_rag: bool) -> list[str]:
    """根据用户授权选择可调用的只读工具；语义检索仍由现有 LLM Tool Calling 按需触发。"""
    tools: list[str] = []
    if use_personal_context:
        tools.extend(["get_current_trip", "get_recent_footprint", "get_user_preferences", "get_travel_memories"])
    if use_rag:
        tools.append("get_personal_knowledge_summary")
    return tools


def _get_travel_context(db: Session, user_uuid: str, _: dict[str, Any]) -> dict[str, Any]:
    """通过 Travel Domain Service 读取当前行程和近期历史。"""
    return travel_service.get_agent_travel_context(db, user_uuid)


def _get_live_observations(db: Session, user_uuid: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """仅在存在进行中行程时读取足迹摘要，避免无意义的跨行程查询。"""
    current_trip = state["travelContext"].get("currentTrip")
    if not current_trip:
        return None
    return footprint_service.get_agent_observation_context(db, user_uuid, current_trip["uuid"])


def _get_preferences(db: Session, user_uuid: str, _: dict[str, Any]) -> dict[str, Any]:
    """读取用户明确确认的偏好，不读取模型推断的信号。"""
    return preference_service.get_agent_preference_context(db, user_uuid)


def _get_memories(db: Session, user_uuid: str, _: dict[str, Any]) -> list[dict[str, Any]]:
    """读取 grounded Travel Memory 摘要。"""
    return memory_service.get_agent_memory_context(db, user_uuid)


def _get_knowledge_summary(db: Session, user_uuid: str, _: dict[str, Any]) -> dict[str, Any]:
    """只确认知识资料范围；具体文本必须继续经 RAG Tool 获取。"""
    return knowledge_service.get_agent_knowledge_summary(db, user_uuid)


def _store_tool_output(state: dict[str, Any], tool_name: str, output: Any) -> None:
    """将工具 Observation 放入 Runtime State，供后续工具和 Prompt 使用。"""
    # 工具名 和 读取数据的字段名一一对应
    mapping = {
        "get_current_trip": "travelContext",
        "get_recent_footprint": "liveObservations",
        "get_user_preferences": "preferences",
        "get_travel_memories": "memories",
        "get_personal_knowledge_summary": "knowledgeSummary",
    }
    state[mapping[tool_name]] = output


def _to_context_preview(state: dict[str, Any]) -> PersonalContextPreview:
    """把已观察的领域结果转换为统一 Context对象，不引入新的数据存储。"""
    travel_context = state["travelContext"] or {"currentTrip": None, "travelHistory": []}
    current_trip = travel_context.get("currentTrip")
    travel_history = travel_context.get("travelHistory", [])
    preferences = state["preferences"] or {}
    memories = state["memories"] or []
    knowledge_summary = state["knowledgeSummary"] or {}
    live_observations = state["liveObservations"]
    labels: list[str] = []
    if current_trip:
        labels.append("当前行程与日程")
    if travel_history:
        labels.append("近期旅行历史")
    if live_observations:
        labels.append("近期旅行观察")
    if preferences.get("hasExplicitPreference"):
        labels.append("明确旅行偏好")
    if memories:
        labels.append("Grounded Travel Memory")
    if knowledge_summary.get("sourceCount", 0):
        labels.append("个人知识资料摘要")
    return PersonalContextPreview(
        labels=labels,
        currentTrip=current_trip,
        travelHistory=travel_history,
        liveObservations=live_observations,
        preferences=preferences,
        memories=memories,
        knowledgeSummary=knowledge_summary,
    )


def _summary_for_tool(tool_name: str, output: Any) -> str:
    """生成不含 GPS 原始坐标与内部数据结构的简短执行结果。"""
    if tool_name == "get_current_trip":
        return "已读取当前行程与近期旅行历史" if output and output.get("currentTrip") else "当前没有进行中的行程"
    if tool_name == "get_recent_footprint":
        return "已读取近期旅行观察" if output else "当前行程暂无可用旅行观察"
    if tool_name == "get_user_preferences":
        return "已读取明确旅行偏好" if output and output.get("hasExplicitPreference") else "尚未设置明确旅行偏好"
    if tool_name == "get_travel_memories":
        return "已读取旅行回忆摘要" if output else "暂无已生成的旅行回忆"
    if tool_name == "get_personal_knowledge_summary":
        return "已确认个人资料范围" if output and output.get("sourceCount") else "暂无个人知识资料"
    return "已完成读取"


def _event(event_type: str, label: str, **extra: str) -> dict[str, str]:
    """统一构造可安全展示的执行事件，不包含模型推理或原始事实。"""
    return {"type": event_type, "label": label, **extra}
