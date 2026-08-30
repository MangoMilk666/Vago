"""认证领域业务服务。"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from sqlalchemy.orm import Session

from app.auth.oauth import OAuthUserProfile, fetch_oauth_user_profile, normalize_provider
from app.auth.schemas import LoginResponse, SmsSendResponse, TokenPair
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.redis import get_redis_client
from app.users.models import User, UserOauthBinding
from app.users.service import (
    build_profile,
    create_default_settings,
    ensure_user_can_login,
    get_user_by_email,
    get_user_by_phone,
    get_user_by_uuid,
)

logger = logging.getLogger(__name__)

SMS_CODE_PREFIX = "vago:sms:code:"
SMS_LIMIT_PREFIX = "vago:sms:limit:"
REFRESH_TOKEN_PREFIX = "vago:token:rt:"
TOKEN_BLACKLIST_PREFIX = "vago:token:bl:"


def _utc_now() -> datetime:
    """统一生成 UTC 时间，避免 token exp 受本地时区影响。"""
    return datetime.now(timezone.utc)


def _require_jwt_secret() -> str:
    """读取 JWT 密钥；未配置时显式报错，避免签出不可验证 token。"""
    if not settings.jwt_secret_key:
        raise AppException("JWT 密钥未配置", status_code=500, code="JWT_SECRET_MISSING")
    return settings.jwt_secret_key


def _strip_bearer_prefix(token: str) -> str:
    """兼容 Authorization: Bearer xxx 与前端当前直接传 token 两种形式。"""
    if token.lower().startswith("bearer "):
        return token[7:]
    return token


def _sign_token(user: User, expires_in: int, token_kind: str) -> str:
    """签发与 Java payload 兼容的 HS256 JWT。"""
    now = _utc_now()
    payload = {
        "userUuid": user.uuid,
        "userId": user.id,
        "typ": token_kind,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, _require_jwt_secret(), algorithm="HS256")


def create_token_pair(user: User) -> TokenPair:
    """为用户签发 access/refresh token 对。"""
    access_token = _sign_token(user, settings.jwt_access_token_ttl_seconds, "access")
    refresh_token = _sign_token(user, settings.jwt_refresh_token_ttl_seconds, "refresh")
    return TokenPair(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=settings.jwt_access_token_ttl_seconds,
    )


async def store_refresh_token(user_uuid: str, refresh_token: str) -> None:
    """保存 refresh token，保持 Java 侧单用户单刷新 token 语义。"""
    redis = await get_redis_client()
    await redis.setex(
        f"{REFRESH_TOKEN_PREFIX}{user_uuid}",
        settings.jwt_refresh_token_ttl_seconds,
        refresh_token,
    )


async def send_sms_code(phone: str) -> SmsSendResponse:
    """生成并缓存短信验证码；真实短信网关后续再接入。"""
    redis = await get_redis_client()
    limit_key = f"{SMS_LIMIT_PREFIX}{phone}"
    if await redis.exists(limit_key):
        raise AppException("验证码发送过于频繁", status_code=429, code="SMS_RATE_LIMITED")
    # 不足 6 位时在前面补 0
    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis.setex(f"{SMS_CODE_PREFIX}{phone}", settings.sms_code_ttl_seconds, code)
    await redis.setex(limit_key, settings.sms_limit_ttl_seconds, "1")
    logger.info("开发环境短信验证码 phone=%s code=%s", phone, code)
    return SmsSendResponse(expireSeconds=settings.sms_code_ttl_seconds)


async def validate_sms_code(phone: str, code: str) -> None:
    """校验并消费短信验证码，避免同一验证码重复使用。"""
    redis = await get_redis_client()
    code_key = f"{SMS_CODE_PREFIX}{phone}"
    cached_code = await redis.get(code_key)
    if not cached_code or cached_code != code:
        raise AppException("验证码错误或已过期", status_code=400, code="SMS_CODE_INVALID")
    await redis.delete(code_key)


def _create_user_from_phone(db: Session, phone: str) -> User:
    """手机号首次登录时自动创建账号，延续 Java 侧体验。"""
    user = User(
        uuid=uuid4().hex,
        phone=phone,
        nickname=f"旅行者{phone[-4:]}",
    )
    db.add(user)
    db.flush()
    create_default_settings(db, user.id)
    return user


def _default_oauth_nickname(profile: OAuthUserProfile) -> str:
    """OAuth 昵称兜底策略，保持 Java 侧默认用户名语义。"""
    if profile.nickname.strip():
        return profile.nickname
    suffix = profile.open_id[-6:] if profile.open_id else uuid4().hex[:6]
    return f"旅行者{suffix}"


def _create_user_from_oauth(db: Session, profile: OAuthUserProfile) -> User:
    """OAuth 首次登录且无法关联老用户时创建账号。"""
    user = User(
        uuid=uuid4().hex,
        email=profile.email,
        nickname=_default_oauth_nickname(profile),
        avatar_oss_key=profile.avatar_url,
    )
    db.add(user)
    db.flush()
    create_default_settings(db, user.id)
    return user


def _sync_user_profile_from_oauth(db: Session, user: User, profile: OAuthUserProfile) -> None:
    """只补齐本地空字段，避免覆盖用户手动修改过的资料。"""
    if not user.nickname and profile.nickname:
        user.nickname = profile.nickname
    if not user.avatar_oss_key and profile.avatar_url:
        user.avatar_oss_key = profile.avatar_url
    if not user.email and profile.email:
        email_owner = get_user_by_email(db, profile.email)
        if email_owner is None or email_owner.id == user.id:
            user.email = profile.email


def _bind_oauth_account(db: Session, user: User, profile: OAuthUserProfile) -> UserOauthBinding:
    """创建或更新第三方账号绑定关系。"""
    binding = UserOauthBinding(
        user_id=user.id,
        provider=profile.provider,
        open_id=profile.open_id,
        access_token=profile.access_token,
        expires_at=profile.expires_at,
    )
    db.add(binding)
    db.flush()
    return binding


async def login_by_oauth(
    db: Session,
    provider: str,
    auth_code: str,
    redirect_uri: str,
) -> LoginResponse:
    """第三方 OAuth 登录；当前迁移 GitHub provider。"""
    normalized_provider = normalize_provider(provider)
    profile = await fetch_oauth_user_profile(normalized_provider, auth_code, redirect_uri)

    binding = db.query(UserOauthBinding).filter(
        UserOauthBinding.provider == normalized_provider,
        UserOauthBinding.open_id == profile.open_id,
    ).one_or_none()
    is_new_user = False

    # 绑定关系已存在
    if binding is not None:
        binding.access_token = profile.access_token
        binding.expires_at = profile.expires_at
        user = db.get(User, binding.user_id)
        if user is None:
            raise AppException("OAuth 绑定用户不存在", status_code=404, code="USER_NOT_FOUND")
        ensure_user_can_login(user)
        _sync_user_profile_from_oauth(db, user, profile)
    # 绑定关系不存在 - 创建新用户和绑定关系
    else:
        user = get_user_by_email(db, profile.email) if profile.email else None
        if user is None:
            user = _create_user_from_oauth(db, profile)
            is_new_user = True
        else:
            ensure_user_can_login(user)
            _sync_user_profile_from_oauth(db, user, profile)
        _bind_oauth_account(db, user, profile)

    token_pair = create_token_pair(user)
    await store_refresh_token(user.uuid, token_pair.refresh_token)
    db.commit()
    db.refresh(user)
    return LoginResponse(
        **token_pair.model_dump(by_alias=True),
        isNewUser=is_new_user,
        userInfo=build_profile(db, user),
    )


async def login_by_phone(db: Session, phone: str, code: str) -> LoginResponse:
    """手机号验证码登录；不存在的手机号会自动注册。"""
    await validate_sms_code(phone, code)
    user = get_user_by_phone(db, phone)
    is_new_user = user is None
    if user is None:
        user = _create_user_from_phone(db, phone)
    ensure_user_can_login(user)
    token_pair = create_token_pair(user)
    await store_refresh_token(user.uuid, token_pair.refresh_token)
    db.commit()
    db.refresh(user)
    return LoginResponse(
        **token_pair.model_dump(by_alias=True),
        isNewUser=is_new_user,
        userInfo=build_profile(db, user),
    )


async def register_by_phone(
    db: Session,
    phone: str,
    code: str,
    nickname: str | None = None,
) -> LoginResponse:
    """手机号注册；已存在账号时返回明确冲突。"""
    await validate_sms_code(phone, code)
    if get_user_by_phone(db, phone) is not None:
        raise AppException("手机号已注册", status_code=409, code="PHONE_ALREADY_REGISTERED")

    user = _create_user_from_phone(db, phone)
    if nickname:
        user.nickname = nickname
    token_pair = create_token_pair(user)
    await store_refresh_token(user.uuid, token_pair.refresh_token)
    db.commit()
    db.refresh(user)
    return LoginResponse(
        **token_pair.model_dump(by_alias=True),
        isNewUser=True,
        userInfo=build_profile(db, user),
    )


async def refresh_token(db: Session, refresh_token_value: str) -> TokenPair:
    """校验 refresh token 并签发新 token 对。"""
    try:
        payload = jwt.decode(refresh_token_value, _require_jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AppException("刷新令牌已过期", status_code=401, code="REFRESH_TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise AppException("刷新令牌无效", status_code=401, code="REFRESH_TOKEN_INVALID")

    if payload.get("typ") != "refresh":
        raise AppException("刷新令牌类型错误", status_code=401, code="REFRESH_TOKEN_INVALID")

    user_uuid = payload.get("userUuid")
    if not user_uuid:
        raise AppException("刷新令牌缺少用户标识", status_code=401, code="REFRESH_TOKEN_INVALID")

    redis = await get_redis_client()
    stored = await redis.get(f"{REFRESH_TOKEN_PREFIX}{user_uuid}")
    if stored != refresh_token_value:
        raise AppException("刷新令牌已失效", status_code=401, code="REFRESH_TOKEN_REVOKED")

    user = get_user_by_uuid(db, user_uuid)
    if user is None:
        raise AppException("用户不存在", status_code=404, code="USER_NOT_FOUND")
    ensure_user_can_login(user)

    token_pair = create_token_pair(user)
    await store_refresh_token(user.uuid, token_pair.refresh_token)
    return token_pair


async def logout(access_token: str | None, refresh_token_value: str | None = None) -> None:
    """退出登录：拉黑 access token，并删除 refresh token。"""
    redis = await get_redis_client()

    if access_token:
        access_token = _strip_bearer_prefix(access_token)
        token_hash = hashlib.md5(access_token.encode()).hexdigest()
        ttl = settings.jwt_access_token_ttl_seconds
        try:
            payload = jwt.decode(
                access_token,
                _require_jwt_secret(),
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            exp = payload.get("exp")
            if exp:
                ttl = max(1, int(exp - _utc_now().timestamp()))
        except jwt.InvalidTokenError:
            ttl = settings.jwt_access_token_ttl_seconds
        await redis.setex(f"{TOKEN_BLACKLIST_PREFIX}{token_hash}", ttl, "1")

    if refresh_token_value:
        try:
            payload = jwt.decode(
                refresh_token_value,
                _require_jwt_secret(),
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            user_uuid = payload.get("userUuid")
            if user_uuid:
                await redis.delete(f"{REFRESH_TOKEN_PREFIX}{user_uuid}")
        except jwt.InvalidTokenError:
            logger.debug("退出登录时忽略无效 refresh token")
