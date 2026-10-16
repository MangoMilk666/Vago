"""旅行规划候选的持久化模型，与正式 Plan/Trip 分离。"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.travel.models import utc_now_naive


class PlanProposal(Base):
    """一段会话中的不可变候选版本；状态仅表示尚待后续阶段校验。"""

    __tablename__ = "plan_proposals"
    __table_args__ = (
        UniqueConstraint("conversation_uuid", "version", name="uk_plan_proposals_conversation_version"),
        UniqueConstraint("conversation_uuid", "idempotency_key", name="uk_plan_proposals_conversation_key"),
        Index("idx_plan_proposals_user_conversation", "user_uuid", "conversation_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    conversation_uuid: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_plan_uuid: Mapped[str | None] = mapped_column(String(32))
    # 仅记录创建时 Plan 的快照时间；阶段 7 仍须复核日程变化与状态。
    target_plan_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    brief: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # 为阶段 2A 的来源映射留位；当前公开创建接口固定为 vago，不接受旧身份决定归属。
    source_system: Mapped[str] = mapped_column(String(32), default="vago", nullable=False)
    source_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
