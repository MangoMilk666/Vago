from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AppException
from app.dependencies.rate_limit import should_rate_limit_path
from app.main import create_app


def test_settings_keep_legacy_provider_fallbacks():
    """配置迁移后仍保留旧 Provider fallback 规则。"""
    settings = Settings(
        openai_api_key="openai-key",
        embed_api_key="",
        embed_base_url="",
        llm_api_key="",
        llm_base_url="",
    )

    assert settings.get_llm_api_key() == "openai-key"
    assert settings.get_embed_api_key() == "openai-key"
    assert settings.get_llm_base_url() is None


def test_settings_build_database_url_from_mysql_parts():
    """数据库连接应由分开的 MySQL 配置字段构造。"""
    settings = Settings(
        mysql_host="db.internal",
        mysql_port=3307,
        mysql_db="vago_test",
        mysql_user="vago_user",
        mysql_password="p@ss/word",
        mysql_charset="utf8mb4",
    )

    url = settings.build_database_url()

    assert url.drivername == "mysql+pymysql"
    assert url.host == "db.internal"
    assert url.port == 3307
    assert url.database == "vago_test"
    assert url.username == "vago_user"
    assert url.password == "p@ss/word"
    assert url.query["charset"] == "utf8mb4"


def test_health_endpoint_uses_app_metadata():
    """应用工厂创建的 app 应正常暴露健康检查接口。"""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Vago API"


def test_app_exception_handler_returns_stable_envelope():
    """业务异常应返回稳定 JSON envelope，方便 Web / iOS 共用错误处理。"""
    app = create_app()

    @app.get("/boom")
    async def boom():
        raise AppException("phase1 test", code="PHASE1_TEST")

    client = TestClient(app)

    response = client.get("/boom")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "code": "PHASE1_TEST",
        "message": "phase1 test",
    }


def test_rate_limiter_only_protects_expensive_capability_paths():
    """测试：旅行与足迹读取不应与 AI、向量索引共用严格限流窗口。"""
    assert should_rate_limit_path("/api/v1/ai/chat") is True
    assert should_rate_limit_path("/api/v1/ai/chat/stream") is True
    assert should_rate_limit_path("/api/v1/knowledge/sources/source-uuid/index") is True
    assert should_rate_limit_path("/api/v1/travel/trips") is False
    assert should_rate_limit_path("/api/v1/footprints/trips/trip-uuid/locations") is False
