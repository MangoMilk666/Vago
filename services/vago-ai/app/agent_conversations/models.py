"""用户可长期保存的 Agent 对话 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.travel.models import utc_now_naive


class AgentConversation(Base):
    """一段由用户拥有的 Agent 会话，保存每段会话的授权偏好。"""

    __tablename__ = "agent_conversations"
    __table_args__ = (Index("idx_agent_conversations_user_updated", "user_uuid", "updated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # 对外暴露的会话 UUID，不使用自增主键作为 API 标识。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_uuid: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # 两个开关属于用户授权范围，而非模型可以自行改变的状态。
    use_rag: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_personal_context: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )


class AgentMessage(Base):
    """会话中的单条用户或 Agent 消息，以及可回放的展示附属数据。"""

    __tablename__ = "agent_messages"
    __table_args__ = (Index("idx_agent_messages_conversation_id", "conversation_uuid", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    conversation_uuid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON 文本仅保存展示所需引用、上下文标签和结构化计划，不保存模型推理过程。
    sources: Mapped[str | None] = mapped_column(Text)
    context_labels: Mapped[str | None] = mapped_column(Text)
    structured_plan: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
