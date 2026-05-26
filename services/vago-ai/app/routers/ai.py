"""
AI 功能路由
- POST /api/v1/ai/plan     行程规划（LLM 生成）
- POST /api/v1/ai/search   攻略 RAG 检索
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()


# ─── 请求 / 响应模型 ──────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    destination: str = Field(..., description="目的地，如 '日本京都'")
    days: int = Field(..., ge=1, le=30, description="行程天数")
    style: Optional[str] = Field(None, description="旅行风格：culture / food / nature / city")
    budget: Optional[str] = Field(None, description="预算级别：budget / mid / luxury")
    user_uuid: Optional[str] = Field(None, description="用户 UUID，用于个性化推荐")


class PlanResponse(BaseModel):
    plan: str = Field(..., description="生成的行程文本（Markdown 格式）")
    tips: list[str] = Field(default_factory=list, description="旅行小贴士")


class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词，如 '京都三日游推荐'")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")


class SearchResult(BaseModel):
    article_id: str
    title: str
    summary: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


# ─── 路由处理 ─────────────────────────────────────────────────────────────────

@router.post("/plan", response_model=PlanResponse, summary="AI 行程规划")
async def plan_itinerary(req: PlanRequest):
    """
    根据目的地、天数、风格生成个性化行程计划。
    TODO: 接入 LangChain + OpenAI，当前返回占位响应。
    """
    # Placeholder — 实际接入 LLM 时替换此处
    mock_plan = (
        f"## {req.destination} {req.days} 日行程\n\n"
        f"**Day 1**：抵达 → 酒店入住 → 周边探索\n\n"
        f"**Day 2**：核心景点打卡\n\n"
        f"**Day 3**：深度体验 + 返程\n\n"
        f"> AI 规划功能开发中，敬请期待 🚧"
    )
    return PlanResponse(
        plan=mock_plan,
        tips=["提前预订热门景点门票", "建议购买当地交通通票"],
    )


@router.post("/search", response_model=SearchResponse, summary="攻略 RAG 检索")
async def search_articles(req: SearchRequest):
    """
    基于向量相似度检索攻略库，返回最相关的 top_k 篇文章摘要。
    TODO: 接入 Milvus/Qdrant 向量数据库，当前返回空结果。
    """
    # Placeholder — 接入向量 DB 时替换
    return SearchResponse(results=[])
