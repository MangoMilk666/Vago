from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AppException
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
