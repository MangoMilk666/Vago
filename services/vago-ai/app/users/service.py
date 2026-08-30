"""用户领域业务服务。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.users.models import User, UserOauthBinding, UserSettings
from app.users.schemas import UserProfile, UserProfileUpdate, UserSettingsResponse, UserSettingsUpdate

ACTIVE_STATUS = 1
BANNED_STATUS = 2
CANCELLING_STATUS = 3

DEFAULT_GPS_MODE = 1
DEFAULT_FOG_RADIUS_M = 200
DEFAULT_DEFAULT_VISIBILITY = 0
DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_NOTIFICATION_CHECKIN = 1


def mask_phone(phone: str | None) -> str | None:
    """手机号脱敏：保持与 Java 侧 ``138****1000`` 的展示规则一致。"""
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def get_user_by_uuid(db: Session, user_uuid: str) -> User | None:
    """按 UUID 查找未软删除用户。"""
    return db.scalar(select(User).where(User.uuid == user_uuid, User.deleted_at.is_(None)))


def get_user_by_phone(db: Session, phone: str) -> User | None:
    """按手机号查找未软删除用户。"""
    return db.scalar(select(User).where(User.phone == phone, User.deleted_at.is_(None)))


def get_user_or_raise(db: Session, user_uuid: str) -> User:
    """获取当前用户，不存在或状态异常时抛出业务异常。"""
    user = get_user_by_uuid(db, user_uuid)
    if user is None:
        raise AppException("用户不存在", status_code=404, code="USER_NOT_FOUND")
    ensure_user_can_login(user)
    return user


def ensure_user_can_login(user: User) -> None:
    """校验账号状态，复用 Java 侧 active/cancelled/banned 语义。"""
    if user.status == ACTIVE_STATUS:
        return
    if user.status == BANNED_STATUS:
        raise AppException("账号已被禁用", status_code=403, code="ACCOUNT_BANNED")
    if user.status == CANCELLING_STATUS:
        raise AppException("账号注销中", status_code=403, code="ACCOUNT_CANCELLING")
    raise AppException("账号状态异常", status_code=403, code="ACCOUNT_INVALID")


def create_default_settings(db: Session, user_id: int) -> UserSettings:
    """为新用户创建默认设置；默认值与当前 MySQL DDL 保持一致。"""
    settings = UserSettings(
        user_id=user_id,
        gps_mode=DEFAULT_GPS_MODE,
        fog_unlock_radius_m=DEFAULT_FOG_RADIUS_M,
        default_visibility=DEFAULT_DEFAULT_VISIBILITY,
        language=DEFAULT_LANGUAGE,
        timezone=DEFAULT_TIMEZONE,
        notification_checkin=DEFAULT_NOTIFICATION_CHECKIN,
    )
    db.add(settings)
    db.flush()
    return settings


def get_or_create_settings(db: Session, user_id: int) -> UserSettings:
    """获取用户设置；历史脏数据缺失时补齐默认设置。"""
    settings = db.get(UserSettings, user_id)
    if settings is None:
        settings = create_default_settings(db, user_id)
    return settings


def build_profile(db: Session, user: User) -> UserProfile:
    """组装用户资料 VO，并对敏感字段做脱敏处理。"""
    providers = db.scalars(
        select(UserOauthBinding.provider).where(UserOauthBinding.user_id == user.id)
    ).all()
    return UserProfile(
        uuid=user.uuid,
        nickname=user.nickname,
        phone=mask_phone(user.phone),
        email=user.email,
        avatarUrl=user.avatar_oss_key,
        planType=user.plan_type,
        articleQuota=user.article_quota,
        status=user.status,
        createdAt=user.created_at,
        oauthProviders=list(providers),
    )


def update_profile(db: Session, user_uuid: str, payload: UserProfileUpdate) -> UserProfile:
    """更新用户基础资料，并返回更新后的脱敏资料。"""
    user = get_user_or_raise(db, user_uuid)

    if payload.nickname is not None:
        user.nickname = payload.nickname
    if payload.email is not None:
        existing = db.scalar(
            select(User).where(
                User.email == payload.email,
                User.id != user.id,
                User.deleted_at.is_(None),
            )
        )
        if existing is not None:
            raise AppException("邮箱已被使用", status_code=409, code="EMAIL_ALREADY_USED")
        user.email = payload.email
    if payload.avatar_url is not None:
        user.avatar_oss_key = payload.avatar_url

    db.commit()
    db.refresh(user)
    return build_profile(db, user)


def get_settings_response(db: Session, user_uuid: str) -> UserSettingsResponse:
    """读取当前用户偏好设置。"""
    user = get_user_or_raise(db, user_uuid)
    settings = get_or_create_settings(db, user.id)
    db.commit()
    return UserSettingsResponse.model_validate(settings).model_copy(
        update={"notification_checkin": settings.notification_checkin == 1}
    )


def update_settings(db: Session, user_uuid: str, payload: UserSettingsUpdate) -> UserSettingsResponse:
    """更新当前用户偏好设置。"""
    user = get_user_or_raise(db, user_uuid)
    settings = get_or_create_settings(db, user.id)

    values = payload.model_dump(exclude_unset=True, by_alias=False)
    for field_name, value in values.items():
        if field_name == "notification_checkin":
            value = 1 if value else 0
        setattr(settings, field_name, value)

    db.commit()
    db.refresh(settings)
    return UserSettingsResponse.model_validate(settings).model_copy(
        update={"notification_checkin": settings.notification_checkin == 1}
    )
