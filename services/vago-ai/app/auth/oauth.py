"""OAuth provider 客户端。

Phase 2 只迁移现有 GitHub 登录能力；后续需要 Apple/微信时再扩展 provider。
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import settings
from app.core.exceptions import AppException

USER_AGENT = "Vago-OAuth/1.0"


@dataclass(frozen=True)
class OAuthUserProfile:
    """统一后的第三方用户资料。"""

    provider: str
    open_id: str
    email: str | None
    nickname: str
    avatar_url: str | None
    access_token: str | None
    expires_at: datetime | None


def normalize_provider(provider: str) -> str:
    """规范化 provider 名称，并限制为当前已迁移的 OAuth provider。"""
    normalized = provider.strip().lower()
    if normalized != "github":
        raise AppException("暂不支持该 OAuth 平台", status_code=400, code="OAUTH_PROVIDER_UNSUPPORTED")
    return normalized


async def fetch_oauth_user_profile(provider: str, auth_code: str, redirect_uri: str) -> OAuthUserProfile:
    """根据 provider 获取统一 OAuth 用户资料。"""
    normalized = normalize_provider(provider)
    if normalized == "github":
        try:
            return await _fetch_github_user_profile(auth_code, redirect_uri)
        except AppException:
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {400, 401, 403}:
                raise AppException("OAuth 授权码无效或已过期", status_code=400, code="OAUTH_CODE_INVALID")
            raise AppException("OAuth 服务调用失败", status_code=502, code="OAUTH_SERVICE_ERROR")
        except httpx.HTTPError:
            raise AppException("OAuth 服务调用失败", status_code=502, code="OAUTH_SERVICE_ERROR")
    raise AppException("暂不支持该 OAuth 平台", status_code=400, code="OAUTH_PROVIDER_UNSUPPORTED")


async def _fetch_github_user_profile(auth_code: str, redirect_uri: str) -> OAuthUserProfile:
    """GitHub OAuth：auth code -> access token -> user/email profile。"""
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise AppException("GitHub OAuth 未完成配置", status_code=500, code="OAUTH_CONFIG_MISSING")

    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_response = await client.post(
            settings.github_oauth_token_url,
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": auth_code,
                "redirect_uri": redirect_uri,
            },
            headers=headers,
        )
        if token_response.status_code in {400, 401, 403}:
            raise AppException("OAuth 授权码无效或已过期", status_code=400, code="OAUTH_CODE_INVALID")
        token_response.raise_for_status()
        token_payload = token_response.json()
        access_token = token_payload.get("access_token")
        if not access_token:
            raise AppException("OAuth 授权码无效或已过期", status_code=400, code="OAUTH_CODE_INVALID")

        auth_headers = {**headers, "Authorization": f"Bearer {access_token}"}
        user_response = await client.get(settings.github_oauth_user_url, headers=auth_headers)
        if user_response.status_code == 401:
            raise AppException("OAuth 授权码无效或已过期", status_code=400, code="OAUTH_CODE_INVALID")
        user_response.raise_for_status()
        user_payload = user_response.json()
        if not user_payload.get("id"):
            raise AppException("OAuth 用户信息为空", status_code=502, code="OAUTH_SERVICE_ERROR")

        email = await _resolve_github_email(client, auth_headers, user_payload.get("email"))
        expires_in = token_payload.get("expires_in")
        expires_at = (
            datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=expires_in)
            if expires_in
            else None
        )

        return OAuthUserProfile(
            provider="github",
            open_id=str(user_payload["id"]),
            email=email,
            nickname=_resolve_github_nickname(user_payload),
            avatar_url=user_payload.get("avatar_url"),
            access_token=access_token,
            expires_at=expires_at,
        )


async def _resolve_github_email(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    primary_email: str | None,
) -> str | None:
    """优先使用 /user email；为空时再读取 GitHub verified 邮箱列表。"""
    if primary_email:
        return primary_email
    try:
        response = await client.get(settings.github_oauth_emails_url, headers=auth_headers)
        response.raise_for_status()
        emails = response.json()
    except httpx.HTTPError:
        return None

    verified_emails = [
        item
        for item in emails
        if item.get("verified") and item.get("email")
    ]
    verified_emails.sort(key=lambda item: not item.get("primary", False))
    return verified_emails[0]["email"] if verified_emails else None


def _resolve_github_nickname(user_payload: dict) -> str:
    """昵称策略保持 Java 侧 name > login > 默认名。"""
    if user_payload.get("name"):
        return user_payload["name"]
    if user_payload.get("login"):
        return user_payload["login"]
    return f"GitHub用户{user_payload['id']}"
