"""Agent 对话持久化 API 的请求与响应模型。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.schemas import SourceCitation


class ConversationCreateRequest(BaseModel):
    """创建空白会话的请求；首条用户消息会自动替换默认标题。"""

    title: str | None = Field(default=None, max_length=120)
    use_rag: bool = Field(default=True, alias="useRag")
    use_personal_context: bool = Field(default=True, alias="usePersonalContext")

    model_config = {"populate_by_name": True}


class ConversationResponse(BaseModel):
    """侧栏展示的轻量会话摘要。"""

    uuid: str
    title: str
    use_rag: bool = Field(alias="useRag")
    use_personal_context: bool = Field(alias="usePersonalContext")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class ConversationMessageResponse(BaseModel):
    """可回放的对话消息；不含临时流式状态。"""

    uuid: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[SourceCitation] = Field(default_factory=list)
    context_labels: list[str] = Field(default_factory=list, alias="contextLabels")
    structured_plan: dict | None = Field(default=None, alias="structuredPlan")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class ConversationMessagesPage(BaseModel):
    """按时间倒序翻页读取后，再按正序交给聊天界面渲染。"""

    messages: list[ConversationMessageResponse]
    next_before_uuid: str | None = Field(default=None, alias="nextBeforeUuid")

    model_config = {"populate_by_name": True}
