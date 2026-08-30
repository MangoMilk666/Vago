from datetime import datetime

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import service as auth_service
from app.auth.schemas import PhoneLoginRequest
from app.users.models import User, UserOauthBinding, UserSettings
from app.users.schemas import UserProfileUpdate, UserSettingsUpdate
from app.users.service import (
    create_default_settings,
    build_profile,
    get_settings_response,
    mask_phone,
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
