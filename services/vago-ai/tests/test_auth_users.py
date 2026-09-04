from datetime import datetime

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import service as auth_service
from app.auth.oauth import OAuthUserProfile
from app.auth.schemas import PhoneLoginRequest
from app.users.models import User, UserOauthBinding, UserSettings
from app.users.schemas import UserProfileUpdate, UserSettingsUpdate
from app.users import service as users_service
from app.users.service import (
    ACTIVE_STATUS,
    CANCELLING_STATUS,
    create_default_settings,
    build_profile,
    cancel_account,
    get_settings_response,
    mask_phone,
    revoke_cancel_account,
    update_profile,
    update_settings,
)


@pytest.fixture()
def db_session() -> Session:
    """用内存 SQLite 验证领域服务，不依赖本地 MySQL。"""
    from app.core.database import Base
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


def _seed_user(db: Session, *, user_id: int, uuid: str, phone: str, nickname: str) -> User:
    user = User(
        id=user_id,
        uuid=uuid,
        phone=phone,
        nickname=nickname,
        created_at=datetime(2026, 8, 30, 9, 0, 0),
        updated_at=datetime(2026, 8, 30, 9, 0, 0),
    )
    db.add(user)
    db.add(UserSettings(user_id=user_id))
    db.flush()
    return user


class FakeRedis:
    """测试用 Redis stub，只覆盖 Phase 2 账号生命周期所需命令。"""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    async def exists(self, key: str) -> bool:
        return key in self.values

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


def test_mask_phone_keeps_java_profile_display_rule():
    """测试：手机号脱敏规则应与 Java UserServiceImpl.toUserVO 保持一致。"""
    assert mask_phone("13800101000") == "138****1000"
    assert mask_phone("123456") == "123456"
    assert mask_phone(None) is None


def test_profile_and_settings_are_isolated_by_current_user(db_session: Session):
    """测试：用户资料和设置更新必须只影响当前 JWT 指向的用户。"""
    alice = _seed_user(
        db_session,
        user_id=1,
        uuid="alice-uuid",
        phone="13800101000",
        nickname="Alice",
    )
    bob = _seed_user(
        db_session,
        user_id=2,
        uuid="bob-uuid",
        phone="13900101000",
        nickname="Bob",
    )
    db_session.add(UserOauthBinding(id=1, user_id=alice.id, provider="github", open_id="alice-gh"))
    db_session.commit()

    alice_profile = update_profile(
        db_session,
        "alice-uuid",
        UserProfileUpdate(nickname="旅行者 Alice", email="alice@example.com"),
    )
    alice_settings = update_settings(
        db_session,
        "alice-uuid",
        UserSettingsUpdate(gpsMode=2, fogUnlockRadiusM=500, notificationCheckin=False),
    )
    bob_profile = build_profile(db_session, bob)
    bob_settings = get_settings_response(db_session, "bob-uuid")

    assert alice_profile.nickname == "旅行者 Alice"
    assert alice_profile.email == "alice@example.com"
    assert alice_profile.phone == "138****1000"
    assert alice_profile.oauth_providers == ["github"]
    assert alice_settings.gps_mode == 2
    assert alice_settings.fog_unlock_radius_m == 500
    assert alice_settings.notification_checkin is False

    assert bob_profile.nickname == "Bob"
    assert bob_profile.email is None
    assert bob_settings.gps_mode == 1
    assert bob_settings.fog_unlock_radius_m == 300
    assert bob_settings.notification_checkin is True


def test_request_schemas_accept_legacy_frontend_field_names(db_session: Session):
    """测试：FastAPI 兼容当前 React user.js 仍在发送的字段名。"""
    login_payload = PhoneLoginRequest(phone="13800101000", smsCode="123456")
    # code/smsCode字段名兼容
    assert login_payload.code == "123456"

    user = _seed_user(
        db_session,
        user_id=3,
        uuid="avatar-user-uuid",
        phone="13600101000",
        nickname="Avatar User",
    )
    profile = update_profile(
        db_session,
        user.uuid,
        UserProfileUpdate.model_validate({"avatarUuid": "oss/avatar.png"}),
    )
    # avatarUrl/avatarUuid兼容
    assert profile.avatar_url == "oss/avatar.png"


def test_default_settings_follow_java_registration_behavior(db_session: Session):
    """测试：新注册用户的默认设置应延续 Java UserServiceImpl 默认值。"""
    settings = create_default_settings(db_session, user_id=99)

    assert settings.gps_mode == 1
    assert settings.fog_unlock_radius_m == 200
    assert settings.default_visibility == 0
    assert settings.notification_checkin == 1


