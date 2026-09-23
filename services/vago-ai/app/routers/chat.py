"""
AI 对话路由（Chat Router）。

提供面向用户的 AI 对话接口，底层由 RAG Agent 驱动：
  - POST /api/v1/ai/chat          非流式对话，等待完整回答后返回 JSON
  - POST /api/v1/ai/chat/stream   流式对话，SSE 实时推送 token

两个接口均需 JWT 鉴权（Bearer token 经 get_current_user_uuid 依赖验证）：
  - 验证 HMAC-HS256 签名及过期时间（与 Java 共享 secret）
  - 检查 Redis 黑名单（退出登录后 Java 侧写入）
  - 从 JWT payload 提取 userUuid，无需客户端在请求体中传递

SSE 事件类型说明（流式接口）：
  {"type": "text",      "content": "..."}  — 文本 token，拼接后得到完整回答
  {"type": "searching", "query":   "..."}  — Agent 正在检索个人资料
  {"type": "sources",   "sources": [...]}  — 回答引用的个人资料来源（流结束前发送）
  {"type": "error",     "message": "..."}  — 生成过程中的错误
  data: [DONE]                             — 流结束标记
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.models.schemas import ChatMessage, ChatRequest, ChatResponse, SourceCitation
from app.agent_conversations import service as conversation_service
from collections.abc import AsyncIterator

from app.agent_runtime import AgentRuntime, AgentRuntimePreparation, AgentRuntimeProgress
from app.services.rag_chain import run_agent_chat, stream_agent_chat
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=ChatResponse,
    summary="AI 对话（非流式）",
    description=(
        "发送对话消息，等待 Agent 完整生成后一次性返回 JSON 响应。\n\n"
        "Agent 仅在问题需要个人资料且请求启用检索时，才检索用户知识源（RAG）：\n"
        "- 个人经验或已导入资料相关问题 → 可选检索后回答\n"
        "- 普通旅行知识或无关问题 → 直接调用 LLM 通用知识回答\n\n"
        "消息历史由调用方维护并完整传入（`messages` 字段），服务端无状态。"
    ),
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ChatResponse:
    """
    非流式 AI 对话接口。

    调用 RAG Agent（run_agent_chat），阻塞等待 LLM 生成完毕，
    返回完整的回答文本和引用的个人资料来源。

    参数:
        request: ChatRequest，包含 messages、use_rag 等字段（user_uuid 由 JWT 注入）。
        user_uuid: 从 JWT payload 提取，由 get_current_user_uuid 依赖提供。

    返回:
        ChatResponse，包含 answer（回答文本）、sources（资料引用）、model（模型名称）。

    异常:
        401 — JWT 缺失 / 无效 / 已过期；
        400 — 消息格式不合法（如最后一条不是 user 消息）；
        503 — LLM 或 Qdrant 服务不可用。
    """
    _validate_messages(request)

    logger.info(
        "[chat] 非流式请求 user=%s messages=%d use_rag=%s",
        user_uuid, len(request.messages), request.use_rag,
    )

    preparation = _prepare_agent_runtime(
        db, user_uuid, request.use_personal_context, request.use_rag, request.messages,
    )
    # 工具调用的请求参数集合？
    try:
        call_kwargs = {
            "user_uuid": user_uuid,
            "messages": request.messages,
            # 如果客户端开启个人资料检索，保留 RAG 工具供 LLM 按需调用。
            "use_rag": request.use_rag and preparation.allow_rag_search,
        }
        # 分支条件：仅 客户端 显式开启 Context 时才扩展既有对话调用参数。
        if preparation.personal_context is not None:
            call_kwargs.update(
                personal_context=preparation.personal_context,
                context_labels=preparation.context_labels,
            )
        result = await run_agent_chat(**call_kwargs)
    except Exception as exc:
        logger.error("[chat] 非流式生成失败 user=%s error=%s", user_uuid, exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"AI 服务暂时不可用：{exc}") from exc

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        model=result["model"],
        structured_plan=result.get("structured_plan"),
        contextLabels=result.get("context_labels", preparation.context_labels),
    )


@router.post(
    "/stream",
    summary="AI 对话（流式 SSE）",
    description=(
        "发送对话消息，以 SSE（Server-Sent Events）格式实时流式返回 token。\n\n"
        "前端通过 `EventSource` 或 `fetch` + ReadableStream 消费流，\n"
        "拼接 `type=text` 事件的 `content` 字段即可实现打字机效果。\n\n"
        "流结束时发送 `data: [DONE]` 标记，前端据此关闭连接。"
    ),
    response_class=StreamingResponse,
)
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> StreamingResponse:
    """
    流式 AI 对话接口（SSE）。

    通过 LangChain astream_events(v2) 捕获 token 级事件，
    以 SSE 格式实时推送给前端，支持打字机效果。

    参数:
        request: ChatRequest，字段与非流式接口完全相同（user_uuid 由 JWT 注入）。
        user_uuid: 从 JWT payload 提取，由 get_current_user_uuid 依赖提供。

    返回:
        StreamingResponse，Content-Type 为 text/event-stream。
        前端通过 SSE 协议接收，详见路由 description 中的事件格式说明。

    异常:
        401 — JWT 缺失 / 无效 / 已过期；
        400 — 消息格式不合法；
        流中如有错误，以 {"type": "error", "message": "..."} 事件推送，不中断连接。
    """
    _validate_messages(request)

    logger.info(
        "[chat] 流式请求 user=%s messages=%d use_rag=%s",
        user_uuid, len(request.messages), request.use_rag,
    )

    if request.conversation_uuid:
        # 分支条件：带会话 UUID 的 Web 请求先落下用户原话，刷新后也可恢复此轮问题。
        conversation_service.record_user_message(
            db,
            user_uuid,
            request.conversation_uuid,
            request.messages[-1].content,
            request.use_rag,
            request.use_personal_context,
        )

    async def event_generator():
        """
        异步事件生成器，包装 stream_agent_chat 并统一异常处理。

        若 stream_agent_chat 在首个 yield 前抛出异常，
        此处捕获并推送 error 事件，确保前端不会收到空流。
        """
        answer_parts: list[str] = []
        sources: list[dict] = []
        response_context_labels: list[str] = []
        agent_events: list[dict[str, str]] = []
        structured_plan: dict | None = None
        stream_failed = False
        try:
            preparation: AgentRuntimePreparation | None = None
            # Runtime 逐步产出公开事件；准备完成后才把真实上下文交给既有 LLM/RAG 链路。
            async for update in _stream_agent_runtime(
                db, user_uuid, request.use_personal_context, request.use_rag, request.messages,
            ):
                if isinstance(update, AgentRuntimeProgress):
                    agent_events.append(update.event)
                    yield f"data: {json.dumps(update.event, ensure_ascii=False)}\n\n"
                else:
                    preparation = update

            if preparation is None:
                raise RuntimeError("Agent Runtime 未返回上下文准备结果")
            response_context_labels = preparation.context_labels
            call_kwargs = {
                "user_uuid": user_uuid,
                "messages": request.messages,
                # 如果客户端开启个人资料检索，保留 RAG 工具供 LLM 按需调用。
                "use_rag": request.use_rag and preparation.allow_rag_search,
            }
            # 分支条件：只有前端明确授权时才把结构化事实注入 Agent 对话。
            if preparation.personal_context is not None:
                call_kwargs.update(
                    personal_context=preparation.personal_context,
                    context_labels=preparation.context_labels,
                )
            async for chunk in stream_agent_chat(**call_kwargs):
                event = _parse_sse_event(chunk)
                if event and event.get("type", "").startswith(("agent.", "tool.")):
                    agent_events.append(event)
                # 分支条件：只有正常文本流才写入长期历史，错误提示仅作为当前界面临时反馈。
                if event and event.get("type") == "text":
                    content = event.get("content")
                    if isinstance(content, str):
                        answer_parts.append(content)
                elif event and event.get("type") == "sources":
                    sources = event.get("sources") or []
                elif event and event.get("type") == "context":
                    response_context_labels = event.get("labels") or []
                elif event and event.get("type") == "structured_plan":
                    structured_plan = event.get("data")
                elif event and event.get("type") == "error":
                    stream_failed = True
                yield chunk
        except Exception as exc:
            stream_failed = True
            logger.error("[chat] 事件生成器异常 user=%s error=%s", user_uuid, exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            # 分支条件：仅有持久化会话且本轮未报错时，保存完整 Agent 回答供后续回放。
            if request.conversation_uuid and not stream_failed:
                try:
                    conversation_service.record_assistant_message(
                        db,
                        user_uuid,
                        request.conversation_uuid,
                        "".join(answer_parts),
                        sources=sources,
                        context_labels=response_context_labels,
                        agent_events=agent_events,
                        structured_plan=structured_plan,
                    )
                except Exception as exc:
                    # 历史保存失败不应反向中断已成功返回给用户的模型回答。
                    logger.error("[chat] 保存会话历史失败 user=%s error=%s", user_uuid, exc, exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁止 Nginx 缓冲，确保 SSE 实时推送
        },
    )


# ─── 私有工具 ─────────────────────────────────────────────────────────────────

def _prepare_agent_runtime(
    db: Session,
    user_uuid: str,
    use_personal_context: bool,
    use_rag: bool,
    messages: list[ChatMessage],
) -> AgentRuntimePreparation:
    """准备只读 Agent Runtime；整体初始化失败时仍保留普通对话能力。"""
    try:
        return AgentRuntime().prepare(
            db, user_uuid,
            use_personal_context=use_personal_context,
            use_rag=use_rag,
            prompt=messages[-1].content,
            recent_user_messages=_recent_user_messages(messages),
        )
    except Exception as exc:
        # 分支条件：Runtime 初始化异常时，不阻断现有 AI 对话链路。
        logger.warning("[chat] Agent Runtime 初始化失败 user=%s error=%s", user_uuid, exc)
        return AgentRuntimePreparation(trace_id="", personal_context=None, context_labels=[], events=[])


async def _stream_agent_runtime(
    db: Session,
    user_uuid: str,
    use_personal_context: bool,
    use_rag: bool,
    messages: list[ChatMessage],
) -> AsyncIterator[AgentRuntimeProgress | AgentRuntimePreparation]:
    """为 SSE 路由提供逐步 Runtime 事件；异常时回退为普通对话。"""
    try:
        async for update in AgentRuntime().stream_prepare(
            db,
            user_uuid,
            use_personal_context=use_personal_context,
            use_rag=use_rag,
            prompt=messages[-1].content,
            recent_user_messages=_recent_user_messages(messages),
        ):
            yield update
    except Exception as exc:
        # 分支条件：Runtime 自身初始化失败时保留既有 LLM 对话可用性，并发送可见降级事件。
        logger.warning("[chat] Agent Runtime 流式初始化失败 user=%s error=%s", user_uuid, exc)
        yield AgentRuntimeProgress({"type": "agent.failed", "label": "旅行上下文暂时不可用，已切换为通用建议"})
        yield AgentRuntimePreparation(trace_id="", personal_context=None, context_labels=[], events=[])


def _recent_user_messages(messages: list[ChatMessage]) -> tuple[str, ...]:
    """只取最近三条用户原话帮助理解类似于“那明天呢”这样的追问，避免把完整会话再次用于路由。"""
    return tuple(
        message.content
        for message in messages[:-1]
        if message.role == "user"
    )[-3:]


def _parse_sse_event(chunk: str) -> dict | None:
    """从既有 Agent SSE 文本中读取可持久化的公开事件字段。"""
    if not chunk.startswith("data:"):
        return None
    raw = chunk[5:].strip()
    if raw == "[DONE]":
        return None
    try:
        event = json.loads(raw)
        return event if isinstance(event, dict) else None
    except json.JSONDecodeError:
        return None

def _validate_messages(request: ChatRequest) -> None:
    """
    校验对话消息格式合法性。

    规则：
      1. messages 列表不得为空；
      2. 最后一条消息的 role 必须为 "user"（当前用户输入）；
      3. 消息数量不得超过 50 条（防止构造超长上下文导致 LLM Token 超限）。

    参数:
        request: ChatRequest 实例。

    异常:
        HTTPException(400) — 格式不合法时抛出，附带说明文字。
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages 不得为空")
    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=400,
            detail="messages 最后一条必须为 role='user' 的用户消息",
        )
    if len(request.messages) > 50:
        raise HTTPException(
            status_code=400,
            detail="messages 最多支持 50 条消息历史",
        )
