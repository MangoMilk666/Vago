"""Grounded Travel Memory HTTP API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.memory import service
from app.memory.schemas import TravelMemoryResponse, TravelMemoryUpdateRequest
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.get("", response_model=ApiResponse[list[TravelMemoryResponse]])
def list_travel_memories(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[TravelMemoryResponse]]:
    """列出当前用户已建立的事实回忆。"""
    return success(service.list_memories(db, user_uuid))


@router.post("/trips/{trip_uuid}/refresh-facts", response_model=ApiResponse[TravelMemoryResponse])
def refresh_trip_memory(
    trip_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TravelMemoryResponse]:
    """从已结束行程刷新 Travel Memory 的事实快照。"""
    return success(service.refresh_trip_memory(db, user_uuid, trip_uuid), "旅行回忆事实已刷新")


@router.patch("/{memory_uuid}", response_model=ApiResponse[TravelMemoryResponse])
def update_travel_memory(
    memory_uuid: str,
    payload: TravelMemoryUpdateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[TravelMemoryResponse]:
    """编辑回忆标题或叙事，不修改事实快照。"""
    return success(service.update_memory(db, user_uuid, memory_uuid, payload), "旅行回忆已更新")
