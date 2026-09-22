"""Web Agent 会话的创建、回放、懒加载与删除 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.agent_conversations import service
from app.agent_conversations.schemas import (
    ConversationCreateRequest,
    ConversationMessagesPage,
    ConversationResponse,
)
from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.get("/conversations", response_model=ApiResponse[list[ConversationResponse]])
def list_agent_conversations(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[ConversationResponse]]:
    """读取当前用户最近活跃的 Agent 会话。"""
    return success(service.list_conversations(db, user_uuid))


@router.post("/conversations", response_model=ApiResponse[ConversationResponse])
def create_agent_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ConversationResponse]:
    """创建一段新的空白对话。"""
    return success(service.create_conversation(db, user_uuid, payload), "已创建新对话")


@router.get("/conversations/{conversation_uuid}/messages", response_model=ApiResponse[ConversationMessagesPage])
def list_agent_messages(
    conversation_uuid: str,
    before_uuid: str | None = Query(default=None, alias="beforeUuid"),
    limit: int = Query(default=30, ge=1, le=50),
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ConversationMessagesPage]:
    """读取会话消息；携带 beforeUuid 可继续加载更早历史。"""
    return success(service.get_messages(db, user_uuid, conversation_uuid, before_uuid, limit))


@router.delete("/conversations/{conversation_uuid}", response_model=ApiResponse[None])
def delete_agent_conversation(
    conversation_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[None]:
    """删除用户指定的整段 Agent 对话。"""
    service.delete_conversation(db, user_uuid, conversation_uuid)
    return success(message="对话已删除")
