"""Personal Travel Context 的传输模型。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PersonalContextPreview(BaseModel):
    """Agent 可读取的个人旅行上下文预览，不包含原始 GPS 经纬度。"""

    labels: list[str] = Field(default_factory=list)
    current_trip: dict[str, Any] | None = Field(default=None, alias="currentTrip")
    travel_history: list[dict[str, Any]] = Field(default_factory=list, alias="travelHistory")
    live_observations: dict[str, Any] | None = Field(default=None, alias="liveObservations")
    preferences: dict[str, Any] = Field(default_factory=dict)
    memories: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_summary: dict[str, int] = Field(default_factory=dict, alias="knowledgeSummary")

    model_config = ConfigDict(populate_by_name=True)
