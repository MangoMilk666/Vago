from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import api_v1_router
from app.core.database import Base, get_db
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import get_current_user_uuid


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """以真实足迹路由和内存 SQLite 验证移动端 HTTP contract。"""
    from app.footprints import models as _footprint_models  # noqa: F401
    from app.travel import models as _travel_models  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    def override_get_db() -> Generator[Session, None, None]:
        with SessionLocal() as session:
            yield session

    async def override_current_user_uuid() -> str:
        return "footprint-api-user"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_uuid] = override_current_user_uuid
    with TestClient(app) as test_client:
        yield test_client


def test_footprint_routes_sync_and_checkin_for_active_trip(client: TestClient):
    """测试：批量轨迹与手动打卡应通过统一 envelope 返回，并绑定进行中 Trip。"""
    trip = client.post(
        "/api/v1/travel/trips",
        json={"title": "新加坡行", "startDate": "2026-09-01", "endDate": "2026-09-05"},
    ).json()["data"]
    client.post(f"/api/v1/travel/trips/{trip['uuid']}/start")
    sample = {
        "clientUuid": "ios-api-sample-1",
        "latitude": 1.3521,
        "longitude": 103.8198,
        "accuracyM": 10.0,
        "recordedAt": "2026-09-04T09:00:00Z",
    }

    sync_response = client.post(
        "/api/v1/footprints/location-samples/sync",
        json={"tripUuid": trip["uuid"], "samples": [sample]},
    )
    locations_response = client.get(f"/api/v1/footprints/trips/{trip['uuid']}/locations")
    checkin_response = client.post(
        "/api/v1/footprints/checkins",
        json={"tripUuid": trip["uuid"], "locationName": "滨海湾花园", "latitude": 1.2816, "longitude": 103.8636},
    )

    assert sync_response.status_code == 200
    assert sync_response.json()["data"]["acceptedCount"] == 1
    assert locations_response.json()["data"][0]["latitude"] == 1.3521
    assert locations_response.json()["data"][0]["recordedAt"].endswith("Z")
    assert checkin_response.json()["data"]["locationName"] == "滨海湾花园"
    assert checkin_response.json()["data"]["checkedAt"].endswith("Z")
