from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent_runtime.runtime import AgentRuntime, AgentRuntimePreparation, AgentRuntimeProgress
from app.agent_runtime.selection import ToolSelectionPlan
from app.agent_runtime.spec import AgentSpec, AgentSpecRegistry, planner_spec
from app.models.schemas import ChatMessage
from app.plan_proposals.schemas import ProposalCreateRequest
from app.plan_proposals.service import create_proposal
from app.services.rag_chain import stream_agent_chat

logger = logging.getLogger(__name__)


class PlanningState(TypedDict, total=False):
    """单轮图状态；长期事实仍保存在现有会话和候选表。"""

    prompt: str
    messages: list[ChatMessage]
    use_personal_context: bool
    use_rag: bool
    conversation_uuid: str | None
    plan: ToolSelectionPlan
    preparation: AgentRuntimePreparation
    structured_plan: dict[str, Any] | None
    failed: bool


def _sse(payload: dict[str, Any]) -> str:
    '''转换成sse字符串'''
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _structured_plan_candidate(plan: dict[str, Any], trace_id: str) -> ProposalCreateRequest | None:
    """把有明确日期的结构化计划转成候选；没有地点来源时交给确定性校验标记。"""
    start_date = plan.get("start_date")
    end_date = plan.get("end_date")
    days = plan.get("days")
    # 如果模型没有提供完整日期或每日安排，先让用户补充信息，不能编造行程日期。
    if not start_date or not end_date or not isinstance(days, list) or not days:
        return None
    # 每日行程数据
    content_days: list[dict[str, Any]] = []
    for day in days:
        items = [
            {
                "id": uuid4().hex,
                "name": spot["name"],
                "kind": "custom",
                "city": plan.get("destination", ""),
                "durationMinutes": spot.get("duration_minutes"),
            }
            for spot in day.get("spots", [])
        ]
        content_days.append({
            "day": day["day_index"],
            "date": day.get("day_date"),
            "city": plan.get("destination", ""),
            "timezone": "Asia/Shanghai",
            "items": items,
            "legs": [],
        })
    # 封装为新增候选计划的DTO
    return ProposalCreateRequest(
        idempotencyKey=trace_id,
        targetKind="new_plan",
        brief={
            "startDate": start_date,
            "endDate": end_date,
            "timezone": "Asia/Shanghai",
            "budgetCurrency": plan.get("budget_currency", "CNY"),
            "hardConstraints": [],
        },
        content={"days": content_days, "gaps": ["地点来源、坐标与相邻路线尚待核验"]},
    )


