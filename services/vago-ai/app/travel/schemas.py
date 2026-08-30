"""Trip / Plan / Itinerary 的请求与响应 schema。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TripCreateRequest(BaseModel):
    """创建正式行程请求。"""

    title: str = Field(min_length=1, max_length=100)
    destination: str | None = Field(default=None, max_length=200)
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    cover_image_key: str | None = Field(default=None, alias="coverImageKey")

    model_config = ConfigDict(populate_by_name=True)


class TripUpdateRequest(BaseModel):
    """更新正式行程请求；None 表示不更新该字段。"""

    title: str | None = Field(default=None, max_length=100)
    destination: str | None = Field(default=None, max_length=200)
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")
    cover_image_key: str | None = Field(default=None, alias="coverImageKey")
    status: int | None = Field(default=None, ge=1, le=3)

    model_config = ConfigDict(populate_by_name=True)


class TripResponse(BaseModel):
    """正式行程响应。"""

    uuid: str
    title: str
    destination: str | None = None
    cover_image_key: str | None = Field(default=None, alias="coverImageKey")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    status: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    # 允许字段名兼容；允许从整个对象的属性中取值
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PlanCreateRequest(BaseModel):
    """创建旅行计划草稿请求。"""

    title: str = Field(min_length=1, max_length=100)
    destination: str | None = Field(default=None, max_length=200)
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")
    budget: Decimal | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, alias="budgetCurrency", max_length=3)
    notes: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


class PlanUpdateRequest(BaseModel):
    """更新旅行计划草稿请求。"""

    title: str | None = Field(default=None, max_length=100)
    destination: str | None = Field(default=None, max_length=200)
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")
    budget: Decimal | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, alias="budgetCurrency", max_length=3)
    notes: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


class PlanResponse(BaseModel):
    """旅行计划草稿响应。"""

    uuid: str
    title: str
    destination: str | None = None
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")
    budget: Decimal | None = None
    budget_currency: str = Field(alias="budgetCurrency")
    notes: str | None = None
    converted_trip_uuid: str | None = Field(default=None, alias="convertedTripUuid")
    status: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ItinerarySpotRequest(BaseModel):
    """每日景点 / 打卡点请求。"""

    uuid: str | None = None
    name: str = Field(min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=300)
    category: int | None = Field(default=None, ge=0, le=5)
    sort_order: int | None = Field(default=None, alias="sortOrder")
    duration_minutes: int | None = Field(default=None, alias="durationMinutes", ge=0)
    notes: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(populate_by_name=True)


class ItineraryDayUpdateRequest(BaseModel):
    """更新单日行程请求。"""

    transportation: str | None = Field(default=None, max_length=200)
    accommodation: str | None = Field(default=None, max_length=300)
    meal_breakfast: str | None = Field(default=None, alias="mealBreakfast", max_length=200)
    meal_lunch: str | None = Field(default=None, alias="mealLunch", max_length=200)
    meal_dinner: str | None = Field(default=None, alias="mealDinner", max_length=200)
    budget_day: Decimal | None = Field(default=None, alias="budgetDay", ge=0)
    notes: str | None = Field(default=None, max_length=2000)
    spots: list[ItinerarySpotRequest] | None = None

    model_config = ConfigDict(populate_by_name=True)


class ItinerarySpotResponse(BaseModel):
    """每日景点 / 打卡点响应。"""

    uuid: str
    name: str
    address: str | None = None
    category: int
    sort_order: int = Field(alias="sortOrder")
    duration_minutes: int | None = Field(default=None, alias="durationMinutes")
    notes: str | None = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ItineraryDayResponse(BaseModel):
    """每日行程响应。"""

    uuid: str
    day_date: date = Field(alias="dayDate")
    day_index: int = Field(alias="dayIndex")
    transportation: str | None = None
    accommodation: str | None = None
    meal_breakfast: str | None = Field(default=None, alias="mealBreakfast")
    meal_lunch: str | None = Field(default=None, alias="mealLunch")
    meal_dinner: str | None = Field(default=None, alias="mealDinner")
    budget_day: Decimal | None = Field(default=None, alias="budgetDay")
    notes: str | None = None
    spots: list[ItinerarySpotResponse] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
