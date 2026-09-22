"""明确旅行偏好的持久化模型。"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.travel.models import utc_now_naive


class TravelPreference(Base):
    """用户主动维护的旅行偏好，不承载模型推断出的行为信号。"""

    __tablename__ = "travel_preferences"

    # 用户 UUID 同时作为偏好记录主键，保证一个用户只有一份明确偏好。
    user_uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 旅行节奏，例如 leisurely / balanced / packed；为空表示用户未声明。
    pace: Mapped[str | None] = mapped_column(String(32))
    # 预算倾向，例如 budget / mid / premium；为空表示用户未声明。
    budget_level: Mapped[str | None] = mapped_column(String(32))
    # 兴趣标签 JSON 字符串；使用 Text 保持 MySQL 与 SQLite 测试兼容。
    interests: Mapped[str | None] = mapped_column(Text)
    # 用户补充的自由文本约束或偏好。
    notes: Mapped[str | None] = mapped_column(Text)
    # 首次创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    # 最近更新时间。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
