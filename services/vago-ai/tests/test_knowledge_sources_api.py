"""个人知识源 API 测试，覆盖新领域与旧 Guide 社区模型的边界。"""

from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import get_current_user_uuid
from app.knowledge import indexing
from app.knowledge.models import KnowledgeSource
from app.users.models import User


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """使用内存 SQLite 验证新知识源领域，不依赖本地 MySQL。"""
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
    tmp_path,
) -> Generator[TestClient, None, None]:
    """挂载真实路由，并隔离可选索引能力和本地文件目录。"""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    async def override_current_user_uuid() -> str:
        return "knowledge-source-user"

    async def fake_index_source_background(source_uuid: str, user_uuid: str) -> None:
        assert source_uuid
        assert user_uuid == "knowledge-source-user"

    async def fake_delete_source_index_background(source_uuid: str, user_uuid: str) -> None:
        assert source_uuid
        assert user_uuid == "knowledge-source-user"

    monkeypatch.setattr(settings, "knowledge_storage_path", str(tmp_path / "knowledge-storage"))
    monkeypatch.setattr(indexing, "index_source_background", fake_index_source_background)
    monkeypatch.setattr(indexing, "delete_source_index_background", fake_delete_source_index_background)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_uuid] = override_current_user_uuid

    with TestClient(app) as test_client:
        yield test_client


def _seed_current_user(db: Session) -> None:
    db.add(
        User(
            id=1,
            uuid="knowledge-source-user",
            phone="13600102000",
            nickname="Source User",
            created_at=datetime(2026, 8, 31, 9, 0, 0),
            updated_at=datetime(2026, 8, 31, 9, 0, 0),
        )
    )
    db.commit()


def test_text_source_crud_keeps_community_fields_out_of_contract(
    client: TestClient,
    db_session: Session,
):
    """测试：个人知识源只表达用户资料，不携带点赞、发布或作者信息。"""
    _seed_current_user(db_session)

    create_response = client.post(
        "/api/v1/knowledge/sources",
        json={
            "title": "京都散步笔记",
            "sourceType": "TEXT",
            "contentText": "哲学之道适合安排在清晨。",
            "destination": "京都",
            "tags": ["步行", "京都"],
        },
    )

    assert create_response.status_code == 200
    source = create_response.json()["data"]
    assert source["sourceType"] == "TEXT"
    assert source["parseStatus"] == "READY"
    assert source["indexStatus"] == "NOT_INDEXED"
    assert {"likeCount", "liked", "viewCount", "authorUuid", "status", "aiStatus"}.isdisjoint(source)

    update_response = client.put(
        f"/api/v1/knowledge/sources/{source['uuid']}",
        json={"contentText": "哲学之道和南禅寺适合安排在清晨。"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["indexStatus"] == "NOT_INDEXED"

    index_response = client.post(f"/api/v1/knowledge/sources/{source['uuid']}/index")
    assert index_response.status_code == 200
    assert index_response.json()["data"]["indexStatus"] == "PENDING"


def test_index_unavailable_returns_displayable_message(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """测试：RAG 关闭时，前端可直接使用统一错误消息提示用户。"""
    _seed_current_user(db_session)
    source_response = client.post(
        "/api/v1/knowledge/sources",
        json={"title": "曼谷笔记", "sourceType": "TEXT", "contentText": "建议避开雨季。"},
    )
    monkeypatch.setattr(settings, "rag_enabled", False)

    index_response = client.post(
        f"/api/v1/knowledge/sources/{source_response.json()['data']['uuid']}/index"
    )

    assert index_response.status_code == 503
    assert index_response.json()["code"] == "RAG_UNAVAILABLE"
    assert index_response.json()["message"] == "当前环境未启用语义索引能力"


def test_markdown_upload_creates_file_source_and_delete_removes_asset(
    client: TestClient,
    db_session: Session,
    tmp_path,
):
    """测试：Markdown 文件需保留原件，同时把 UTF-8 文本存入个人知识源。"""
    _seed_current_user(db_session)

    response = client.post(
        "/api/v1/knowledge/sources/files",
        data={"destination": "北海道", "tags": '["雪景", "咖啡"]'},
        files={"file": ("sapporo.md", "# 札幌\n早晨去二条市场。", "text/markdown")},
    )

    assert response.status_code == 200
    source = response.json()["data"]
    assert source["sourceType"] == "FILE"
    assert source["mimeType"] == "text/markdown"
    assert source["originalFilename"] == "sapporo.md"
    assert "二条市场" in source["contentText"]

    stored_path = tmp_path / "knowledge-storage" / source["storageKey"]
    assert stored_path.exists()
    delete_response = client.delete(f"/api/v1/knowledge/sources/{source['uuid']}")
    assert delete_response.status_code == 200
    assert not stored_path.exists()


def test_source_detail_rejects_another_users_source(client: TestClient, db_session: Session):
    """测试：个人知识源必须按 user_uuid 隔离，不能跨用户读取。"""
    _seed_current_user(db_session)
    db_session.add(
        KnowledgeSource(
            uuid="another-user-source",
            user_uuid="another-user",
            title="别人的旅行资料",
            source_type="TEXT",
            mime_type="text/plain",
            content_text="不应被当前用户读取。",
            parse_status="READY",
            index_status="NOT_INDEXED",
            created_at=datetime(2026, 8, 31, 9, 0, 0),
            updated_at=datetime(2026, 8, 31, 9, 0, 0),
        )
    )
    db_session.commit()

    response = client.get("/api/v1/knowledge/sources/another-user-source")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
