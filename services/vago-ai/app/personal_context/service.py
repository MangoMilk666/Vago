"""按任务组装 Personal Travel Context，而不是建立新的统一数据仓库。"""

import json

from sqlalchemy.orm import Session

from app.footprints import service as footprint_service
from app.knowledge import service as knowledge_service
from app.memory import service as memory_service
from app.personal_context.schemas import PersonalContextPreview
from app.preferences import service as preference_service
from app.travel import service as travel_service


def build_personal_context(
    db: Session,
    user_uuid: str,
    include_travel_context: bool = True,
    include_personal_knowledge: bool = True,
) -> PersonalContextPreview:
    """按本轮授权组合 Agent 可安全读取的旅行事实摘要。"""
    # 分支条件：用户关闭旅行上下文时，完全跳过结构化旅行事实及偏好/回忆读取。
    if include_travel_context:
        travel_context = travel_service.get_agent_travel_context(db, user_uuid)
        current_trip = travel_context["currentTrip"]
        live_observations = (
            footprint_service.get_agent_observation_context(db, user_uuid, current_trip["uuid"])
            if current_trip is not None
            else None
        )
        preferences = preference_service.get_agent_preference_context(db, user_uuid)
        memories = memory_service.get_agent_memory_context(db, user_uuid)
    else:
        current_trip = None
        travel_context = {"travelHistory": []}
        live_observations = None
        preferences = {}
        memories = []

    # 分支条件：关闭个人资料时，不读取来源数量，也不把知识资料摘要注入 Prompt。
    knowledge_summary = (
        knowledge_service.get_agent_knowledge_summary(db, user_uuid)
        if include_personal_knowledge
        else {}
    )
    labels = _build_labels(
        current_trip=current_trip,
        travel_history=travel_context["travelHistory"],
        live_observations=live_observations,
        preferences=preferences,
        memories=memories,
        knowledge_summary=knowledge_summary,
    )
    return PersonalContextPreview(
        labels=labels,
        currentTrip=current_trip,
        travelHistory=travel_context["travelHistory"],
        liveObservations=live_observations,
        preferences=preferences,
        memories=memories,
        knowledgeSummary=knowledge_summary,
    )


def format_context_for_agent(context: PersonalContextPreview) -> str:
    """将结构化上下文缩短为 Prompt 数据块，不把它当作系统指令。"""
    data = context.model_dump(by_alias=True, exclude_none=True)
    # labels 只供客户端执行摘要使用，避免重复占用模型上下文。
    data.pop("labels", None)
    return json.dumps(data, ensure_ascii=False, default=str)


def _build_labels(**context: object) -> list[str]:
    """把上下文来源转换为用户可理解的执行摘要，不泄露原始敏感位置。"""
    labels: list[str] = []
    if context["current_trip"]:
        labels.append("当前行程与日程")
    if context["travel_history"]:
        labels.append("近期旅行历史")
    if context["live_observations"]:
        labels.append("近期旅行观察")
    preferences = context["preferences"]
    if isinstance(preferences, dict) and preferences.get("hasExplicitPreference"):
        labels.append("明确旅行偏好")
    if context["memories"]:
        labels.append("Grounded Travel Memory")
    knowledge_summary = context["knowledge_summary"]
    if isinstance(knowledge_summary, dict) and knowledge_summary.get("sourceCount", 0):
        labels.append("个人知识资料摘要")
    return labels
