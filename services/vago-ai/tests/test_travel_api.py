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
def db_session() -> Generator[Session, None, None]:
    """路由层测试使用内存 SQLite，避免依赖本地 MySQL。"""
    from app.travel import models as _models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    with SessionLocal() as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """挂载真实 v1 router，并替换 DB/current user 依赖。"""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    async def override_current_user_uuid() -> str:
        return "api-user-uuid"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_uuid] = override_current_user_uuid

    with TestClient(app) as test_client:
        yield test_client


def test_travel_trip_api_returns_java_compatible_envelope(client: TestClient):
    """测试：Trip API 应返回 Java Result 风格 envelope 和 camelCase 字段。"""
    create_response = client.post(
        "/api/v1/travel/trips",
        json={
            "title": "大阪行",
            "destination": "Osaka",
            "startDate": "2026-09-01",
            "endDate": "2026-09-03",
            "coverImageKey": "cover/osaka.png",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert create_response.json()["message"] == "行程创建成功"
    assert created["uuid"]
    assert created["coverImageKey"] == "cover/osaka.png"

    list_response = client.get("/api/v1/travel/trips")

    assert list_response.status_code == 200
    assert list_response.json()["code"] == 200
    assert list_response.json()["data"][0]["title"] == "大阪行"


def test_travel_plan_days_and_convert_api(client: TestClient):
    """测试：Plan / Itinerary API 应支持每日安排更新并转换为 Trip。"""
    plan_response = client.post(
        "/api/v1/travel/plans",
        json={
            "title": "北海道草稿",
            "destination": "Hokkaido",
            "startDate": "2026-12-01",
            "endDate": "2026-12-02",
            "budget": "5000.00",
        },
    )
    plan_uuid = plan_response.json()["data"]["uuid"]

    update_day_response = client.put(
        f"/api/v1/travel/plans/{plan_uuid}/days/1",
        json={
            "transportation": "JR",
            "spots": [
                {"name": "小樽运河", "category": 0, "durationMinutes": 90},
                {"name": "札幌拉面", "category": 1},
            ],
        },
    )

    assert update_day_response.status_code == 200
    day = update_day_response.json()["data"]
    assert day["dayIndex"] == 1
    assert [spot["sortOrder"] for spot in day["spots"]] == [0, 1]

    convert_response = client.post(f"/api/v1/travel/plans/{plan_uuid}/convert")

    assert convert_response.status_code == 200
    trip_uuid = convert_response.json()["data"]["uuid"]

    trip_days_response = client.get(f"/api/v1/travel/trips/{trip_uuid}/days")

    assert trip_days_response.status_code == 200
    assert trip_days_response.json()["data"][0]["spots"][0]["name"] == "小樽运河"