def test_token_pair_keeps_legacy_jwt_claim_names(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """测试：FastAPI 签发的 JWT payload 需要保留 Java 侧 userUuid/userId 字段。"""
    monkeypatch.setattr(auth_service.settings, "jwt_secret_key", "test-secret")
    monkeypatch.setattr(auth_service.settings, "jwt_access_token_ttl_seconds", 60)
    monkeypatch.setattr(auth_service.settings, "jwt_refresh_token_ttl_seconds", 120)
    user = _seed_user(
        db_session,
        user_id=10,
        uuid="token-user-uuid",
        phone="13700101000",
        nickname="Token User",
    )

    token_pair = auth_service.create_token_pair(user)
    access_payload = jwt.decode(token_pair.access_token, "test-secret", algorithms=["HS256"])
    refresh_payload = jwt.decode(token_pair.refresh_token, "test-secret", algorithms=["HS256"])

    assert access_payload["userUuid"] == "token-user-uuid"
    assert access_payload["userId"] == 10
    assert access_payload["typ"] == "access"
    assert refresh_payload["typ"] == "refresh"
    assert token_pair.expires_in == 60


@pytest.mark.anyio
async def test_phone_logins_keep_refresh_tokens_for_separate_devices(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """测试：同一账号的 Web 与 iOS 登录应保留各自独立的刷新会话。"""
    fake_redis = FakeRedis()
    monkeypatch.setattr(auth_service.settings, "jwt_secret_key", "test-secret")

    async def fake_validate_sms_code(phone: str, code: str) -> None:
        assert phone == "13800101000"
        assert code == "123456"

    async def fake_get_redis_client() -> FakeRedis:
        return fake_redis

    monkeypatch.setattr(auth_service, "validate_sms_code", fake_validate_sms_code)
    monkeypatch.setattr(auth_service, "get_redis_client", fake_get_redis_client)

    ios_response = await auth_service.login_by_phone(
        db_session, "13800101000", "123456", "ios", "ios-installation-id"
    )
    web_response = await auth_service.login_by_phone(
        db_session, "13800101000", "123456", "web", "web-browser-id"
    )

    assert ios_response.session_id == "ios-installation-id"
    assert web_response.session_id == "web-browser-id"
    assert {key.rsplit(":", maxsplit=1)[-1] for key in fake_redis.values} == {
        "ios-installation-id",
        "web-browser-id",
    }
    assert len(fake_redis.values) == 2


@pytest.mark.anyio
async def test_oauth_login_creates_user_and_binding(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """测试：OAuth 首次登录应创建用户、默认设置和 provider 绑定。"""
    monkeypatch.setattr(auth_service.settings, "jwt_secret_key", "test-secret")

    async def fake_fetch_oauth_user_profile(provider: str, auth_code: str, redirect_uri: str):
        assert provider == "github"
        assert auth_code == "code"
        assert redirect_uri == "http://localhost:5173/login"
        return OAuthUserProfile(
            provider="github",
            open_id="10001",
            email="oauth@example.com",
            nickname="OAuth User",
            avatar_url="https://avatar.example.com/u.png",
            access_token="github-token",
            expires_at=None,
        )

    async def fake_store_refresh_token(user_uuid: str, session_id: str, refresh_token: str) -> None:
        assert user_uuid
        assert session_id
        assert refresh_token

    monkeypatch.setattr(auth_service, "fetch_oauth_user_profile", fake_fetch_oauth_user_profile)
    monkeypatch.setattr(auth_service, "store_refresh_token", fake_store_refresh_token)

    response = await auth_service.login_by_oauth(
        db_session,
        "github",
        "code",
        "http://localhost:5173/login",
    )

    binding = db_session.query(UserOauthBinding).one()
    assert response.is_new_user is True
    assert response.user_info.email == "oauth@example.com"
    assert response.user_info.oauth_providers == ["github"]
    assert binding.provider == "github"
    assert binding.open_id == "10001"


@pytest.mark.anyio
async def test_oauth_login_binds_existing_user_by_email(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """测试：OAuth 邮箱命中老用户时应绑定老账号，不创建重复用户。"""
    monkeypatch.setattr(auth_service.settings, "jwt_secret_key", "test-secret")
    existing = _seed_user(
        db_session,
        user_id=20,
        uuid="email-user-uuid",
        phone="13500101000",
        nickname="已存在用户",
    )
    existing.email = "same@example.com"
    db_session.commit()

    async def fake_fetch_oauth_user_profile(provider: str, auth_code: str, redirect_uri: str):
        return OAuthUserProfile(
            provider="github",
            open_id="20002",
            email="same@example.com",
            nickname="GitHub Name",
            avatar_url="https://avatar.example.com/old.png",
            access_token="github-token",
            expires_at=None,
        )

    async def fake_store_refresh_token(user_uuid: str, session_id: str, refresh_token: str) -> None:
        assert user_uuid == "email-user-uuid"
        assert session_id

    monkeypatch.setattr(auth_service, "fetch_oauth_user_profile", fake_fetch_oauth_user_profile)
    monkeypatch.setattr(auth_service, "store_refresh_token", fake_store_refresh_token)

    response = await auth_service.login_by_oauth(db_session, "github", "code", "redirect")

    assert response.is_new_user is False
    assert response.user_info.uuid == "email-user-uuid"
    assert db_session.query(User).count() == 1
    assert db_session.query(UserOauthBinding).count() == 1


@pytest.mark.anyio
async def test_cancel_and_revoke_account_updates_status_and_cancel_key(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """测试：账号注销与撤销应围绕当前用户状态和 Redis 宽限期 key 流转。"""
    fake_redis = FakeRedis()
    user = _seed_user(
        db_session,
        user_id=30,
        uuid="cancel-user-uuid",
        phone="13400101000",
        nickname="Cancel User",
    )

    async def fake_validate_sms_code(phone: str, code: str) -> None:
        assert phone == "13400101000"
        assert code == "123456"

    async def fake_get_redis_client():
        return fake_redis

    monkeypatch.setattr(auth_service, "validate_sms_code", fake_validate_sms_code)
    monkeypatch.setattr(users_service, "get_redis_client", fake_get_redis_client)

    result = await cancel_account("cancel-user-uuid", "123456", db_session)
    db_session.refresh(user)

    assert result.cancel_deadline
    assert user.status == CANCELLING_STATUS
    assert "vago:cancel:cancel-user-uuid" in fake_redis.values

    await revoke_cancel_account("cancel-user-uuid", db_session)
    db_session.refresh(user)

    assert user.status == ACTIVE_STATUS
    assert "vago:cancel:cancel-user-uuid" not in fake_redis.values
