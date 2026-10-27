"""会话内规划候选的创建、列表、回读与状态查询。"""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.plan_proposals import service
from app.plan_proposals.schemas import ProposalCreateRequest, ProposalDetail, ProposalStatus, ProposalSummary
from app.plan_proposals.providers import (
    PlaceSearchRequest, RouteSearchRequest, enforce_provider_quota, search_places, search_routes,
)
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.post("/planning/places/search", response_model=ApiResponse[list[dict]])
async def search_planning_places(
    payload: PlaceSearchRequest,
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[dict]]:
    """由服务端按地区查询规划地点，认证身份只用于授权入口。"""
    await enforce_provider_quota(user_uuid)
    return success(await search_places(payload))


@router.post("/planning/routes/search", response_model=ApiResponse[list[dict]])
async def search_planning_routes(
    payload: RouteSearchRequest,
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[dict]]:
    """查询路线并签发仅属于当前用户的短期路线引用。"""
    await enforce_provider_quota(user_uuid)
    return success(await search_routes(payload, user_uuid))


@router.post("/conversations/{conversation_uuid}/proposals", response_model=ApiResponse[ProposalDetail])
def create_proposal(
    conversation_uuid: str,
    payload: ProposalCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ProposalDetail]:
    """保存一版待校验候选plan，不创建或修改正式 Plan。"""
    return success(service.create_proposal(db, user_uuid, conversation_uuid, payload), "候选已保存")


@router.get("/conversations/{conversation_uuid}/proposals", response_model=ApiResponse[list[ProposalSummary]])
def list_proposals(
    conversation_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[ProposalSummary]]:
    """读取当前会话的候选版本列表。"""
    return success(service.list_proposals(db, user_uuid, conversation_uuid))


@router.get("/conversations/{conversation_uuid}/proposals/versions/{version}", response_model=ApiResponse[ProposalDetail])
def get_proposal(
    conversation_uuid: str,
    version: int = Path(ge=1),
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ProposalDetail]:
    """按服务端版本号回读完整候选。"""
    return success(service.get_proposal(db, user_uuid, conversation_uuid, version))


@router.get(
    "/conversations/{conversation_uuid}/proposals/versions/{version}/status",
    response_model=ApiResponse[ProposalStatus],
)
def get_proposal_status(
    conversation_uuid: str,
    version: int = Path(ge=1),
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ProposalStatus]:
    """断线后独立查询候选持久化状态。"""
    return success(service.get_status(db, user_uuid, conversation_uuid, version))


@router.post(
    "/conversations/{conversation_uuid}/proposals/versions/{version}/validate",
    response_model=ApiResponse[ProposalDetail],
)
def revalidate_proposal(
    conversation_uuid: str,
    version: int = Path(ge=1),
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[ProposalDetail]:
    """按当前确定性规则重新校验已归属候选。"""
    return success(service.revalidate_proposal(db, user_uuid, conversation_uuid, version), "校验已更新")
