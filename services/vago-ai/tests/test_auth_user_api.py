from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import api_v1_router
from app.auth import service as auth_service
from app.auth.oauth import OAuthUserProfile
from app.core.database import Base, get_db
from app.core.exceptions import register_exception_handlers
from app.dependencies.auth import get_current_user_uuid
from app.users import service as users_service
from app.users.models import User, UserSettings


class FakeRedis:
    """API 测试用 Redis stub，避免依赖本地 Redis。"""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    async def exists(self, key: str) -> bool:
        return key in self.values

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """路由层测试使用内存 SQLite，避免依赖本地 MySQL 服务。"""
    from app.users import models as _models  # noqa: F401

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
    """挂载真实 v1 router，并替换请求级数据库与当前用户依赖。"""
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


def _seed_current_user(db: Session) -> User:
    user = User(
        id=1,
        uuid="api-user-uuid",
        phone="13800101000",
        nickname="API User",
        created_at=datetime(2026, 8, 30, 9, 0, 0),
        updated_at=datetime(2026, 8, 30, 9, 0, 0),
    )
    db.add(user)
    db.add(
        UserSettings(
            user_id=1,
            gps_mode=1,
            fog_unlock_radius_m=200,
            default_visibility=0,
            notification_checkin=1,
        )
    )
    db.commit()
    return user


def test_legacy_user_profile_api_returns_java_compatible_envelope(
    client: TestClient,
    db_session: Session,
):
    """测试：兼容路径 /api/v1/user/profile 应返回 Java Result 风格 envelope。"""
    _seed_current_user(db_session)

    response = client.get("/api/v1/user/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["message"] == "success"
    assert body["data"]["uuid"] == "api-user-uuid"
    assert body["data"]["phone"] == "138****1000"
    assert body["data"]["avatarUrl"] is None


def test_legacy_user_profile_api_accepts_avatar_uuid(
    client: TestClient,
    db_session: Session,
):
    """测试：当前 React 仍发送 avatarUuid，FastAPI 兼容入口应能接收并回传 avatarUrl。"""
    _seed_current_user(db_session)

    response = client.put(
        "/api/v1/user/profile",
        json={"nickname": "新的旅行者", "avatarUuid": "oss/avatar.png"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "资料已更新"
    assert body["data"]["nickname"] == "新的旅行者"
    assert body["data"]["avatarUrl"] == "oss/avatar.png"


def test_legacy_user_settings_api_uses_boolean_notification(
    client: TestClient,
    db_session: Session,
):
    """测试：用户设置接口应保持 Java VO 中 notificationCheckin 的 boolean 语义。"""
    _seed_current_user(db_session)

    response = client.put(
        "/api/v1/user/settings",
        json={"gpsMode": 2, "fogUnlockRadiusM": 500, "notificationCheckin": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["gpsMode"] == 2
    assert body["data"]["fogUnlockRadiusM"] == 500
    assert body["data"]["notificationCheckin"] is False


def test_legacy_register_api_accepts_sms_code_and_nickname(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """测试：注册接口应兼容 React 当前发送的 smsCode 和 nickname。"""
    monkeypatch.setattr(auth_service.settings, "jwt_secret_key", "test-secret")
    monkeypatch.setattr(auth_service.settings, "jwt_access_token_ttl_seconds", 60)
    monkeypatch.setattr(auth_service.settings, "jwt_refresh_token_ttl_seconds", 120)

    async def fake_validate_sms_code(phone: str, code: str) -> None:
        # 测试只验证 API contract，短信验证码缓存由 service 单测覆盖。
        assert phone == "13700101000"
        assert code == "123456"

    async def fake_store_refresh_token(user_uuid: str, refresh_token: str) -> None:
        assert user_uuid
        assert refresh_token

    monkeypatch.setattr(auth_service, "validate_sms_code", fake_validate_sms_code)
    monkeypatch.setattr(auth_service, "store_refresh_token", fake_store_refresh_token)

    response = client.post(
        "/api/v1/user/register",
        json={"phone": "13700101000", "smsCode": "123456", "nickname": "注册用户"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "注册成功"
    assert body["data"]["accessToken"]
    assert body["data"]["refreshToken"]
    assert body["data"]["isNewUser"] is True
    assert body["data"]["userInfo"]["nickname"] == "注册用户"


def test_legacy_oauth_api_returns_login_vo_shape(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """测试：OAuth 登录兼容路径应返回 Java LoginVO 字段结构。"""
    monkeypatch.setattr(auth_service.settings, "jwt_secret_key", "test-secret")

    async def fake_fetch_oauth_user_profile(provider: str, auth_code: str, redirect_uri: str):
        assert provider == "github"
        return OAuthUserProfile(
            provider="github",
            open_id="api-oauth-open-id",
            email="api-oauth@example.com",
            nickname="API OAuth",
            avatar_url=None,
            access_token="github-token",
            expires_at=None,
        )

    async def fake_store_refresh_token(user_uuid: str, refresh_token: str) -> None:
        assert user_uuid

    monkeypatch.setattr(auth_service, "fetch_oauth_user_profile", fake_fetch_oauth_user_profile)
    monkeypatch.setattr(auth_service, "store_refresh_token", fake_store_refresh_token)

    response = client.post(
        "/api/v1/user/login/oauth",
        json={
            "provider": "github",
            "authCode": "oauth-code",
            "redirectUri": "http://localhost:5173/login",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["isNewUser"] is True
    assert body["data"]["userInfo"]["email"] == "api-oauth@example.com"
    assert body["data"]["userInfo"]["oauthProviders"] == ["github"]


def test_legacy_account_cancel_and_revoke_paths(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """测试：账号注销与撤销兼容路径应完成状态流转。"""
    fake_redis = FakeRedis()
    user = _seed_current_user(db_session)

    async def fake_validate_sms_code(phone: str, code: str) -> None:
        assert phone == "13800101000"
        assert code == "123456"

    async def fake_get_redis_client():
        return fake_redis

    monkeypatch.setattr(auth_service, "validate_sms_code", fake_validate_sms_code)
    monkeypatch.setattr(users_service, "get_redis_client", fake_get_redis_client)

    cancel_response = client.request(
        "DELETE",
        "/api/v1/user/account",
        json={"smsCode": "123456", "reason": "测试注销"},
    )
    db_session.refresh(user)

    assert cancel_response.status_code == 200
    assert cancel_response.json()["message"] == "注销申请已提交，7日内可撤销"
    assert cancel_response.json()["data"]["cancelDeadline"]
    assert user.status == 3

    revoke_response = client.post("/api/v1/user/account/cancel-revoke")
    db_session.refresh(user)

    assert revoke_response.status_code == 200
    assert revoke_response.json()["message"] == "注销申请已撤销，账号恢复正常"
    assert user.status == 1
