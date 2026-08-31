"""Trip / Plan / Itinerary 的请求与响应 schema。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TripCreateRequest(BaseModel):
    """创建正式行程请求。"""

    # 行程标题。
    title: str = Field(min_length=1, max_length=100)
    # 行程目的地。
    destination: str | None = Field(default=None, max_length=200)
    # 行程开始日期。
    start_date: date = Field(alias="startDate")
    # 行程结束日期。
    end_date: date = Field(alias="endDate")
    # 封面图对象存储 key。
    cover_image_key: str | None = Field(default=None, alias="coverImageKey")

    model_config = ConfigDict(populate_by_name=True)


class TripUpdateRequest(BaseModel):
    """更新正式行程请求；None 表示不更新该字段。"""

    # 新行程标题；未传表示不修改。
    title: str | None = Field(default=None, max_length=100)
    # 新行程目的地；未传表示不修改。
    destination: str | None = Field(default=None, max_length=200)
    # 新行程开始日期；未传表示不修改。
    start_date: date | None = Field(default=None, alias="startDate")
    # 新行程结束日期；未传表示不修改。
    end_date: date | None = Field(default=None, alias="endDate")
    # 新封面图对象存储 key；未传表示不修改。
    cover_image_key: str | None = Field(default=None, alias="coverImageKey")
    # 新行程状态；未传表示不修改。
    status: int | None = Field(default=None, ge=1, le=3)

    model_config = ConfigDict(populate_by_name=True)


class TripResponse(BaseModel):
    """正式行程响应。"""

    # 行程业务 UUID。
    uuid: str
    # 行程标题。
    title: str
    # 行程目的地。
    destination: str | None = None
    # 封面图对象存储 key。
    cover_image_key: str | None = Field(default=None, alias="coverImageKey")
    # 行程开始日期。
    start_date: date = Field(alias="startDate")
    # 行程结束日期。
    end_date: date = Field(alias="endDate")
    # 行程状态。
    status: int
    # 行程创建时间。
    created_at: datetime = Field(alias="createdAt")
    # 行程最近更新时间。
    updated_at: datetime = Field(alias="updatedAt")
    # 允许字段名兼容；允许从整个对象的属性中取值
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PlanCreateRequest(BaseModel):
    """创建旅行计划草稿请求。"""

    # 计划标题。
    title: str = Field(min_length=1, max_length=100)
    # 计划目的地。
    destination: str | None = Field(default=None, max_length=200)
    # 计划开始日期；草稿阶段可为空。
    start_date: date | None = Field(default=None, alias="startDate")
    # 计划结束日期；草稿阶段可为空。
    end_date: date | None = Field(default=None, alias="endDate")
    # 计划总预算。
    budget: Decimal | None = Field(default=None, ge=0)
    # 预算货币代码；为空时服务端默认 CNY。
    budget_currency: str | None = Field(default=None, alias="budgetCurrency", max_length=3)
    # 计划备注。
    notes: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


class PlanUpdateRequest(BaseModel):
    """更新旅行计划草稿请求。"""

    # 新计划标题；未传表示不修改。
    title: str | None = Field(default=None, max_length=100)
    # 新计划目的地；未传表示不修改。
    destination: str | None = Field(default=None, max_length=200)
    # 新计划开始日期；未传表示不修改。
    start_date: date | None = Field(default=None, alias="startDate")
    # 新计划结束日期；未传表示不修改。
    end_date: date | None = Field(default=None, alias="endDate")
    # 新计划总预算；未传表示不修改。
    budget: Decimal | None = Field(default=None, ge=0)
    # 新预算货币代码；未传表示不修改。
    budget_currency: str | None = Field(default=None, alias="budgetCurrency", max_length=3)
    # 新计划备注；未传表示不修改。
    notes: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


class PlanResponse(BaseModel):
    """旅行计划草稿响应。"""

    # 计划业务 UUID。
    uuid: str
    # 计划标题。
    title: str
    # 计划目的地。
    destination: str | None = None
    # 计划开始日期。
    start_date: date | None = Field(default=None, alias="startDate")
    # 计划结束日期。
    end_date: date | None = Field(default=None, alias="endDate")
    # 计划总预算。
    budget: Decimal | None = None
    # 预算货币代码。
    budget_currency: str = Field(alias="budgetCurrency")
    # 计划备注。
    notes: str | None = None
    # 计划转换后的正式 Trip UUID。
    converted_trip_uuid: str | None = Field(default=None, alias="convertedTripUuid")
    # 计划状态。
    status: int
    # 计划创建时间。
    created_at: datetime = Field(alias="createdAt")
    # 计划最近更新时间。
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ItinerarySpotRequest(BaseModel):
    """每日景点 / 打卡点请求。"""

    # 客户端传入的景点 UUID；当前替换策略下仅作兼容保留。
    uuid: str | None = None
    # 景点或活动名称。
    name: str = Field(min_length=1, max_length=100)
    # 景点或活动地址。
    address: str | None = Field(default=None, max_length=300)
    # 类型分类，0=景点，1=餐厅，2=购物，3=娱乐，4=中转，5=其他。
    category: int | None = Field(default=None, ge=0, le=5)
    # 客户端排序序号；服务端当前按列表顺序重建。
    sort_order: int | None = Field(default=None, alias="sortOrder")
    # 预计停留时长，单位为分钟。
    duration_minutes: int | None = Field(default=None, alias="durationMinutes", ge=0)
    # 景点或活动备注。
    notes: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(populate_by_name=True)


class ItineraryDayUpdateRequest(BaseModel):
    """更新单日行程请求。"""

    # 当日交通安排；未传表示不修改。
    transportation: str | None = Field(default=None, max_length=200)
    # 当日住宿安排；未传表示不修改。
    accommodation: str | None = Field(default=None, max_length=300)
    # 当日早餐安排；未传表示不修改。
    meal_breakfast: str | None = Field(default=None, alias="mealBreakfast", max_length=200)
    # 当日午餐安排；未传表示不修改。
    meal_lunch: str | None = Field(default=None, alias="mealLunch", max_length=200)
    # 当日晚餐安排；未传表示不修改。
    meal_dinner: str | None = Field(default=None, alias="mealDinner", max_length=200)
    # 当日预算；未传表示不修改。
    budget_day: Decimal | None = Field(default=None, alias="budgetDay", ge=0)
    # 当日备注；未传表示不修改。
    notes: str | None = Field(default=None, max_length=2000)
    # 当日景点列表；传入时全量替换，未传时保留原列表。
    spots: list[ItinerarySpotRequest] | None = None

    model_config = ConfigDict(populate_by_name=True)


class ItinerarySpotResponse(BaseModel):
    """每日景点 / 打卡点响应。"""

    # 景点/活动业务 UUID。
    uuid: str
    # 景点或活动名称。
    name: str
    # 景点或活动地址。
    address: str | None = None
    # 类型分类。
    category: int
    # 当日排序序号。
    sort_order: int = Field(alias="sortOrder")
    # 预计停留时长，单位为分钟。
    duration_minutes: int | None = Field(default=None, alias="durationMinutes")
    # 景点或活动备注。
    notes: str | None = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ItineraryDayResponse(BaseModel):
    """每日行程响应。"""

    # 每日行程业务 UUID。
    uuid: str
    # 当日日期。
    day_date: date = Field(alias="dayDate")
    # 第几天，1-based。
    day_index: int = Field(alias="dayIndex")
    # 当日交通安排。
    transportation: str | None = None
    # 当日住宿安排。
    accommodation: str | None = None
    # 当日早餐安排。
    meal_breakfast: str | None = Field(default=None, alias="mealBreakfast")
    # 当日午餐安排。
    meal_lunch: str | None = Field(default=None, alias="mealLunch")
    # 当日晚餐安排。
    meal_dinner: str | None = Field(default=None, alias="mealDinner")
    # 当日预算。
    budget_day: Decimal | None = Field(default=None, alias="budgetDay")
    # 当日备注。
    notes: str | None = None
    # 当日景点/活动列表。
    spots: list[ItinerarySpotResponse] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
