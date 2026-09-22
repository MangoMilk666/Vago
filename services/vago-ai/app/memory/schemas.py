"""Travel Memory API schema。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCheckinFact(BaseModel):
    """由用户手动确认的打卡事实摘要。"""

    location_name: str = Field(alias="locationName")
    occurred_at: datetime = Field(alias="occurredAt")

    model_config = ConfigDict(populate_by_name=True)


class TravelMemoryFacts(BaseModel):
    """可追溯且不可由 Agent 任意修改的旅行事实快照。"""

    trip_uuid: str = Field(alias="tripUuid")
    trip_title: str = Field(alias="tripTitle")
    destination: str | None = None
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    itinerary_spot_names: list[str] = Field(default_factory=list, alias="itinerarySpotNames")
    automatic_sample_count: int = Field(alias="automaticSampleCount")
    checkins: list[MemoryCheckinFact] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class TravelMemoryResponse(BaseModel):
    """Travel Memory 对外响应，显式区分 facts 与 narrative。"""

    uuid: str
    trip_uuid: str = Field(alias="tripUuid")
    title: str
    facts: TravelMemoryFacts
    narrative: str | None = None
    facts_refreshed_at: datetime = Field(alias="factsRefreshedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class TravelMemoryUpdateRequest(BaseModel):
    """只允许用户编辑标题和叙事，不开放事实字段写入。"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    narrative: str | None = Field(default=None, max_length=10_000)

    model_config = ConfigDict(populate_by_name=True)
