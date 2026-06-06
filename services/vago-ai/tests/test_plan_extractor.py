#!/usr/bin/env python3
"""
Test plan_extractor.py logic.
"""

import asyncio
import logging
import sys
from pathlib import Path

# sys.path configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.plan_extractor import extract_structured_plan, _should_extract

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_plan_extractor")


async def main():
    # 1. Test keyword filtering
    logger.info("--- Testing _should_extract ---")
    assert _should_extract("帮我规划一个旅行行程") is True
    assert _should_extract("去哪玩比较好") is False
    assert _should_extract("东京旅游攻略") is True
    assert _should_extract("你好，随便聊聊") is False
    logger.info("Keyword filtering tests passed!")

    # 2. Test extraction with a planning question
    logger.info("--- Testing extract_structured_plan with plan content ---")
    answer_text = """
这是我为你规划的东京 3 日游行程：
第一天：
- 上午：参观浅草寺，感受传统江户文化。
- 下午：去秋叶原逛动漫周边店。
- 晚上：在新宿吃拉面，住宿在新宿。

第二天：
- 上午：去筑地场外市场吃海鲜早餐，然后前往东京铁塔。
- 下午：去涩谷十字路口打卡。
- 晚上：六本木看夜景。

第三天：
- 全天：东京迪士尼乐园一日游。
预算预计为每人 3000 元人民币左右。
"""
    user_message = "帮我规划一个东京3日游行程"
    
    logger.info("Extracting plan...")
    plan = await extract_structured_plan(answer_text, user_message)
    if plan:
        logger.info("Successfully extracted plan!")
        logger.info(f"Title: {plan.title}")
        logger.info(f"Destination: {plan.destination}")
        logger.info(f"Budget: {plan.budget} {plan.budget_currency}")
        logger.info(f"Days: {len(plan.days)}")
        for day in plan.days:
            logger.info(f"  Day {day.day_index}: accommodation={day.accommodation}, spots={len(day.spots)}")
            for spot in day.spots:
                logger.info(f"    - Spot: name={spot.name}, category={spot.category}")
    else:
        logger.error("Failed to extract plan (returned None)")

    # 3. Test extraction with non-planning question
    logger.info("--- Testing extract_structured_plan with non-plan content ---")
    non_plan_answer = "东京是一个很棒的城市，那里有很多好玩的景点。比如浅草寺、秋叶原和东京铁塔。你可以考虑坐地铁出行。"
    plan_none = await extract_structured_plan(non_plan_answer, "你好，随便聊聊")
    if plan_none is None:
        logger.info("Successfully skipped non-plan content (returned None)!")
    else:
        logger.error(f"Failed: extracted plan from non-plan content: {plan_none}")


if __name__ == "__main__":
    asyncio.run(main())
