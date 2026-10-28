import asyncio
import os
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.agent_conversations import service as conversations
from app.agent_conversations.schemas import ConversationCreateRequest
from app.core.database import SessionLocal
from app.core.redis import close_redis_pool
from app.plan_proposals import service as proposals
from app.plan_proposals.providers import PlaceSearchRequest, RouteSearchRequest, search_places, search_routes, route_preview_image
from app.plan_proposals.schemas import ProposalCreateRequest
from app.users.models import User


@pytest.mark.skipif(os.getenv("VAGO_AMAP_LIVE_TEST") != "1", reason="需显式开启真实高德和 MySQL 验收")
def test_mainland_route_proposal_round_trip_with_live_amap():
    """测试：真实境内路线可预览、保存候选并跨数据库会话回读。"""
    user_uuid = "5519a1d427b249ed90e5fd9851224125"
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.uuid == user_uuid, User.nickname == "wkf-merge-test"))
        assert user is not None
        conversation = conversations.create_conversation(db, user_uuid, ConversationCreateRequest())

    async def query_route():
        try:
            origin = (await search_places(PlaceSearchRequest(countryCode="CN", city="上海", query="外滩")))[0]
            destination = (await search_places(PlaceSearchRequest(countryCode="CN", city="上海", query="东方明珠")))[0]
            route_request = RouteSearchRequest(
                countryCode="CN", city="上海", cityCode=origin.get("cityCode"), mode="walking",
                fromItemId=origin["id"], toItemId=destination["id"],
                originLatitude=origin["latitude"], originLongitude=origin["longitude"],
                destinationLatitude=destination["latitude"], destinationLongitude=destination["longitude"],
                coordinateSystem="GCJ-02",
            )
            route = (await search_routes(route_request, user_uuid))[0]
            image, media_type = await route_preview_image(route["routeChoiceId"], user_uuid)
            assert media_type.startswith("image/png") and image.startswith(b"\x89PNG")
            return origin, destination, route
        finally:
            await close_redis_pool()

    try:
        origin, destination, route = asyncio.run(query_route())
        trip_date = date(2026, 11, 1)
        destination_start = datetime.combine(trip_date, time(9, 30)) + timedelta(minutes=route["routeDurationMinutes"] + 15)
        destination_end = destination_start + timedelta(minutes=30)
        assert destination_end.date() == trip_date
        items = [
            {"id": origin["id"], "name": origin["name"], "kind": "custom", "city": "上海",
             "latitude": origin["latitude"], "longitude": origin["longitude"],
             "coordinateSystem": "GCJ-02", "startTime": "09:00", "endTime": "09:30"},
            {"id": destination["id"], "name": destination["name"], "kind": "custom", "city": "上海",
             "latitude": destination["latitude"], "longitude": destination["longitude"],
             "coordinateSystem": "GCJ-02", "startTime": destination_start.strftime("%H:%M"),
             "endTime": destination_end.strftime("%H:%M")},
        ]
        leg = {"fromItemId": origin["id"], "toItemId": destination["id"],
               "routeDurationMinutes": route["routeDurationMinutes"], "bufferMinutes": 0,
               "provider": route["provider"], "mode": route["mode"],
               "queriedAt": route["queriedAt"], "routeChoiceId": route["routeChoiceId"]}
        request = ProposalCreateRequest(
            idempotencyKey="phase4-live-route-001", targetKind="new_plan",
            brief={"startDate": trip_date.isoformat(), "endDate": trip_date.isoformat(),
                   "timezone": "Asia/Shanghai", "hardConstraints": []},
            content={"days": [{"day": 1, "date": trip_date.isoformat(), "city": "上海",
                               "timezone": "Asia/Shanghai", "items": items, "legs": [leg]}]},
        )
        with SessionLocal() as db:
            created = proposals.create_proposal(db, user_uuid, conversation.uuid, request)
            assert created.status == "VALIDATED"
            assert any(check["code"] == "route_provenance" and check["status"] == "pass"
                       for check in created.validation["checks"])
        with SessionLocal() as db:
            detail = proposals.get_proposal(db, user_uuid, conversation.uuid, created.version)
            assert detail.content["days"][0]["legs"][0]["routeChoiceId"] == route["routeChoiceId"]
            assert detail.validation["hardChecksPassed"] is True
            assert proposals.list_proposals(db, user_uuid, conversation.uuid)[0].version == created.version
    finally:
        with SessionLocal() as db:
            conversations.delete_conversation(db, user_uuid, conversation.uuid)
