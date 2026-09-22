"""仅供 Web Agent 测试入口使用的 Personal Context 预览 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.personal_context.schemas import PersonalContextPreview
from app.personal_context.service import build_personal_context
from app.shared.responses import ApiResponse, success

router = APIRouter()


@router.get("/context-preview", response_model=ApiResponse[PersonalContextPreview])
def preview_personal_context(
    use_personal_context: bool = Query(default=True, alias="usePersonalContext"),
    use_rag: bool = Query(default=True, alias="useRag"),
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[PersonalContextPreview]:
    """预览当前授权下 Agent 可读取的事实摘要，方便用户核对范围。"""
    return success(
        build_personal_context(
            db,
            user_uuid,
            include_travel_context=use_personal_context,
            include_personal_knowledge=use_rag,
        )
    )
