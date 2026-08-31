"""
AI 行程规划路由（AI Router）。

提供基于 LLM 的行程生成接口。
当前为 Stub 实现（返回占位文本），待 RAG 检索链路完成后接入：
  - 调用 articles.search 检索用户私有攻略库（Top-K RAG 召回）
  - 将检索结果注入 Prompt，调用 OpenAI Chat Completion
  - 解析结构化 JSON 行程草稿并返回

TODO: 接入 LangChain RAG Chain + OpenAI GPT-4o
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_uuid
from app.models.schemas import AiPlanSaveResponse, PlanRequest, PlanResponse, StructuredPlan
from app.shared.responses import ApiResponse, success
from app.travel import service as travel_service

router = APIRouter()


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="AI 行程规划（RAG + LLM）",
    description=(
        "根据目的地、天数、风格、预算生成个性化行程计划。\n"
        "优先检索 user_uuid 对应的个人攻略库（RAG），\n"
        "库内内容不足时 fallback 到模型通用知识。\n\n"
        "**当前状态**：Stub 占位，完整 LLM 链路开发中。"
    ),
)
async def plan_itinerary(req: PlanRequest) -> PlanResponse:
    """
    AI 行程规划接口（占位实现）。

    接收用户的自然语言规划需求，返回结构化行程草稿。
    完整实现流程：
      1. embed_query(req 转换为问题文本)
      2. search_by_user(user_uuid, query_embedding, top_k=8)
      3. 构建 RAG Prompt（检索结果 + 用户偏好 + 系统约束）
      4. 调用 OpenAI Chat Completion（GPT-4o）
      5. 解析 JSON 行程 → 返回 PlanResponse

    参数:
        req: PlanRequest，包含 destination、days、style、budget、user_uuid。

    返回:
        PlanResponse，包含 Markdown 行程文本和贴士列表。
    """
    # Placeholder — 接入 LangChain RAG Chain 时替换此处
    mock_plan = (
        f"## {req.destination} {req.days} 日行程\n\n"
        f"**Day 1**：抵达 {req.destination} → 酒店入住 → 周边漫步\n\n"
        f"**Day 2**：核心景点打卡 → 当地美食体验\n\n"
        f"**Day 3**：深度体验 → 购物 → 返程\n\n"
        f"> AI 规划功能正在接入 RAG 链路，敬请期待。"
    )
    return PlanResponse(
        plan=mock_plan,
        tips=[
            "提前预订热门景点门票，避免排队",
            "建议购买当地交通通票节省费用",
            "导入更多目的地攻略可获得更个性化的推荐",
        ],
    )


@router.post("/plans/save-draft", response_model=ApiResponse[AiPlanSaveResponse])
def save_structured_plan_as_draft(
    payload: StructuredPlan,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[AiPlanSaveResponse]:
    """保存 AI 生成的结构化行程为 Plan 草稿。"""
    result = travel_service.save_structured_plan_as_draft(db, user_uuid, payload)
    return success(result)


@router.post("/plans/save-trip", response_model=ApiResponse[AiPlanSaveResponse])
def save_structured_plan_as_trip(
    payload: StructuredPlan,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[AiPlanSaveResponse]:
    """保存 AI 生成的结构化行程为正式 Trip。"""
    result = travel_service.save_structured_plan_as_trip(db, user_uuid, payload)
    return success(result)
