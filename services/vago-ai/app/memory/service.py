"""Grounded Travel Memory 领域服务。"""

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.footprints.models import TravelObservation
from app.footprints.service import AUTO_GPS, MANUAL_CHECKIN
from app.memory.models import TravelMemory
from app.memory.schemas import (
    MemoryCheckinFact,
    TravelMemoryFacts,
    TravelMemoryResponse,
    TravelMemoryUpdateRequest,
)
from app.travel.models import ItineraryDay, ItinerarySpot, Trip, utc_now_naive
from app.travel.service import TRIP_STATUS_ENDED


def refresh_trip_memory(db: Session, user_uuid: str, trip_uuid: str) -> TravelMemoryResponse:
    """从已结束行程的领域事实刷新 Memory 快照，不调用模型生成内容。"""
    trip = _get_owned_trip(db, user_uuid, trip_uuid)
    # 分支条件：行程尚未结束时事实仍可能变化，不能提前固化为旅行回忆。
    if trip.status != TRIP_STATUS_ENDED:
        raise AppException("仅已结束行程可以生成旅行回忆", status_code=409, code="TRIP_NOT_ENDED")

    facts = _build_facts(db, trip)
    memory = db.scalar(
        select(TravelMemory).where(
            TravelMemory.user_uuid == user_uuid,
            TravelMemory.trip_uuid == trip_uuid,
        )
    )
    # 分支条件：同一用户和行程只维护一份 Memory，刷新时保留用户原有叙事。
    if memory is None:
        memory = TravelMemory(
            uuid=uuid4().hex,
            user_uuid=user_uuid,
            trip_uuid=trip_uuid,
            title=f"{trip.title}旅行回忆",
            fact_snapshot=_serialize_facts(facts),
        )
        db.add(memory)
    else:
        memory.fact_snapshot = _serialize_facts(facts)
        memory.facts_refreshed_at = utc_now_naive()

    db.commit()
    db.refresh(memory)
    return _to_response(memory)


def list_memories(db: Session, user_uuid: str) -> list[TravelMemoryResponse]:
    """列出当前用户的 Grounded Travel Memory。"""
    memories = db.scalars(
        select(TravelMemory)
        .where(TravelMemory.user_uuid == user_uuid)
        .order_by(TravelMemory.updated_at.desc())
    ).all()
    return [_to_response(memory) for memory in memories]


def update_memory(
    db: Session,
    user_uuid: str,
    memory_uuid: str,
    payload: TravelMemoryUpdateRequest,
) -> TravelMemoryResponse:
    """更新用户可编辑的叙事字段，不允许覆盖事实快照。"""
    memory = db.scalar(
        select(TravelMemory).where(
            TravelMemory.uuid == memory_uuid,
            TravelMemory.user_uuid == user_uuid,
        )
    )
    if memory is None:
        raise AppException("旅行回忆不存在或无权访问", status_code=404, code="MEMORY_NOT_FOUND")

    values = payload.model_dump(exclude_unset=True)
    for field_name, value in values.items():
        # 分支条件：用户输入空叙事代表主动清除，不影响已经落库的事实快照。
        if field_name == "narrative" and isinstance(value, str):
            value = value.strip() or None
        elif field_name == "title" and isinstance(value, str):
            value = value.strip()
        setattr(memory, field_name, value)

    memory.updated_at = utc_now_naive()
    db.commit()
    db.refresh(memory)
    return _to_response(memory)


def get_agent_memory_context(db: Session, user_uuid: str, limit: int = 3) -> list[dict]:
    """为 Personal Context 提供近期 Memory 摘要，避免把完整叙事无上限注入 Prompt。"""
    memories = db.scalars(
        select(TravelMemory)
        .where(TravelMemory.user_uuid == user_uuid)
        .order_by(TravelMemory.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "title": memory.title,
            "tripUuid": memory.trip_uuid,
            "destination": _parse_facts(memory.fact_snapshot).destination,
            "narrative": (memory.narrative or "")[:500] or None,
        }
        for memory in memories
    ]


def _get_owned_trip(db: Session, user_uuid: str, trip_uuid: str) -> Trip:
    """读取用户自己的正式行程，避免跨用户生成回忆。找不到抛出异常"""
    trip = db.scalar(
        select(Trip).where(
            Trip.uuid == trip_uuid,
            Trip.user_uuid == user_uuid,
            Trip.deleted_at.is_(None),
        )
    )
    if trip is None:
        raise AppException("行程不存在或无权访问", status_code=404, code="TRIP_NOT_FOUND")
    return trip


def _build_facts(db: Session, trip: Trip) -> TravelMemoryFacts:
    """从 Travel 与 Footprint 事实构建可审计快照，不做 LLM 推断。"""
    days = db.scalars(
        select(ItineraryDay).where(
            ItineraryDay.ref_uuid == trip.uuid,
            ItineraryDay.ref_type == ItineraryDay.REF_TYPE_TRIP,
        )
    ).all()
    day_uuids = [day.uuid for day in days]
    spots = []
    # 分支条件：没有日程时避免生成空 IN 查询，Memory 仍可依据行程与足迹建立。
    if day_uuids:
        spots = db.scalars(
            select(ItinerarySpot)
            .where(ItinerarySpot.day_uuid.in_(day_uuids))
            .order_by(ItinerarySpot.sort_order.asc())
        ).all()
    observations = db.scalars(
        select(TravelObservation)
        .where(TravelObservation.trip_uuid == trip.uuid, TravelObservation.user_uuid == trip.user_uuid)
        .order_by(TravelObservation.occurred_at.asc())
    ).all()
    # 返回结果，包含的手动打卡点最多20个
    return TravelMemoryFacts(
        tripUuid=trip.uuid,
        tripTitle=trip.title,
        destination=trip.destination,
        startDate=trip.start_date,
        endDate=trip.end_date,
        itinerarySpotNames=[spot.name for spot in spots[:30]],
        automaticSampleCount=sum(item.observation_type == AUTO_GPS for item in observations),
        checkins=[
            MemoryCheckinFact(locationName=item.location_name or "未命名地点", occurredAt=item.occurred_at)
            for item in observations
            if item.observation_type == MANUAL_CHECKIN
        ][:20],
    )


def _to_response(memory: TravelMemory) -> TravelMemoryResponse:
    """将 Memory ORM 转为显式 facts / narrative 响应。"""
    return TravelMemoryResponse(
        uuid=memory.uuid,
        tripUuid=memory.trip_uuid,
        title=memory.title,
        facts=_parse_facts(memory.fact_snapshot),
        narrative=memory.narrative,
        factsRefreshedAt=memory.facts_refreshed_at,
        createdAt=memory.created_at,
        updatedAt=memory.updated_at,
    )


def _serialize_facts(facts: TravelMemoryFacts) -> str:
    """以稳定 JSON 保存事实快照，支持后续审计和 API 重放。"""
    return json.dumps(facts.model_dump(mode="json", by_alias=True), ensure_ascii=False)


def _parse_facts(value: str) -> TravelMemoryFacts:
    """解析已保存快照；损坏数据视为服务端数据错误而非沉默伪造事实。"""
    try:
        return TravelMemoryFacts.model_validate_json(value)
    except ValueError as exc:
        raise AppException("旅行回忆事实快照损坏", status_code=500, code="MEMORY_FACTS_INVALID") from exc
