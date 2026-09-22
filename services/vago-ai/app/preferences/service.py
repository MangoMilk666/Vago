"""用户明确旅行偏好的领域服务。"""

import json

from sqlalchemy.orm import Session

from app.preferences.models import TravelPreference
from app.preferences.schemas import TravelPreferenceResponse, TravelPreferenceUpdateRequest
from app.travel.models import utc_now_naive


def get_preferences(db: Session, user_uuid: str) -> TravelPreferenceResponse:
    """读取用户明确偏好；尚未填写时返回空偏好，不在读取路径创建记录。"""
    preference = db.get(TravelPreference, user_uuid)
    return _to_response(preference)


def update_preferences(
    db: Session,
    user_uuid: str,
    payload: TravelPreferenceUpdateRequest,
) -> TravelPreferenceResponse:
    """更新用户明确确认的偏好，不接受或生成推断偏好。"""
    preference = db.get(TravelPreference, user_uuid)
    # 分支条件：用户第一次保存偏好时创建唯一的个人记录。
    if preference is None:
        preference = TravelPreference(user_uuid=user_uuid)
        db.add(preference)
    # 把dto按字段转为dict对象values
    values = payload.model_dump(exclude_unset=True, by_alias=False)

    # 文本规范化，构造最终保存的TravelPreference实体类对象
    for field_name, value in values.items():
        # 分支条件：兴趣标签以 JSON 字符串保存，避免数据库方言差异影响 API 语义。
        if field_name == "interests":
            value = json.dumps(_normalize_interests(value), ensure_ascii=False)
        elif field_name in {"pace", "budget_level", "notes"} and isinstance(value, str):
            value = value.strip() or None
        setattr(preference, field_name, value)

    preference.updated_at = utc_now_naive()
    db.commit()
    db.refresh(preference)
    return _to_response(preference)


def get_agent_preference_context(db: Session, user_uuid: str) -> dict:
    """为 Personal Context 输出经过长度约束的明确偏好，不包含模型推断。"""
    preference = db.get(TravelPreference, user_uuid)
    response = _to_response(preference)
    return {
        "pace": response.pace,
        "budgetLevel": response.budget_level,
        "interests": response.interests,
        "notes": (response.notes or "")[:500] or None,
        "hasExplicitPreference": any(
            [response.pace, response.budget_level, response.interests, response.notes]
        ),
    }


def _to_response(preference: TravelPreference | None) -> TravelPreferenceResponse:
    """将 ORM 偏好转换为 API 响应；空记录保持为可编辑的空状态。"""
    if preference is None:
        return TravelPreferenceResponse()
    return TravelPreferenceResponse(
        pace=preference.pace,
        budgetLevel=preference.budget_level,
        interests=_parse_interests(preference.interests),
        notes=preference.notes,
        updatedAt=preference.updated_at,
    )


def _normalize_interests(values: list[str] | None) -> list[str]:
    """去除空白与重复兴趣标签，防止无意义数据进入 Prompt。"""
    normalized: list[str] = []
    for value in values or []:
        item = value.strip()
        if item and item not in normalized:
            normalized.append(item[:64])
    return normalized


def _parse_interests(value: str | None) -> list[str]:
    """兼容读取历史或异常 JSON；异常内容不作为偏好展示或注入 Agent。"""
    if not value:
        return []
    # 把json字符串转回dict对象后再解析
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return _normalize_interests(parsed) if isinstance(parsed, list) else []
