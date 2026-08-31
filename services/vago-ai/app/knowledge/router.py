"""Personal Travel Knowledge API 路由。"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.knowledge import service
from app.knowledge.schemas import GuideCreateRequest, GuideResponse, GuideUpdateRequest
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.get("/guides/mine", response_model=ApiResponse[list[GuideResponse]])
def list_my_guides(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[GuideResponse]]:
    """获取当前用户的个人旅行知识源列表。"""
    return success(service.list_my_guides(db, user_uuid))


@router.get("/guides/{guide_uuid}", response_model=ApiResponse[GuideResponse])
def get_my_guide_detail(
    guide_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """获取当前用户自己的知识源详情。"""
    return success(service.get_my_guide_detail(db, user_uuid, guide_uuid))


@router.post("/guides", response_model=ApiResponse[GuideResponse])
def create_guide(
    payload: GuideCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """创建个人旅行知识源；发布状态会进入后台索引队列。"""
    guide = service.create_guide(db, user_uuid, payload)
    # 分支条件：已发布知识源创建后，后台写入个人 RAG 知识库。
    if guide.status == service.GUIDE_STATUS_PUBLISHED:
        background_tasks.add_task(service.index_guide_background, guide.uuid, user_uuid)
    return success(guide, "攻略创建成功")


@router.put("/guides/{guide_uuid}", response_model=ApiResponse[GuideResponse])
def update_guide(
    guide_uuid: str,
    payload: GuideUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """更新个人旅行知识源；发布状态重建索引，草稿状态清理向量。"""
    guide = service.update_guide(db, user_uuid, guide_uuid, payload)
    # 分支条件：更新后仍是发布状态，后台重新索引。
    if guide.status == service.GUIDE_STATUS_PUBLISHED:
        background_tasks.add_task(service.index_guide_background, guide.uuid, user_uuid)
    else:
        # 分支条件：更新为草稿状态，后台清理已有向量。
        background_tasks.add_task(service.delete_guide_vectors_background, guide.uuid, user_uuid)
    return success(guide, "攻略更新成功")


@router.delete("/guides/{guide_uuid}", response_model=ApiResponse[None])
def delete_guide(
    guide_uuid: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[None]:
    """软删除个人旅行知识源，并在需要时清理向量库。"""
    should_delete_vectors = service.delete_guide(db, user_uuid, guide_uuid)
    # 分支条件：该知识源曾进入索引流程时，需要清理 Qdrant 文本块。
    if should_delete_vectors:
        background_tasks.add_task(service.delete_guide_vectors_background, guide_uuid, user_uuid)
    return success(None, "攻略删除成功")


@router.post("/guides/{guide_uuid}/index", response_model=ApiResponse[GuideResponse])
def index_guide(
    guide_uuid: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """手动触发知识源向量化。"""
    guide = service.mark_guide_pending(db, user_uuid, guide_uuid)
    background_tasks.add_task(service.index_guide_background, guide.uuid, user_uuid)
    return success(guide, "攻略已加入 AI 知识库索引队列")
