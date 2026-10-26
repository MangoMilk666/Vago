"""需要本机 Redis 的 Web Session 集成测试。"""

import hashlib
import os
import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import api_v1_router
from app.auth.web_session import COOKIE_NAME, SESSION_PREFIX
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.exceptions import register_exception_handlers
from app.users.models import User


@pytest.mark.skipif(os.getenv("VAGO_AUTH_REDIS_TEST") != "1", reason="需要显式启用本机 Redis 集成测试")
def test_web_login_session_csrf_and_logout(monkeypatch: pytest.MonkeyPatch):
    """测试：真实 Redis Session 登录后可恢复、拒绝跨站写入并在退出后失效。"""
    from app.users import models as _models  # noqa: F401

    monkeypatch.setattr(settings, "jwt_secret_key", "integration-test-secret")

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    def database_session():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = database_session
    redis = Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db, decode_responses=True)
    phone = f"139{secrets.randbelow(100_000_000):08d}"
    code_key = f"vago:sms:code:{phone}"
    limit_key = f"vago:sms:limit:{phone}"
    redis.setex(code_key, 300, "123456")
    origin = "http://localhost:5173"
    session_key = None
    ios_refresh_key = None

    try:
        with TestClient(app, base_url="https://testserver") as client:
            rejected = client.post(
                "/api/v1/auth/login/phone",
                json={"phone": phone, "code": "123456", "clientType": "web"},
                headers={"Origin": "https://evil.example"},
            )
            assert rejected.status_code == 403

            browser_native_request = client.post(
                "/api/v1/auth/login/phone",
                json={"phone": phone, "code": "123456", "clientType": "ios"},
                headers={"Origin": origin},
            )
            assert browser_native_request.status_code == 403

            ios_login = client.post(
                "/api/v1/auth/login/phone",
                json={"phone": phone, "code": "123456", "clientType": "ios", "deviceId": "ios-session-test"},
            )
            assert ios_login.status_code == 200
            ios_token = ios_login.json()["data"]["accessToken"]
            ios_user_uuid = ios_login.json()["data"]["userInfo"]["uuid"]
            ios_refresh_key = f"vago:token:rt:{ios_user_uuid}:ios-session-test"
            assert client.get("/api/v1/user/profile", headers={"Authorization": f"Bearer {ios_token}"}).status_code == 200
            assert client.cookies.get(COOKIE_NAME) is None

            redis.setex(code_key, 300, "123456")
            login = client.post(
                "/api/v1/auth/login/phone",
                json={"phone": phone, "code": "123456", "clientType": "web"},
                headers={"Origin": origin},
            )
            assert login.status_code == 200
            assert "accessToken" not in login.json()["data"]
            assert "refreshToken" not in login.json()["data"]
            cookie = client.cookies.get(COOKIE_NAME)
            assert cookie
            session_key = f"{SESSION_PREFIX}{hashlib.sha256(cookie.encode()).hexdigest()}"
            assert redis.exists(session_key)

            current = client.get("/api/v1/auth/session")
            assert current.status_code == 200
            csrf = current.json()["data"]["csrfToken"]
            assert client.get("/api/v1/user/profile").status_code == 200

            path = "/api/v1/user/profile"
            payload = {"nickname": "会话测试"}
            assert client.put(path, json=payload, headers={"Origin": origin}).status_code == 403
            assert client.put(path, json=payload, headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf}).status_code == 403
            assert client.put(path, json=payload, headers={"Origin": origin, "X-CSRF-Token": csrf}).status_code == 200

            # 如果显式提供无效 Bearer，即使同时携带有效 Cookie 也必须拒绝。
            assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401

            redis.setex(code_key, 300, "123456")
            second_login = client.post(
                "/api/v1/auth/login/phone",
                json={"phone": phone, "code": "123456", "clientType": "web"},
                headers={"Origin": origin},
            )
            assert second_login.status_code == 200
            assert not redis.exists(session_key)
            cookie = client.cookies.get(COOKIE_NAME)
            session_key = f"{SESSION_PREFIX}{hashlib.sha256(cookie.encode()).hexdigest()}"
            assert redis.exists(session_key)
            csrf = client.get("/api/v1/auth/session").json()["data"]["csrfToken"]

            logout = client.post("/api/v1/auth/logout", headers={"Origin": origin, "X-CSRF-Token": csrf})
            assert logout.status_code == 200
            assert not redis.exists(session_key)
            assert client.get("/api/v1/auth/session").status_code == 401

            for account_status, expected_code in ((2, "ACCOUNT_BANNED"), (3, "ACCOUNT_CANCELLING")):
                # 测试：账号状态变化后，当前 Web Session 立即失效并返回明确原因。
                with session_factory() as db:
                    user = db.query(User).filter(User.uuid == ios_user_uuid).one()
                    user.status = 1
                    db.commit()
                redis.setex(code_key, 300, "123456")
                assert client.post(
                    "/api/v1/auth/login/phone",
                    json={"phone": phone, "code": "123456", "clientType": "web"},
                    headers={"Origin": origin},
                ).status_code == 200
                cookie = client.cookies.get(COOKIE_NAME)
                session_key = f"{SESSION_PREFIX}{hashlib.sha256(cookie.encode()).hexdigest()}"
                with session_factory() as db:
                    user = db.query(User).filter(User.uuid == ios_user_uuid).one()
                    user.status = account_status
                    db.commit()
                rejected_session = client.get("/api/v1/auth/session")
                assert rejected_session.status_code == 403
                assert rejected_session.json()["code"] == expected_code
                assert not redis.exists(session_key)
                assert client.get("/api/v1/auth/session").status_code == 401
    finally:
        redis.delete(code_key, limit_key)
        if ios_refresh_key:
            redis.delete(ios_refresh_key)
        if session_key:
            redis.delete(session_key)
        engine.dispose()
