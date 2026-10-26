from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WkfImportRecord(Base):
    """保存一次历史来源记录与 Vago 测试账号中的目标映射。"""

    __tablename__ = "wkf_import_records"
    __table_args__ = (
        UniqueConstraint("user_uuid", "source_key", name="uk_wkf_import_user_source"),
        Index("idx_wkf_import_user_batch", "user_uuid", "batch_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    target_kind: Mapped[str | None] = mapped_column(String(32))
    target_uuid: Mapped[str | None] = mapped_column(String(32))
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
