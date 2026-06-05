"""
结构化行程计划提取模块。

在 AI 文本回答生成完成后，使用独立的 LLM 调用对回答内容进行结构化提取。
仅当用户消息包含行程规划相关关键词时才触发提取，以节省 token 开销。

提取策略："两步法"
  1. 第一步：正常流式/非流式生成文本回答（由 rag_chain 完成）；
  2. 第二步：本模块使用 with_structured_output() 对文本回答做结构化提取。
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.models.schemas import StructuredPlan
from app.services.llm import get_chat_llm

logger = logging.getLogger(__name__)

# ─── 行程规划关键词（用户消息命中任一则触发结构化提取）───────────────────────

PLANNING_KEYWORDS: list[str] = [
    "规划", "计划", "行程", "安排", "攻略",
    "plan", "itinerary", "schedule", "trip",
    "几日游", "天游", "日游", "自由行", "旅行",
]


def _should_extract(user_message: str) -> bool:
    """
    判断用户消息是否包含行程规划相关关键词。

    仅当定位到行程规划关键词时才触发后续的结构化提取 LLM 调用，
    避免对闲聊类问题浪费 token。
    """
    text = user_message.lower()
    return any(kw in text for kw in PLANNING_KEYWORDS)


# ─── 提取用 Wrapper Schema ─────────────────────────────────────────────────────

class _ExtractionResult(BaseModel):
    """提取结果包装器，允许 LLM 返回 null 表示无行程内容。"""
    plan: Optional[StructuredPlan] = Field(
        None,
        description=(
            "从文本中提取的结构化旅行计划。"
            "如果文本不包含具体的多日行程规划内容，返回 null。"
        ),
    )


# ─── 提取 Prompt ───────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """你是一个结构化数据提取助手。请从以下 AI 旅行助手的回答文本中提取结构化行程计划。

提取规则：
1. 如果文本包含具体的多日行程规划（如 "第1天"、"Day 1" 等按天安排），则提取为结构化计划。
2. 如果文本只是一般性建议、单个景点推荐、或非行程规划内容，plan 字段返回 null。
3. title：根据内容生成简洁的行程标题（如"东京5日游"、"京都文化之旅"）。
4. destination：提取主要目的地。
5. start_date / end_date：仅当文本中有明确日期时填写（YYYY-MM-DD 格式），否则为 null。
6. budget / budget_currency：仅当文本中提到具体预算金额时填写，否则为 null。budget_currency 默认 "CNY"。
7. days：按天提取，day_index 从 1 开始。
8. spots：每天的景点按文本中出现的顺序排列，sort_order 从 0 开始。
9. category：0=景点/观光, 1=餐厅/美食, 2=购物, 3=娱乐, 4=中转/交通枢纽, 5=其他。
10. duration_minutes：根据文本提示估算，无提示则为 null。

--- 以下是 AI 旅行助手的回答文本 ---

{answer_text}
"""


# ─── 公开接口 ──────────────────────────────────────────────────────────────────

async def extract_structured_plan(
    answer_text: str,
    user_message: str,
) -> Optional[StructuredPlan]:
    """
    尝试从 AI 回答文本中提取结构化行程计划。

    提取流程：
      1. 关键词检测：user_message 不含规划关键词 → 直接返回 None；
      2. LLM 结构化提取：使用 with_structured_output() 约束输出为 StructuredPlan；
      3. 空值处理：LLM 判断文本不含行程 → 返回 None。

    参数:
        answer_text:  完整的 AI 回答文本。
        user_message: 触发本轮对话的用户消息（用于关键词检测）。

    返回:
        StructuredPlan 实例（提取成功）或 None（不含行程 / 提取失败）。
    """
    # 1. 关键词预检
    if not _should_extract(user_message):
        logger.debug("[plan_extractor] 用户消息不含规划关键词，跳过结构化提取")
        return None

    # 2. 文本过短，不太可能包含完整行程
    if len(answer_text.strip()) < 100:
        logger.debug("[plan_extractor] 回答文本过短（%d 字），跳过提取", len(answer_text))
        return None

    logger.info("[plan_extractor] 开始结构化提取，回答长度=%d", len(answer_text))

    try:
        # 要进行结构化提取（让 AI 填表），必须等它完全思考完毕并返回一个完整的 JSON 结构
        # 所以这里不能使用流式打字机效果，必须一次性全量返回
        llm = get_chat_llm(streaming=False)
        # 约束llm的输出结构
        structured_llm = llm.with_structured_output(_ExtractionResult)

        # 使用 await 和 ainvoke 进行异步非阻塞调用。
        # 在等待大模型提取的 2-3 秒期间，Python 服务的事件循环（Event Loop）会被释放，去处理其他的并发网络请求，保持服务的高吞吐
        result = await structured_llm.ainvoke(
            EXTRACTION_PROMPT.format(answer_text=answer_text)
        )

        plan = None
        if isinstance(result, dict):
            plan_data = result.get("plan")
            if plan_data:
                if isinstance(plan_data, dict):
                    plan = StructuredPlan(**plan_data)
                elif isinstance(plan_data, StructuredPlan):
                    plan = plan_data
        elif result is not None and hasattr(result, "plan"):
            plan = result.plan

        if plan:
            logger.info(
                "[plan_extractor] 提取成功: title='%s' destination='%s' days=%d",
                plan.title, plan.destination, len(plan.days),
            )
            return plan

        logger.info("[plan_extractor] LLM 判断文本不含行程规划内容")
        return None

    except Exception as exc:
        logger.error("[plan_extractor] 结构化提取失败: %s", exc, exc_info=True)
        return None
