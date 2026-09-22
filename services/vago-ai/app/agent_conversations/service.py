"""Agent 会话领域服务，负责用户隔离、分页与流式结果落库。"""

import json
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agent_conversations.models import AgentConversation, AgentMessage
from app.agent_conversations.schemas import (
    ConversationCreateRequest,
    ConversationMessageResponse,
    ConversationMessagesPage,
    ConversationResponse,
    ConversationUpdateRequest,
)
from app.core.exceptions import AppException
from app.travel.models import utc_now_naive

DEFAULT_TITLE = "新对话"


def create_conversation(
    db: Session,
    user_uuid: str,
    payload: ConversationCreateRequest,
) -> ConversationResponse:
    """创建用户明确发起的一段空白 Agent 对话。"""
    conversation = AgentConversation(
        uuid=uuid4().hex,
        user_uuid=user_uuid,
        title=(payload.title or "").strip()[:120] or DEFAULT_TITLE,
        use_rag=payload.use_rag,
        use_personal_context=payload.use_personal_context,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _to_conversation_response(conversation)


def list_conversations(db: Session, user_uuid: str, limit: int = 50) -> list[ConversationResponse]:
    """按最近活动时间展示当前用户的会话侧栏。"""
    conversations = db.scalars(
        select(AgentConversation)
        .where(AgentConversation.user_uuid == user_uuid)
        .order_by(AgentConversation.updated_at.desc(), AgentConversation.id.desc())
        .limit(limit)
    ).all()
    return [_to_conversation_response(item) for item in conversations]


def get_messages(
    db: Session,
    user_uuid: str,
    conversation_uuid: str,
    before_uuid: str | None = None,
    limit: int = 30,
) -> ConversationMessagesPage:
    """读取会话最近一页消息；较旧消息通过最早 UUID 继续上拉加载。每次默认加载30条"""
    conversation = get_owned_conversation(db, user_uuid, conversation_uuid)
    before_id = _resolve_before_id(db, conversation.uuid, before_uuid)
    statement = select(AgentMessage).where(AgentMessage.conversation_uuid == conversation.uuid)
    # 分支条件：携带游标时只读取该页之前的历史，避免重复返回已展示消息。
    if before_id is not None:
        statement = statement.where(AgentMessage.id < before_id)
    # 每次加载limit条
    rows_desc = db.scalars(statement.order_by(AgentMessage.id.desc()).limit(limit + 1)).all()
    has_more = len(rows_desc) > limit
    rows = list(reversed(rows_desc[:limit]))
    return ConversationMessagesPage(
        messages=[_to_message_response(item) for item in rows],
        nextBeforeUuid=rows[0].uuid if has_more and rows else None,
    )


def get_owned_conversation(db: Session, user_uuid: str, conversation_uuid: str) -> AgentConversation:
    """读取归属当前用户的会话，拒绝跨账号追加、读取或删除。conversation不存在抛出异常"""
    conversation = db.scalar(
        select(AgentConversation).where(
            AgentConversation.uuid == conversation_uuid,
            AgentConversation.user_uuid == user_uuid,
        )
    )
    if conversation is None:
        raise AppException("对话不存在或无权访问", status_code=404, code="AGENT_CONVERSATION_NOT_FOUND")
    return conversation


def record_user_message(
    db: Session,
    user_uuid: str,
    conversation_uuid: str,
    content: str,
    use_rag: bool,
    use_personal_context: bool,
) -> AgentConversation:
    """在发起模型调用前保存用户消息，并同步本轮明确选择的授权范围。"""
    conversation = get_owned_conversation(db, user_uuid, conversation_uuid)
    conversation.use_rag = use_rag
    conversation.use_personal_context = use_personal_context
    # 分支条件：默认标题只在第一条有效用户消息到来时替换，避免覆盖用户自定义标题。
    if conversation.title == DEFAULT_TITLE:
        conversation.title = _make_title(content)
    db.add(AgentMessage(uuid=uuid4().hex, conversation_uuid=conversation.uuid, role="user", content=content))
    conversation.updated_at = utc_now_naive()
    db.commit()
    return conversation


def record_assistant_message(
    db: Session,
    user_uuid: str,
    conversation_uuid: str,
    content: str,
    sources: list[dict] | None = None,
    context_labels: list[str] | None = None,
    structured_plan: dict | None = None,
) -> None:
    """仅在流式生成得到有效回答后保存 Agent 消息与可回放展示数据。"""
    conversation = get_owned_conversation(db, user_uuid, conversation_uuid)
    # 分支条件：网络中断或模型未生成文本时不伪造一条“空回答”历史。
    if not content.strip():
        return
    db.add(
        AgentMessage(
            uuid=uuid4().hex,
            conversation_uuid=conversation.uuid,
            role="assistant",
            content=content,
            sources=_dump_json(sources),
            context_labels=_dump_json(context_labels),
            structured_plan=_dump_json(structured_plan),
        )
    )
    conversation.updated_at = utc_now_naive()
    db.commit()


def delete_conversation(db: Session, user_uuid: str, conversation_uuid: str) -> None:
    """删除一整段用户对话及其消息，不影响任何旅行事实或知识资料。"""
    conversation = get_owned_conversation(db, user_uuid, conversation_uuid)
    db.execute(delete(AgentMessage).where(AgentMessage.conversation_uuid == conversation.uuid))
    db.delete(conversation)
    db.commit()


def update_conversation(
    db: Session,
    user_uuid: str,
    conversation_uuid: str,
    payload: ConversationUpdateRequest,
) -> ConversationResponse:
    """更新用户主动维护的会话标题，不影响已保存的消息内容。"""
    conversation = get_owned_conversation(db, user_uuid, conversation_uuid)
    title = " ".join(payload.title.split())
    # 分支条件：全空白标题没有识别价值，拒绝写入而不是退回默认标题掩盖用户输入错误。
    if not title:
        raise AppException("对话标题不能为空", status_code=400, code="AGENT_CONVERSATION_TITLE_EMPTY")
    conversation.title = title[:120]
    conversation.updated_at = utc_now_naive()
    db.commit()
    db.refresh(conversation)
    return _to_conversation_response(conversation)


def _resolve_before_id(db: Session, conversation_uuid: str, before_uuid: str | None) -> int | None:
    """将公开 UUID 游标解析为同一会话内的内部排序键。"""
    if not before_uuid:
        return None
    message = db.scalar(
        select(AgentMessage).where(
            AgentMessage.uuid == before_uuid,
            AgentMessage.conversation_uuid == conversation_uuid,
        )
    )
    if message is None:
        raise AppException("对话历史游标无效", status_code=400, code="AGENT_MESSAGE_CURSOR_INVALID")
    return message.id


def _make_title(content: str) -> str:
    """用首个问题生成可扫描的侧栏标题，不调用模型额外生成标题。最多前36个字符"""
    normalized = " ".join(content.split())
    return normalized[:36] + ("…" if len(normalized) > 36 else "")


def _dump_json(value: object | None) -> str | None:
    """空附属数据保持 NULL，减少历史记录体积。"""
    return json.dumps(value, ensure_ascii=False) if value else None


def _load_json(value: str | None, default: object) -> object:
    """历史附属 JSON 损坏时降级为空，不影响用户继续阅读文字对话。"""
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _to_conversation_response(item: AgentConversation) -> ConversationResponse:
    '''
    转换为ConversationResponse VO对象
    '''
    return ConversationResponse(
        uuid=item.uuid,
        title=item.title,
        useRag=item.use_rag,
        usePersonalContext=item.use_personal_context,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


def _to_message_response(item: AgentMessage) -> ConversationMessageResponse:
    '''
    转换为可回放的对话消息，即ConversationMessageResponse VO对象
    '''
    return ConversationMessageResponse(
        uuid=item.uuid,
        role=item.role,
        content=item.content,
        sources=_load_json(item.sources, []),
        contextLabels=_load_json(item.context_labels, []),
        structuredPlan=_load_json(item.structured_plan, None),
        createdAt=item.created_at,
    )
