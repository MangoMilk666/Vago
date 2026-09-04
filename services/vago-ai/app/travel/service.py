"""Trip / Plan / Itinerary 领域服务。"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.schemas import AiPlanSaveResponse, StructuredDay, StructuredPlan
from app.travel.models import ItineraryDay, ItinerarySpot, Plan, Trip, utc_now_naive
from app.travel.schemas import (
    ItineraryDayResponse,
    ItineraryDayUpdateRequest,
    ItinerarySpotResponse,
    PlanCreateRequest,
    PlanResponse,
    PlanUpdateRequest,
    TripCreateRequest,
    TripResponse,
    TripUpdateRequest,
)

# 未开始
TRIP_STATUS_NOT_STARTED = 1
# 进行中
TRIP_STATUS_IN_PROGRESS = 2
# 已结束
TRIP_STATUS_ENDED = 3
PLAN_STATUS_DRAFT = 0
PLAN_STATUS_CONVERTED = 1


def _parse_optional_date(value: str | None) -> date | None:
    """解析 AI structured plan 中的日期字符串，非法或为空时按旧 Java 行为返回 None。"""
    # 分支条件：AI 没有返回日期时，交由调用方决定 fallback 策略。
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _new_uuid() -> str:
    """生成与 Java IdUtil.fastSimpleUUID 兼容的 32 位业务 ID。"""
    return uuid4().hex


def _date_range(start: date, end: date) -> list[date]:
    """返回闭区间 [start, end] 的所有日期。"""
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current = current + timedelta(days=1)
    return days


def _ensure_trip_owner(trip: Trip, user_uuid: str) -> None:
    """校验 Trip 归属当前用户。"""
    # 分支条件：行程归属用户与当前 JWT 用户不一致时，拒绝访问。
    if trip.user_uuid != user_uuid:
        raise AppException("无权访问该行程", status_code=403, code="FORBIDDEN")


def _ensure_plan_owner(plan: Plan, user_uuid: str) -> None:
    """校验 Plan 归属当前用户。"""
    # 分支条件：计划归属用户与当前 JWT 用户不一致时，拒绝访问。
    if plan.user_uuid != user_uuid:
        raise AppException("无权访问该计划", status_code=403, code="FORBIDDEN")


def _get_trip_or_raise(db: Session, trip_uuid: str, user_uuid: str | None = None) -> Trip:
    """读取未删除 Trip，不存在时返回业务错误。"""
    trip = db.scalar(select(Trip).where(Trip.uuid == trip_uuid, Trip.deleted_at.is_(None)))
    # 分支条件：行程不存在或已软删除时，返回行程不存在。
    if trip is None:
        raise AppException("行程不存在", status_code=404, code="TRIP_NOT_FOUND")
    # 分支条件：调用方要求校验归属时，进一步检查当前用户。
    if user_uuid is not None:
        _ensure_trip_owner(trip, user_uuid)
    return trip


def _get_plan_or_raise(db: Session, plan_uuid: str, user_uuid: str | None = None) -> Plan:
    """读取未删除 Plan，不存在时返回业务错误。"""
    plan = db.scalar(select(Plan).where(Plan.uuid == plan_uuid, Plan.deleted_at.is_(None)))
    # 分支条件：计划不存在或已软删除时，返回计划不存在。
    if plan is None:
        raise AppException("计划不存在", status_code=404, code="PLAN_NOT_FOUND")
    # 分支条件：调用方要求校验归属时，进一步检查当前用户。
    if user_uuid is not None:
        _ensure_plan_owner(plan, user_uuid)
    return plan


def _trip_to_response(trip: Trip) -> TripResponse:
    """Trip ORM -> API response。"""
    return TripResponse.model_validate(trip)


def _ensure_trip_editable(trip: Trip) -> None:
    """已结束行程仅供回顾，禁止再修改其业务数据。"""
    # 分支条件：历史行程已结束时，拒绝修改、删除及每日安排编辑。
    if trip.status == TRIP_STATUS_ENDED:
        raise AppException("已结束的历史行程不允许修改", status_code=409, code="TRIP_ENDED")


def _plan_to_response(plan: Plan) -> PlanResponse:
    """Plan ORM -> API response。"""
    return PlanResponse.model_validate(plan)


def create_trip(db: Session, user_uuid: str, payload: TripCreateRequest) -> TripResponse:
    """创建正式行程。"""
    trip = Trip(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        title=payload.title,
        destination=payload.destination,
        cover_image_key=payload.cover_image_key,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=TRIP_STATUS_NOT_STARTED,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return _trip_to_response(trip)


def list_trips(db: Session, user_uuid: str) -> list[TripResponse]:
    """列出当前用户全部未删除行程。"""
    trips = db.scalars(
        select(Trip)
        .where(Trip.user_uuid == user_uuid, Trip.deleted_at.is_(None))
        .order_by(Trip.created_at.desc())
    ).all()
    # 最终返回列表
    return [_trip_to_response(trip) for trip in trips]


def list_history_trips(db: Session, user_uuid: str) -> list[TripResponse]:
    """列出当前用户已结束的历史行程。"""
    trips = db.scalars(
        select(Trip)
        .where(
            Trip.user_uuid == user_uuid,
            Trip.status == TRIP_STATUS_ENDED,
            Trip.deleted_at.is_(None),
        )
        .order_by(Trip.end_date.desc())
    ).all()
    return [_trip_to_response(trip) for trip in trips]


def get_trip_detail(db: Session, user_uuid: str, trip_uuid: str) -> TripResponse:
    """读取行程详情。"""
    return _trip_to_response(_get_trip_or_raise(db, trip_uuid, user_uuid))


def update_trip(
    db: Session,
    user_uuid: str,
    trip_uuid: str,
    payload: TripUpdateRequest,
) -> TripResponse:
    """局部更新行程。"""
    trip = _get_trip_or_raise(db, trip_uuid, user_uuid)
    _ensure_trip_editable(trip)
    values = payload.model_dump(exclude_unset=True, by_alias=False)
    for field_name, value in values.items():
        setattr(trip, field_name, value)
    trip.updated_at = utc_now_naive()
    db.commit()
    db.refresh(trip)
    return _trip_to_response(trip)


def delete_trip(db: Session, user_uuid: str, trip_uuid: str) -> None:
    """软删除行程。"""
    trip = _get_trip_or_raise(db, trip_uuid, user_uuid)
    _ensure_trip_editable(trip)
    now = utc_now_naive()
    trip.deleted_at = now
    trip.updated_at = now
    db.commit()


def start_trip(db: Session, user_uuid: str, trip_uuid: str) -> TripResponse:
    """开始未开始的行程；每位用户同一时间最多只能进行一个行程。"""
    trip = _get_trip_or_raise(db, trip_uuid, user_uuid)
    # 分支条件：仅未开始行程可以切换到进行中，避免重复开始或重开历史行程。
    if trip.status != TRIP_STATUS_NOT_STARTED:
        raise AppException("仅未开始的行程可以开始", status_code=409, code="TRIP_NOT_STARTABLE")

    active_trip = db.scalar(
        select(Trip).where(
            Trip.user_uuid == user_uuid,
            Trip.status == TRIP_STATUS_IN_PROGRESS,
            Trip.deleted_at.is_(None),
        )
    )
    # 分支条件：已有进行中行程时，要求用户先结束该行程，保证当前旅行上下文唯一。
    if active_trip is not None:
        raise AppException(
            f"当前已有进行中的行程「{active_trip.title}」",
            status_code=409,
            code="TRIP_ALREADY_IN_PROGRESS",
        )

    trip.status = TRIP_STATUS_IN_PROGRESS
    trip.updated_at = utc_now_naive()
    db.commit()
    db.refresh(trip)
    return _trip_to_response(trip)


def finish_trip(db: Session, user_uuid: str, trip_uuid: str) -> TripResponse:
    """结束进行中的行程，并将其归入历史行程。"""
    trip = _get_trip_or_raise(db, trip_uuid, user_uuid)
    # 分支条件：未开始或已结束行程不能直接结束，避免产生无效历史记录。
    if trip.status != TRIP_STATUS_IN_PROGRESS:
        raise AppException("仅进行中的行程可以结束", status_code=409, code="TRIP_NOT_FINISHABLE")

    trip.status = TRIP_STATUS_ENDED
    trip.updated_at = utc_now_naive()
    db.commit()
    db.refresh(trip)
    return _trip_to_response(trip)


def create_plan(db: Session, user_uuid: str, payload: PlanCreateRequest) -> PlanResponse:
    """创建旅行计划草稿。"""
    plan = Plan(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        title=payload.title,
        destination=payload.destination,
        start_date=payload.start_date,
        end_date=payload.end_date,
        budget=payload.budget,
        budget_currency=payload.budget_currency or "CNY",
        notes=payload.notes,
        status=PLAN_STATUS_DRAFT,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _plan_to_response(plan)


def list_plans(db: Session, user_uuid: str) -> list[PlanResponse]:
    """列出当前用户全部未删除计划。"""
    plans = db.scalars(
        select(Plan)
        .where(Plan.user_uuid == user_uuid, Plan.deleted_at.is_(None))
        .order_by(Plan.created_at.desc())
    ).all()
    return [_plan_to_response(plan) for plan in plans]


def get_plan_detail(db: Session, user_uuid: str, plan_uuid: str) -> PlanResponse:
    """读取计划详情。"""
    return _plan_to_response(_get_plan_or_raise(db, plan_uuid, user_uuid))


def update_plan(
    db: Session,
    user_uuid: str,
    plan_uuid: str,
    payload: PlanUpdateRequest,
) -> PlanResponse:
    """局部更新计划。"""
    plan = _get_plan_or_raise(db, plan_uuid, user_uuid)
    values = payload.model_dump(exclude_unset=True, by_alias=False)
    for field_name, value in values.items():
        setattr(plan, field_name, value)
    plan.updated_at = utc_now_naive()
    db.commit()
    db.refresh(plan)
    return _plan_to_response(plan)


def delete_plan(db: Session, user_uuid: str, plan_uuid: str) -> None:
    """软删除计划。"""
    plan = _get_plan_or_raise(db, plan_uuid, user_uuid)
    now = utc_now_naive()
    plan.deleted_at = now
    plan.updated_at = now
    db.commit()


def convert_plan_to_trip(db: Session, user_uuid: str, plan_uuid: str) -> TripResponse:
    """将计划转换为正式行程，并复制已有每日行程。"""
    plan = _get_plan_or_raise(db, plan_uuid, user_uuid)
    # 分支条件：已转换计划不允许重复转换。
    if plan.status == PLAN_STATUS_CONVERTED:
        raise AppException("计划已转换为正式行程", status_code=409, code="PLAN_ALREADY_CONVERTED")
    # 分支条件：计划缺少日期时，无法创建需要起止日期的正式行程。
    if plan.start_date is None or plan.end_date is None:
        raise AppException("计划缺少出行日期，无法转为行程", status_code=400, code="PLAN_DATE_REQUIRED")

    trip = Trip(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        title=plan.title,
        destination=plan.destination,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=TRIP_STATUS_NOT_STARTED,
    )
    db.add(trip)
    db.flush()

    # 计划状态更新为已转换，绑定转换的行程uuid
    plan.status = PLAN_STATUS_CONVERTED
    plan.converted_trip_uuid = trip.uuid
    plan.updated_at = utc_now_naive()
    _copy_days_from_plan_to_trip(db, plan.uuid, trip.uuid)

    db.commit()
    db.refresh(trip)
    return _trip_to_response(trip)


def save_structured_plan_as_draft(
    db: Session,
    user_uuid: str,
    payload: StructuredPlan,
) -> AiPlanSaveResponse:
    """将 AI 结构化行程保存为 Plan 草稿，并创建对应 days/spots。"""
    start_date = _parse_optional_date(payload.start_date) or date.today()
    end_date = _parse_optional_date(payload.end_date) or start_date + timedelta(days=len(payload.days) - 1)
    plan = Plan(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        title=payload.title,
        destination=payload.destination,
        start_date=start_date,
        end_date=end_date,
        budget=payload.budget,
        budget_currency=payload.budget_currency or "CNY",
        status=PLAN_STATUS_DRAFT,
    )
    db.add(plan)
    db.flush()
    _create_days_and_spots_from_structured(db, plan.uuid, ItineraryDay.REF_TYPE_PLAN, payload.days, start_date)
    db.commit()
    return AiPlanSaveResponse(uuid=plan.uuid, type="plan")


def save_structured_plan_as_trip(
    db: Session,
    user_uuid: str,
    payload: StructuredPlan,
) -> AiPlanSaveResponse:
    """将 AI 结构化行程保存为正式 Trip，并创建对应 days/spots。"""
    start_date = _parse_optional_date(payload.start_date)
    end_date = _parse_optional_date(payload.end_date)
    # 分支条件：正式行程必须具备起止日期，缺失或格式非法时拒绝保存。
    if start_date is None or end_date is None:
        raise AppException("正式行程必须包含出发日期和返回日期", status_code=400, code="PARAM_INVALID")

    trip = Trip(
        uuid=_new_uuid(),
        user_uuid=user_uuid,
        title=payload.title,
        destination=payload.destination,
        start_date=start_date,
        end_date=end_date,
        status=TRIP_STATUS_NOT_STARTED,
    )
    db.add(trip)
    db.flush()
    _create_days_and_spots_from_structured(db, trip.uuid, ItineraryDay.REF_TYPE_TRIP, payload.days, start_date)
    db.commit()
    return AiPlanSaveResponse(uuid=trip.uuid, type="trip")


def _create_days_and_spots_from_structured(
    db: Session,
    ref_uuid: str,
    ref_type: int,
    days: list[StructuredDay],
    base_start_date: date,
) -> None:
    """把 AI structured plan 的 days/spots 批量写入 itinerary 表。"""
    for day_payload in days:
        day_date = _parse_optional_date(day_payload.day_date)
        # 分支条件：AI 未给出某天具体日期时，用起始日期 + dayIndex 推导。
        if day_date is None:
            day_date = base_start_date + timedelta(days=day_payload.day_index - 1)

        day = ItineraryDay(
            uuid=_new_uuid(),
            ref_uuid=ref_uuid,
            ref_type=ref_type,
            day_date=day_date,
            day_index=day_payload.day_index,
            transportation=day_payload.transportation,
            accommodation=day_payload.accommodation,
            meal_breakfast=day_payload.meal_breakfast,
            meal_lunch=day_payload.meal_lunch,
            meal_dinner=day_payload.meal_dinner,
            budget_day=day_payload.budget_day,
            notes=day_payload.notes,
        )
        db.add(day)
        db.flush()

        for index, spot_payload in enumerate(day_payload.spots):
            db.add(
                ItinerarySpot(
                    uuid=_new_uuid(),
                    day_uuid=day.uuid,
                    name=spot_payload.name,
                    address=spot_payload.address,
                    category=spot_payload.category,
                    sort_order=index,
                    duration_minutes=spot_payload.duration_minutes,
                    notes=spot_payload.notes,
                )
            )


def _resolve_date_range(db: Session, ref_uuid: str, ref_type: int, user_uuid: str) -> list[date] | None:
    """解析行程或计划的日期区间。"""
    # 分支条件：ref_type 为 Trip 时，从 trips 表读取日期范围并校验归属。
    if ref_type == ItineraryDay.REF_TYPE_TRIP:
        trip = _get_trip_or_raise(db, ref_uuid, user_uuid)
        return _date_range(trip.start_date, trip.end_date)

    plan = _get_plan_or_raise(db, ref_uuid, user_uuid)
    # 分支条件：计划还没有起止日期时，按 Java 行为返回空日程。
    if plan.start_date is None or plan.end_date is None:
        return None
    return _date_range(plan.start_date, plan.end_date)


def _create_empty_day(db: Session, ref_uuid: str, ref_type: int, day_date: date, day_index: int) -> ItineraryDay:
    """创建空的每日行程记录。"""
    day = ItineraryDay(
        uuid=_new_uuid(),
        ref_uuid=ref_uuid,
        ref_type=ref_type,
        day_date=day_date,
        day_index=day_index,
    )
    db.add(day)
    db.flush()
    return day


def _spot_to_response(spot: ItinerarySpot) -> ItinerarySpotResponse:
    """ItinerarySpot ORM -> API response。"""
    return ItinerarySpotResponse.model_validate(spot)


def _day_to_response(day: ItineraryDay, spots: Iterable[ItinerarySpot]) -> ItineraryDayResponse:
    """ItineraryDay ORM + spots -> API response。"""
    return ItineraryDayResponse(
        uuid=day.uuid,
        dayDate=day.day_date,
        dayIndex=day.day_index,
        transportation=day.transportation,
        accommodation=day.accommodation,
        mealBreakfast=day.meal_breakfast,
        mealLunch=day.meal_lunch,
        mealDinner=day.meal_dinner,
        budgetDay=day.budget_day,
        notes=day.notes,
        spots=[_spot_to_response(spot) for spot in spots],
    )


def get_itinerary_days(
    db: Session,
    user_uuid: str,
    ref_uuid: str,
    ref_type: int,
) -> list[ItineraryDayResponse]:
    """读取行程/计划的每日安排；缺失日期会懒初始化空记录。"""
    dates = _resolve_date_range(db, ref_uuid, ref_type, user_uuid)
    # 分支条件：计划未填写日期时，返回空列表。
    if dates is None:
        return []

    existing_days = db.scalars(
        select(ItineraryDay)
        .where(ItineraryDay.ref_uuid == ref_uuid, ItineraryDay.ref_type == ref_type)
        .order_by(ItineraryDay.day_index.asc(), ItineraryDay.id.asc())
    ).all()
    days_by_date: dict[date, list[ItineraryDay]] = defaultdict(list)
    for day in existing_days:
        days_by_date[day.day_date].append(day)

    all_days: list[ItineraryDay] = []
    for index, day_date in enumerate(dates, start=1):
        days_for_date = days_by_date.get(day_date, [])
        # 分支条件：某日期没有 day 记录时，懒初始化一条空 day。
        if not days_for_date:
            all_days.append(_create_empty_day(db, ref_uuid, ref_type, day_date, index))
        else:
            # 分支条件：某日期已有 day 记录时，复用现有记录并检查 dayIndex。
            for day in days_for_date:
                # 分支条件：日期区间变化导致 dayIndex 不一致时，自动修正。
                if day.day_index != index:
                    day.day_index = index
                    day.updated_at = utc_now_naive()
            all_days.extend(days_for_date)

    db.flush()
    spots = db.scalars(
        select(ItinerarySpot)
        .join(ItineraryDay, ItinerarySpot.day_uuid == ItineraryDay.uuid)
        .where(ItineraryDay.ref_uuid == ref_uuid, ItineraryDay.ref_type == ref_type)
        .order_by(ItineraryDay.day_index.asc(), ItinerarySpot.sort_order.asc(), ItinerarySpot.id.asc())
    ).all()
    spots_by_day: dict[str, list[ItinerarySpot]] = defaultdict(list)
    for spot in spots:
        spots_by_day[spot.day_uuid].append(spot)

    db.commit()
    return [_day_to_response(day, spots_by_day.get(day.uuid, [])) for day in all_days]


def update_itinerary_day(
    db: Session,
    user_uuid: str,
    ref_uuid: str,
    ref_type: int,
    day_index: int,
    payload: ItineraryDayUpdateRequest,
) -> ItineraryDayResponse:
    """更新单日行程；spots 不为 None 时采用全量替换策略。"""
    get_itinerary_days(db, user_uuid, ref_uuid, ref_type)
    # 分支条件：正式行程已结束时，日程仅供回顾，不允许继续编辑。
    if ref_type == ItineraryDay.REF_TYPE_TRIP:
        _ensure_trip_editable(_get_trip_or_raise(db, ref_uuid, user_uuid))

    day = db.scalar(
        select(ItineraryDay).where(
            ItineraryDay.ref_uuid == ref_uuid,
            ItineraryDay.ref_type == ref_type,
            ItineraryDay.day_index == day_index,
        )
    )
    # 分支条件：指定 dayIndex 不在日期范围内时，返回资源不存在。
    if day is None:
        raise AppException("每日行程不存在", status_code=404, code="ITINERARY_DAY_NOT_FOUND")

    values = payload.model_dump(exclude_unset=True, exclude={"spots"}, by_alias=False)
    for field_name, value in values.items():
        setattr(day, field_name, value)
    day.updated_at = utc_now_naive()

    saved_spots: list[ItinerarySpot]
    # 分支条件：spots 字段传入时，按 Java 行为全量替换当日景点。
    if payload.spots is not None:
        db.execute(delete(ItinerarySpot).where(ItinerarySpot.day_uuid == day.uuid))
        saved_spots = []
        for index, spot_payload in enumerate(payload.spots):
            spot = ItinerarySpot(
                uuid=_new_uuid(),
                day_uuid=day.uuid,
                name=spot_payload.name,
                address=spot_payload.address,
                category=spot_payload.category if spot_payload.category is not None else 0,
                sort_order=index,
                duration_minutes=spot_payload.duration_minutes,
                notes=spot_payload.notes,
            )
            db.add(spot)
            saved_spots.append(spot)
        db.flush()
    else:
        # 分支条件：spots 字段未传入时，保留当日已有景点。
        saved_spots = db.scalars(
            select(ItinerarySpot)
            .where(ItinerarySpot.day_uuid == day.uuid)
            .order_by(ItinerarySpot.sort_order.asc(), ItinerarySpot.id.asc())
        ).all()

    db.commit()
    db.refresh(day)
    return _day_to_response(day, saved_spots)


def _copy_days_from_plan_to_trip(db: Session, plan_uuid: str, trip_uuid: str) -> None:
    """计划转行程时复制每日安排和景点。"""
    plan_days = db.scalars(
        select(ItineraryDay)
        .where(ItineraryDay.ref_uuid == plan_uuid, ItineraryDay.ref_type == ItineraryDay.REF_TYPE_PLAN)
        .order_by(ItineraryDay.day_index.asc(), ItineraryDay.id.asc())
    ).all()
    # 分支条件：计划没有任何日程记录时，无需复制。
    if not plan_days:
        return

    for plan_day in plan_days:
        trip_day = ItineraryDay(
            uuid=_new_uuid(),
            ref_uuid=trip_uuid,
            ref_type=ItineraryDay.REF_TYPE_TRIP,
            day_date=plan_day.day_date,
            day_index=plan_day.day_index,
            transportation=plan_day.transportation,
            accommodation=plan_day.accommodation,
            meal_breakfast=plan_day.meal_breakfast,
            meal_lunch=plan_day.meal_lunch,
            meal_dinner=plan_day.meal_dinner,
            budget_day=plan_day.budget_day,
            notes=plan_day.notes,
        )
        db.add(trip_day)
        db.flush()

        plan_spots = db.scalars(
            select(ItinerarySpot)
            .where(ItinerarySpot.day_uuid == plan_day.uuid)
            .order_by(ItinerarySpot.sort_order.asc(), ItinerarySpot.id.asc())
        ).all()
        for plan_spot in plan_spots:
            db.add(
                ItinerarySpot(
                    uuid=_new_uuid(),
                    day_uuid=trip_day.uuid,
                    name=plan_spot.name,
                    address=plan_spot.address,
                    category=plan_spot.category,
                    sort_order=plan_spot.sort_order,
                    duration_minutes=plan_spot.duration_minutes,
                    notes=plan_spot.notes,
                )
            )
