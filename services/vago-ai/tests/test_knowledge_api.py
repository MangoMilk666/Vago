from collections.abc import Generator
from datetime import datetime

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
from app.knowledge import service as knowledge_service
from app.knowledge.models import Guide
from app.users.models import User


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Knowledge API 测试使用内存 SQLite，避免依赖本地 MySQL。"""
    from app.knowledge import models as _knowledge_models  # noqa: F401
    from app.users import models as _user_models  # noqa: F401

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
def client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """挂载真实 v1 router，并替换 DB/current user/后台索引依赖。"""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    async def override_current_user_uuid() -> str:
        return "knowledge-user-uuid"

    async def fake_index_guide_background(guide_uuid: str, user_uuid: str) -> None:
        assert guide_uuid
        assert user_uuid == "knowledge-user-uuid"

    async def fake_delete_guide_vectors_background(guide_uuid: str, user_uuid: str) -> None:
        assert guide_uuid
        assert user_uuid == "knowledge-user-uuid"

    monkeypatch.setattr(knowledge_service, "index_guide_background", fake_index_guide_background)
    monkeypatch.setattr(
        knowledge_service,
        "delete_guide_vectors_background",
        fake_delete_guide_vectors_background,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_uuid] = override_current_user_uuid

    with TestClient(app) as test_client:
        yield test_client


def _seed_current_user(db: Session) -> None:
    db.add(
        User(
            id=1,
            uuid="knowledge-user-uuid",
            phone="13600101000",
            nickname="Knowledge User",
            created_at=datetime(2026, 8, 31, 9, 0, 0),
            updated_at=datetime(2026, 8, 31, 9, 0, 0),
        )
    )
    db.commit()


def test_knowledge_guide_crud_keeps_legacy_response_shape(
    client: TestClient,
    db_session: Session,
):
    """测试：个人攻略迁入 Knowledge 后仍保持旧 GuideVO 字段形态。"""
    _seed_current_user(db_session)

    create_response = client.post(
        "/api/v1/knowledge/guides",
        json={
            "title": "京都寺社笔记",
            "destination": "京都",
            "content": "清水寺和祇园适合放在同一天。",
            "tags": ["京都", "寺庙"],
            "imageKeys": ["guides/kyoto-1.png"],
            "status": 1,
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["uuid"]
    assert created["imageKeys"] == ["guides/kyoto-1.png"]
    assert created["aiStatus"] == 0
    assert created["authorNickname"] == "Knowledge User"

    list_response = client.get("/api/v1/knowledge/guides/mine")

    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["title"] == "京都寺社笔记"

    update_response = client.put(
        f"/api/v1/knowledge/guides/{created['uuid']}",
        json={"status": 0, "tags": ["草稿"]},
    )

    assert update_response.status_code == 200
    assert update_response.json()["data"]["status"] == 0
    assert update_response.json()["data"]["aiStatus"] is None

    delete_response = client.delete(f"/api/v1/knowledge/guides/{created['uuid']}")

    assert delete_response.status_code == 200
    assert db_session.query(Guide).filter(Guide.uuid == created["uuid"]).one().deleted_at is not None


def test_knowledge_guide_index_rejects_draft(client: TestClient, db_session: Session):
    """测试：草稿知识源不能进入 RAG 索引队列。"""
    _seed_current_user(db_session)

    create_response = client.post(
        "/api/v1/knowledge/guides",
        json={
            "title": "大阪草稿",
            "destination": "大阪",
            "content": "这篇还没整理完。",
            "status": 0,
        },
    )
    guide_uuid = create_response.json()["data"]["uuid"]

    index_response = client.post(f"/api/v1/knowledge/guides/{guide_uuid}/index")

    assert index_response.status_code == 400
    assert index_response.json()["code"] == "PARAM_INVALID"
