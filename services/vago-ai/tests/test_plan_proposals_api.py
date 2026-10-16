"""规划候选 API 的回读、幂等及双用户隔离测试。"""

from collections.abc import Generator
from pathlib import Path
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import api_v1_router
from app.core.database import Base, get_db
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import get_current_user_uuid
from app.plan_proposals.models import PlanProposal

SAMPLE_PATH = Path(__file__).resolve().parents[3] / "docs/project-merge/phase-1/cases.json"


@pytest.fixture()
def client_and_db() -> Generator[tuple[TestClient, Session, dict[str, str]], None, None]:
    """测试：用同一 SQLite 会话模拟两个经认证的 Vago 用户。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()
    identity = {"uuid": "user-a"}
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    def override_db() -> Generator[Session, None, None]:
        yield db

    async def override_user() -> str:
        return identity["uuid"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_uuid] = override_user
    with TestClient(app) as client:
        yield client, db, identity
    db.close()
    engine.dispose()


def _conversation(client: TestClient) -> str:
    return client.post("/api/v1/agent/conversations", json={}).json()["data"]["uuid"]


def _payload(key: str = "request-key-001") -> dict:
    sample = json.loads(SAMPLE_PATH.read_text())["cases"][0]
    return {
        "idempotencyKey": key,
        "targetKind": "new_plan",
        "brief": sample["wkf_form"],
        "content": {
            "points": [{"id": "fictional-stop", "placeRef": "example.invalid/stop", "name": "示例地点"}],
            "routes": [{"pointIds": ["fictional-stop"], "polyline": []}],
            "warnings": ["仅为合成数据，不可用于正式确认"],
        },
    }


def test_proposal_round_trip_version_and_idempotency(client_and_db):
    """测试：固定样例完整回读、版本递增，同一请求重试不重复写入。"""
    client, db, _ = client_and_db
    conversation_uuid = _conversation(client)
    url = f"/api/v1/agent/conversations/{conversation_uuid}/proposals"
    first = client.post(url, json=_payload())
    assert first.status_code == 200
    created = first.json()["data"]
    assert created["version"] == 1
    assert created["status"] == "PENDING_VALIDATION"
    assert created["content"]["points"][0]["placeRef"] == "example.invalid/stop"
    assert created["brief"]["cities"] == ["示例城甲", "示例城乙"]
    assert client.post(url, json=_payload()).json()["data"]["uuid"] == created["uuid"]
    assert db.scalar(select(func.count()).select_from(PlanProposal)) == 1

    second = client.post(url, json=_payload("request-key-002")).json()["data"]
    assert second["version"] == 2
    assert [item["version"] for item in client.get(url).json()["data"]] == [2, 1]
    assert client.get(f"{url}/versions/1").json()["data"]["content"] == created["content"]
    assert client.get(f"{url}/versions/1/status").json()["data"]["status"] == "PENDING_VALIDATION"
    assert client.get(f"{url}/versions/99").status_code == 404
    assert client.post(url, json={**_payload(), "content": {"points": []}}).status_code == 409
    # 候选保存只是规划资源持久化，不得隐式创建正式计划。
    assert client.get("/api/v1/travel/plans").json()["data"] == []


def test_proposal_endpoints_are_isolated_and_conversation_delete_cleans_up(client_and_db):
    """测试：另一个用户不能创建、列表、读版本或状态，也不能通过改请求体取得归属。"""
    client, db, identity = client_and_db
    conversation_uuid = _conversation(client)
    url = f"/api/v1/agent/conversations/{conversation_uuid}/proposals"
    client.post(url, json=_payload())

    identity["uuid"] = "user-b"
    assert client.post(url, json=_payload("request-key-003")).status_code == 404
    assert client.get(url).status_code == 404
    assert client.get(f"{url}/versions/1").status_code == 404
    assert client.get(f"{url}/versions/1/status").status_code == 404
    assert client.post(url, json={**_payload("request-key-007"), "userUuid": "user-a"}).status_code == 422
    assert db.scalar(select(func.count()).select_from(PlanProposal)) == 1

    identity["uuid"] = "user-a"
    assert client.delete(f"/api/v1/agent/conversations/{conversation_uuid}").status_code == 200
    assert db.scalar(select(func.count()).select_from(PlanProposal)) == 0


def test_draft_target_requires_owner_and_unconverted_plan(client_and_db):
    """测试：仅当前账号的未转换草稿可作为编辑候选的目标。"""
    client, _, identity = client_and_db
    conversation_uuid = _conversation(client)
    url = f"/api/v1/agent/conversations/{conversation_uuid}/proposals"
    draft = client.post(
        "/api/v1/travel/plans",
        json={"title": "已有草稿", "startDate": "2026-11-03", "endDate": "2026-11-04"},
    ).json()["data"]
    payload = {**_payload(), "targetKind": "draft_plan", "targetPlanUuid": draft["uuid"]}
    assert client.post(url, json=payload).status_code == 200
    assert client.post(url, json={**_payload("request-key-004"), "targetKind": "draft_plan"}).status_code == 422

    identity["uuid"] = "user-b"
    other_conversation = _conversation(client)
    other_url = f"/api/v1/agent/conversations/{other_conversation}/proposals"
    assert client.post(other_url, json={**payload, "idempotencyKey": "request-key-005"}).status_code == 404

    identity["uuid"] = "user-a"
    assert client.post(f"/api/v1/travel/plans/{draft['uuid']}/convert").status_code == 200
    assert client.post(url, json={**payload, "idempotencyKey": "request-key-006"}).status_code == 409
