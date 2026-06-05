"""
统一请求/响应 Pydantic 模型。

所有路由的入参与返回体均定义于此，避免在 router 文件中散乱定义。
枚举类型供 Service 层复用，保证类型安全。
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── 枚举 ─────────────────────────────────────────────────────────────────────

class ArticleStatus(str, Enum):
    """攻略索引状态机。"""

    PENDING = "PENDING"      # 已接收，等待处理
    INDEXING = "INDEXING"    # 正在向量化
    INDEXED = "INDEXED"      # 已完成索引
    FAILED = "FAILED"        # 处理失败


class ArticleCategory(str, Enum):
    """攻略内容分类标签。"""

    TRANSPORT = "TRANSPORT"      # 交通
    HOTEL = "HOTEL"              # 住宿
    FOOD = "FOOD"                # 美食
    ATTRACTION = "ATTRACTION"    # 景点
    TIPS = "TIPS"                # 攻略贴士


# ─── 攻略入库（Ingest）─────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    """Java 侧调用 /articles/ingest 时的请求体。"""

    article_id: str = Field(..., description="由 Java 生成的攻略 UUID，用于幂等 upsert")
    user_uuid: str = Field(..., description="所属用户 UUID，用于向量库命名空间隔离")
    title: str = Field(..., max_length=200, description="攻略标题")
    source_url: Optional[str] = Field(None, description="原始来源链接，可为空")
    raw_content: str = Field(
        ...,
        max_length=50000,
        description="原始攻略全文，最多 50000 字",
    )
    destinations: Optional[list[str]] = Field(
        None,
        description="前端已打标的目的地列表；为 None 时由 AI 服务自动提取",
    )


class IngestResponse(BaseModel):
    """攻略入库结果，Java 侧依据此更新 article 状态字段。"""

    article_id: str
    status: ArticleStatus
    chunk_count: int = Field(description="实际写入向量库的文本块数量")
    destinations: list[str] = Field(description="提取到的目的地列表")
    categories: list[str] = Field(description="提取到的内容分类列表（ArticleCategory 枚举值）")
    message: str = Field(description="处理结果描述，失败时包含错误原因")


# ─── 攻略 RAG 检索（Search）──────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """RAG 向量检索请求，通常由 AI 规划链路在内部调用。"""

    query: str = Field(..., description="自然语言检索问题，如「京都三日游景点推荐」")
    user_uuid: str = Field(..., description="仅检索该用户的私有攻略库")
    top_k: int = Field(5, ge=1, le=20, description="返回最相关的 top_k 个文本块")
    score_threshold: float = Field(
        0.60,
        ge=0.0,
        le=1.0,
        description="余弦相似度阈值，低于此值的结果被过滤",
    )


class SearchResultItem(BaseModel):
    """单条检索结果，对应 Qdrant 中的一个文本块。"""

    article_id: str
    chunk_index: int
    chunk_text: str = Field(description="命中的文本块原文")
    title: str = Field(description="所属攻略标题")
    destinations: list[str]
    categories: list[str]
    score: float = Field(description="与查询的余弦相似度得分，范围 [0, 1]")


class SearchResponse(BaseModel):
    """RAG 检索结果集。"""

    query: str
    results: list[SearchResultItem]
    total: int = Field(description="命中结果总数（已过滤阈值后）")


# ─── 攻略删除（Delete）───────────────────────────────────────────────────────

class DeleteArticleResponse(BaseModel):
    """删除攻略向量数据的结果。"""

    article_id: str
    deleted_count: int = Field(description="从向量库中删除的文本块数量")
    message: str


# ─── AI 行程规划（Plan）──────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    """AI 行程规划请求。"""

    destination: str = Field(..., description="目的地，如「日本京都」")
    days: int = Field(..., ge=1, le=30, description="行程天数")
    style: Optional[str] = Field(
        None,
        description="旅行风格：culture / food / nature / city",
    )
    budget: Optional[str] = Field(
        None,
        description="预算级别：budget / mid / luxury",
    )
    user_uuid: Optional[str] = Field(None, description="用户 UUID，用于 RAG 个性化检索")


class PlanResponse(BaseModel):
    """AI 行程规划结果（当前为占位实现，后续接入 RAG + LLM）。"""

    plan: str = Field(description="生成的行程文本（Markdown 格式）")
    tips: list[str] = Field(default_factory=list, description="旅行小贴士列表")


# ─── AI 对话（Chat）──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """单条对话消息，兼容 OpenAI Chat Completions 消息格式。"""

    role: Literal["user", "assistant", "system"] = Field(
        description="消息角色：user=用户输入，assistant=模型回复，system=系统提示"
    )
    content: str = Field(..., description="消息正文")


class ChatRequest(BaseModel):
    """AI 对话请求体，由 Java vago-backend 或前端直接发送。"""

    user_uuid: str = Field(..., description="当前用户 UUID，用于 RAG 检索隔离")
    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        description=(
            "完整对话历史（含本轮用户消息）。"
            "列表最后一条必须为 role=user 的消息。"
            "Java 侧负责维护历史记录并完整传入，服务端无状态。"
        ),
    )
    use_rag: bool = Field(
        True,
        description="是否启用 RAG 私有攻略库检索。False 时直接调用 LLM 通用知识。",
    )
    top_k: int = Field(6, ge=1, le=20, description="RAG 检索返回的最大文本块数")
    score_threshold: float = Field(
        0.55,
        ge=0.0,
        le=1.0,
        description="RAG 检索相似度阈值，低于此值的结果被过滤",
    )


class SourceCitation(BaseModel):
    """RAG 检索命中的攻略来源，随回答一同返回，供前端展示引用来源。"""

    article_id: str
    title: str = Field(description="攻略标题")
    chunk_text: str = Field(description="命中的文本块摘要（前 300 字）")
    score: float = Field(description="相似度得分，范围 [0, 1]")


# ─── AI 结构化行程计划（Structured Plan）─────────────────────────────────────

class StructuredSpot(BaseModel):
    """结构化行程中的单个景点/打卡点，对齐 itinerary_spots 表结构。"""
    name: str = Field(..., description="景点名称")
    address: Optional[str] = Field(None, description="详细地址")
    category: int = Field(0, ge=0, le=5, description="0=景点, 1=餐厅, 2=购物, 3=娱乐, 4=中转, 5=其他")
    sort_order: int = Field(0, description="排序序号（从 0 开始）")
    duration_minutes: Optional[int] = Field(None, ge=0, description="预计停留时间（分钟）")
    notes: Optional[str] = Field(None, description="备注")


class StructuredDay(BaseModel):
    """结构化行程中的单日计划，对齐 itinerary_days 表结构。"""
    day_index: int = Field(..., ge=1, description="第几天（1-based）")
    day_date: Optional[str] = Field(None, description="具体日期 YYYY-MM-DD，无明确日期时为 null")
    transportation: Optional[str] = Field(None, description="当日交通方式")
    accommodation: Optional[str] = Field(None, description="住宿信息")
    meal_breakfast: Optional[str] = Field(None, description="早餐")
    meal_lunch: Optional[str] = Field(None, description="午餐")
    meal_dinner: Optional[str] = Field(None, description="晚餐")
    budget_day: Optional[float] = Field(None, ge=0, description="当日预算")
    notes: Optional[str] = Field(None, description="当日备注")
    spots: list[StructuredSpot] = Field(default_factory=list, description="当日景点列表")


class StructuredPlan(BaseModel):
    """AI 提取的结构化旅行计划，（复用）对齐 plans/trips + itinerary_days/spots 表结构。"""
    title: str = Field(..., description="行程标题")
    destination: str = Field(..., description="目的地")
    start_date: Optional[str] = Field(None, description="出发日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="返回日期 YYYY-MM-DD")
    budget: Optional[float] = Field(None, ge=0, description="总预算")
    budget_currency: str = Field("CNY", description="货币单位")
    days: list[StructuredDay] = Field(..., min_length=1, description="每日行程")


class ChatResponse(BaseModel):
    """AI 对话非流式响应体。"""

    answer: str = Field(description="模型生成的回答文本")
    sources: list[SourceCitation] = Field(
        default_factory=list,
        description="本次回答引用的攻略来源列表，为空时表示基于通用知识作答",
    )
    model: str = Field(description="实际使用的模型名称")
    structured_plan: Optional[StructuredPlan] = Field(
        None,
        description="结构化行程计划（仅当回答包含行程规划时）",
    )
