"""旅行偏好 API 与 Personal Context 使用的 schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TravelPreferenceResponse(BaseModel):
    """用户确认过的旅行偏好。"""

    pace: str | None = None
    budget_level: str | None = Field(default=None, alias="budgetLevel")
    interests: list[str] = Field(default_factory=list)
    notes: str | None = None
    updated_at: datetime | None = Field(default=None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class TravelPreferenceUpdateRequest(BaseModel):
    """更新用户主动维护的旅行偏好的DTO；未传字段保持原值。"""

    pace: str | None = Field(default=None, max_length=32)
    budget_level: str | None = Field(default=None, alias="budgetLevel", max_length=32)
    interests: list[str] | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)
