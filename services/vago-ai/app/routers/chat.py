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
  {"type": "searching", "query":   "..."}  — Agent 正在检索用户攻略库
  {"type": "sources",   "sources": [...]}  — 回答引用的攻略来源（流结束前发送）
  {"type": "error",     "message": "..."}  — 生成过程中的错误
  data: [DONE]                             — 流结束标记
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies.auth import get_current_user_uuid
from app.models.schemas import ChatRequest, ChatResponse, SourceCitation
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
        "Agent 会根据问题类型自动决定是否检索用户私有攻略库（RAG）：\n"
        "- 旅行相关问题 → 检索攻略库 → 结合检索结果生成回答\n"
        "- 非旅行问题  → 直接调用 LLM 通用知识回答\n\n"
        "消息历史由调用方维护并完整传入（`messages` 字段），服务端无状态。"
    ),
)
async def chat(
    request: ChatRequest,
    user_uuid: str = Depends(get_current_user_uuid),
) -> ChatResponse:
    """
    非流式 AI 对话接口。

    调用 RAG Agent（run_agent_chat），阻塞等待 LLM 生成完毕，
    返回完整的回答文本和引用的攻略来源。

    参数:
        request: ChatRequest，包含 messages、use_rag 等字段（user_uuid 由 JWT 注入）。
        user_uuid: 从 JWT payload 提取，由 get_current_user_uuid 依赖提供。

    返回:
        ChatResponse，包含 answer（回答文本）、sources（攻略引用）、model（模型名称）。

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

    try:
        result = await run_agent_chat(
            user_uuid=user_uuid,
            messages=request.messages,
        )
    except Exception as exc:
        logger.error("[chat] 非流式生成失败 user=%s error=%s", user_uuid, exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"AI 服务暂时不可用：{exc}") from exc

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        model=result["model"],
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

    async def event_generator():
        """
        异步事件生成器，包装 stream_agent_chat 并统一异常处理。

        若 stream_agent_chat 在首个 yield 前抛出异常，
        此处捕获并推送 error 事件，确保前端不会收到空流。
        """
        try:
            async for chunk in stream_agent_chat(
                user_uuid=user_uuid,
                messages=request.messages,
            ):
                yield chunk
        except Exception as exc:
            logger.error("[chat] 事件生成器异常 user=%s error=%s", user_uuid, exc)
            import json
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁止 Nginx 缓冲，确保 SSE 实时推送
        },
    )


# ─── 私有工具 ─────────────────────────────────────────────────────────────────

def _validate_messages(request: ChatRequest) -> None:
    """
    校验对话消息格式合法性。

    规则：
      1. messages 列表不得为空；
      2. 最后一条消息的 role 必须为 "user"（当前用户输入）。

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