class PlanningGraphRuntime:
    """组织并运行单轮 Agent 流程。

    类负责组装节点、决定节点之间的执行顺序，并把过程事件交给聊天接口。
    具体的资料读取、模型回答和候选保存仍由各自的现有服务完成。
    """

    def __init__(self, db: Session, user_uuid: str, spec: AgentSpec | None = None) -> None:
        """保存当前用户和数据库会话，并核对 Agent 配置中的工具是否真实可用。"""
        self._db = db
        self._user_uuid = user_uuid
        self._domain = AgentRuntime()
        self._spec = spec or planner_spec(self._domain.registry)
        AgentSpecRegistry([self._spec], self._domain.registry)

    async def stream(
        self, *, messages: list[ChatMessage], use_personal_context: bool,
        use_rag: bool, conversation_uuid: str | None,
    ) -> AsyncIterator[str]:
        """从用户消息开始运行整张图，逐条向聊天接口交出 SSE 事件。

        节点把进度放入 queue；本函数一边运行图，一边从 queue 读取事件。
        客户端停止读取时，函数末尾会取消尚未完成的图任务。
        """
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        turn_uuid = uuid4().hex
        sequence = 0

        async def emit(payload: dict[str, Any] | str) -> None:
            """统一给节点产生的事件编号，再放进等待发送给客户端的队列。"""
            nonlocal sequence
            if isinstance(payload, str):
                if not payload.startswith("data:"):
                    await queue.put(payload)
                    return
                event = json.loads(payload[5:].strip())
            else:
                event = payload
            sequence += 1
            event.update({
                "turnUuid": turn_uuid, "sequence": sequence,
                "conversationUuid": conversation_uuid,
            })
            await queue.put(_sse(event))

        async def select(state: PlanningState) -> dict[str, Any]:
            """根据本轮问题和最近的用户提问选择工具，并检查工具白名单。

            返回的 plan 写入图状态，下一节点 prepare 会按它读取资料。
            """
            recent = tuple(message.content for message in state["messages"][:-1] if message.role == "user")[-3:]
            plan = self._domain.select_plan(
                state["prompt"], recent, state["use_personal_context"], state["use_rag"],
            )
            # unknown: 未允许使用的工具名单
            unknown = set(plan.tool_names) - self._spec.allowed_tools
            if unknown or (plan.allow_rag_search and "search_personal_knowledge" not in self._spec.allowed_tools):
                raise ValueError(f"Agent 配置禁止本轮工具：{', '.join(sorted(unknown))}")
            await emit({"type": "agent.status", "label": "已确认本轮可使用的旅行资料范围"})
            return {"plan": plan}

        async def prepare(state: PlanningState) -> dict[str, Any]:
            """调用现有 AgentRuntime 读取已选中的个人资料。

            读取过程中的进度立即发给客户端；最终准备结果交给回答节点。
            """
            runtime = AgentRuntime(max_read_steps=self._spec.max_read_steps)
            recent = tuple(message.content for message in state["messages"][:-1] if message.role == "user")[-3:]
            preparation: AgentRuntimePreparation | None = None
            async for update in runtime.stream_prepare(
                self._db, self._user_uuid,
                use_personal_context=state["use_personal_context"],
                use_rag=state["use_rag"], prompt=state["prompt"],
                recent_user_messages=recent, selection_plan=state["plan"],
            ):
                # 如果工具产生公开进度，立即通过同一 SSE 流发送，不暴露原始 GPS 或工具参数。
                if isinstance(update, AgentRuntimeProgress):
                    await emit(update.event)
                else:
                    preparation = update
            if preparation is None:
                raise RuntimeError("领域读取未返回准备结果")
            return {"preparation": preparation}

        async def clarify(state: PlanningState) -> dict[str, Any]:
            """问题范围不明确时发出澄清问题，本轮不调用模型生成旅行建议。"""
            answer = "请告诉我具体的行程或日期范围，我再按这个范围查询你的旅行记录。"
            await emit({"type": "agent.clarification", "label": "需要确认查询范围"})
            await emit({"type": "text", "content": answer})
            return {"structured_plan": None, "failed": False}

        async def answer(state: PlanningState) -> dict[str, Any]:
            """调用原有的 stream_agent_chat，逐条转发模型生成的事件。

            同时记下结构化计划和错误状态，供后面的 candidate 节点判断。
            """
            preparation = state["preparation"]
            structured: dict[str, Any] | None = None
            failed = False
            async for chunk in stream_agent_chat(
                user_uuid=self._user_uuid, messages=state["messages"],
                use_rag=state["use_rag"] and preparation.allow_rag_search,
                personal_context=preparation.personal_context,
                context_labels=preparation.context_labels,
                max_iterations=self._spec.max_model_steps,
            ):
                # 结束标记由图的最终节点发送，候选保存结果必须先到达客户端。
                if chunk.strip() == "data: [DONE]":
                    continue
                if chunk.startswith("data:"):
                    event = json.loads(chunk[5:].strip())
                    if event.get("type") == "structured_plan":
                        structured = event.get("data")
                    elif event.get("type") == "error":
                        failed = True
                await emit(chunk)
            return {"structured_plan": structured, "failed": failed}

        async def candidate(state: PlanningState) -> dict[str, Any]:
            """模型给出完整计划时，将其作为当前会话的候选版本保存。

            保存后返回候选编号和校验状态；缺少必要信息时请求用户补充。
            """
            plan = state.get("structured_plan")
            conversation_uuid = state.get("conversation_uuid")
            # 如果没有持久化会话、结构化计划或本轮出错，就不创建候选版本。
            if not conversation_uuid or not plan or state.get("failed"):
                return {"failed": state.get("failed", False)}
            payload = _structured_plan_candidate(plan, state["preparation"].trace_id)
            if payload is None:
                await emit({"type": "agent.clarification", "label": "请补充旅行的开始日期、结束日期和每日安排后再保存候选"})
                return {"failed": False}
            try:
                proposal = create_proposal(self._db, self._user_uuid, conversation_uuid, payload)
            except Exception:
                logger.exception("[planning_graph] 候选保存失败 user=%s", self._user_uuid)
                await emit({"type": "agent.candidate_failed", "label": "候选保存失败，请稍后重试"})
                return {"failed": True}
            await emit({
                "type": "agent.candidate_ready", "label": "已保存待确认的候选计划",
                "proposalUuid": proposal.uuid, "version": proposal.version,
                "status": proposal.status, "validation": proposal.validation,
            })
            return {"failed": False}

        # 这些函数是图的节点(nodes)；边规定先选择工具、再读取资料，随后澄清或回答。
        graph = StateGraph(PlanningState)
        graph.add_node("select", select)
        graph.add_node("prepare", prepare)
        graph.add_node("clarify", clarify)
        graph.add_node("answer", answer)
        graph.add_node("candidate", candidate)
        graph.set_entry_point("select")
        # LangGraph体系的Edge，规定节点的执行顺序，比如 prepare 后进入澄清还是回答
        graph.add_edge("select", "prepare")
        graph.add_conditional_edges(
            "prepare", lambda state: "clarify" if state["plan"].clarification else "answer",
            {"clarify": "clarify", "answer": "answer"},
        )
        graph.add_edge("clarify", END)
        graph.add_edge("answer", "candidate")
        graph.add_edge("candidate", END)
        compiled = graph.compile()

        async def run_graph() -> None:
            """在时限内执行已组装的图，并发送完成、失败或超时事件。"""
            try:
                async with asyncio.timeout(self._spec.timeout_seconds):
                    result = await compiled.ainvoke({
                        "prompt": messages[-1].content, "messages": messages,
                        "use_personal_context": use_personal_context,
                        "use_rag": use_rag, "conversation_uuid": conversation_uuid,
                    })
                if result.get("failed"):
                    await emit({"type": "agent.failed", "label": "本轮规划未能完成"})
                else:
                    await emit({"type": "agent.completed", "label": "本轮规划已完成"})
            except TimeoutError:
                await emit({"type": "agent.failed", "label": "本轮规划已超时"})
                await emit({"type": "error", "message": "Agent 运行超时，请稍后重试"})
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[planning_graph] 执行失败 user=%s", self._user_uuid)
                await emit({"type": "agent.failed", "label": "本轮规划未能完成"})
                await emit({"type": "error", "message": "Agent 运行失败，请稍后重试"})
            finally:
                await queue.put(None)

        # 图在后台执行；当前生成器持续交出 queue 中的事件，让前端及时显示进度。
        task = asyncio.create_task(run_graph())
        try:
            while (chunk := await queue.get()) is not None:
                yield chunk
            yield "data: [DONE]\n\n"
        finally:
            # 如果客户端断开，立即取消图任务，不继续查询或保存候选。
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
