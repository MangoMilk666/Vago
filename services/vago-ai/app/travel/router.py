"""Trip / Plan / Itinerary API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.shared.responses import ApiResponse, success
from app.travel import service
from app.travel.models import ItineraryDay
from app.travel.schemas import (
    ItineraryDayResponse,
    ItineraryDayUpdateRequest,
    PlanCreateRequest,
    PlanResponse,
    PlanUpdateRequest,
    TripCreateRequest,
    TripResponse,
    TripUpdateRequest,
)

router = APIRouter()


@router.post("/trips", response_model=ApiResponse[TripResponse])
def create_trip(
    payload: TripCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TripResponse]:
    """创建正式行程。"""
    return success(service.create_trip(db, user_uuid, payload), "行程创建成功")


@router.get("/trips", response_model=ApiResponse[list[TripResponse]])
def list_trips(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[TripResponse]]:
    """获取当前用户全部行程。"""
    return success(service.list_trips(db, user_uuid))


@router.get("/trips/history", response_model=ApiResponse[list[TripResponse]])
def list_history_trips(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[TripResponse]]:
    """获取当前用户历史行程。"""
    return success(service.list_history_trips(db, user_uuid))


@router.get("/trips/{trip_uuid}", response_model=ApiResponse[TripResponse])
def get_trip_detail(
    trip_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TripResponse]:
    """获取行程详情。"""
    return success(service.get_trip_detail(db, user_uuid, trip_uuid))


@router.put("/trips/{trip_uuid}", response_model=ApiResponse[TripResponse])
def update_trip(
    trip_uuid: str,
    payload: TripUpdateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TripResponse]:
    """更新行程。"""
    return success(service.update_trip(db, user_uuid, trip_uuid, payload), "行程更新成功")


@router.delete("/trips/{trip_uuid}", response_model=ApiResponse[None])
def delete_trip(
    trip_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[None]:
    """软删除行程。"""
    service.delete_trip(db, user_uuid, trip_uuid)
    return success(None, "行程删除成功")


@router.post("/plans", response_model=ApiResponse[PlanResponse])
def create_plan(
    payload: PlanCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[PlanResponse]:
    """创建旅行计划草稿。"""
    return success(service.create_plan(db, user_uuid, payload), "计划创建成功")


@router.get("/plans", response_model=ApiResponse[list[PlanResponse]])
def list_plans(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[PlanResponse]]:
    """获取当前用户全部计划。"""
    return success(service.list_plans(db, user_uuid))


@router.get("/plans/{plan_uuid}", response_model=ApiResponse[PlanResponse])
def get_plan_detail(
    plan_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[PlanResponse]:
    """获取计划详情。"""
    return success(service.get_plan_detail(db, user_uuid, plan_uuid))


@router.put("/plans/{plan_uuid}", response_model=ApiResponse[PlanResponse])
def update_plan(
    plan_uuid: str,
    payload: PlanUpdateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[PlanResponse]:
    """更新计划。"""
    return success(service.update_plan(db, user_uuid, plan_uuid, payload), "计划更新成功")


@router.delete("/plans/{plan_uuid}", response_model=ApiResponse[None])
def delete_plan(
    plan_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[None]:
    """软删除计划。"""
    service.delete_plan(db, user_uuid, plan_uuid)
    return success(None, "计划删除成功")


@router.post("/plans/{plan_uuid}/convert", response_model=ApiResponse[TripResponse])
def convert_plan_to_trip(
    plan_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TripResponse]:
    """将计划转为正式行程。"""
    return success(service.convert_plan_to_trip(db, user_uuid, plan_uuid), "计划已转为正式行程")


@router.get("/trips/{trip_uuid}/days", response_model=ApiResponse[list[ItineraryDayResponse]])
def get_trip_days(
    trip_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[ItineraryDayResponse]]:
    """获取正式行程的每日安排。"""
    return success(service.get_itinerary_days(db, user_uuid, trip_uuid, ItineraryDay.REF_TYPE_TRIP))


@router.put("/trips/{trip_uuid}/days/{dayIndex}", response_model=ApiResponse[ItineraryDayResponse])
def update_trip_day(
    trip_uuid: str,
    dayIndex: int,
    payload: ItineraryDayUpdateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ItineraryDayResponse]:
    """更新正式行程的单日安排。"""
    return success(
        service.update_itinerary_day(
            db,
            user_uuid,
            trip_uuid,
            ItineraryDay.REF_TYPE_TRIP,
            dayIndex,
            payload,
        ),
        "每日行程更新成功",
    )


@router.get("/plans/{plan_uuid}/days", response_model=ApiResponse[list[ItineraryDayResponse]])
def get_plan_days(
    plan_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[ItineraryDayResponse]]:
    """获取旅行计划的每日安排。"""
    return success(service.get_itinerary_days(db, user_uuid, plan_uuid, ItineraryDay.REF_TYPE_PLAN))


@router.put("/plans/{plan_uuid}/days/{dayIndex}", response_model=ApiResponse[ItineraryDayResponse])
def update_plan_day(
    plan_uuid: str,
    dayIndex: int,
    payload: ItineraryDayUpdateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ItineraryDayResponse]:
    """更新旅行计划的单日安排。"""
    return success(
        service.update_itinerary_day(
            db,
            user_uuid,
            plan_uuid,
            ItineraryDay.REF_TYPE_PLAN,
            dayIndex,
            payload,
        ),
        "每日行程更新成功",
    )
