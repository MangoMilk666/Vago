"""用户领域业务服务。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.exceptions import AppException
from app.core.redis import get_redis_client
from app.users.models import User, UserOauthBinding, UserSettings
from app.users.schemas import (
    AccountCancelResponse,
    UserProfile,
    UserProfileUpdate,
    UserSettingsResponse,
    UserSettingsUpdate,
)

ACTIVE_STATUS = 1
BANNED_STATUS = 2
CANCELLING_STATUS = 3

DEFAULT_GPS_MODE = 1
DEFAULT_FOG_RADIUS_M = 200
DEFAULT_DEFAULT_VISIBILITY = 0
DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_NOTIFICATION_CHECKIN = 1
CANCEL_KEY_PREFIX = "vago:cancel:"


def mask_phone(phone: str | None) -> str | None:
    """手机号脱敏：保持与 Java 侧 ``138****1000`` 的展示规则一致。"""
    # 分支条件：手机号为空或长度不足时，原样返回。
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def get_user_by_uuid(db: Session, user_uuid: str) -> User | None:
    """按 UUID 查找未软删除用户。"""
    return db.scalar(select(User).where(User.uuid == user_uuid, User.deleted_at.is_(None)))


def get_user_by_phone(db: Session, phone: str) -> User | None:
    """按手机号查找未软删除用户。"""
    return db.scalar(select(User).where(User.phone == phone, User.deleted_at.is_(None)))


def get_user_by_email(db: Session, email: str) -> User | None:
    """按邮箱查找未软删除用户，用于 OAuth 账号合并与资料更新冲突校验。"""
    return db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))


def get_user_or_raise(db: Session, user_uuid: str) -> User:
    """获取当前用户，不存在或状态异常时抛出业务异常。"""
    user = get_user_by_uuid(db, user_uuid)
    # 分支条件：UUID 找不到未删除用户时，返回用户不存在。
    if user is None:
        raise AppException("用户不存在", status_code=404, code="USER_NOT_FOUND")
    ensure_user_can_login(user)
    return user


def ensure_user_can_login(user: User) -> None:
    """校验账号状态，复用 Java 侧 active/banned/cancelling 语义。"""
    # 分支条件：账号状态为正常时允许继续业务流程。
    if user.status == ACTIVE_STATUS:
        return
    # 分支条件：账号状态为封禁时拒绝登录或资料操作。
    if user.status == BANNED_STATUS:
        raise AppException("账号已被禁用", status_code=403, code="ACCOUNT_BANNED")
    # 分支条件：账号状态为注销中时拒绝登录或资料操作。
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
    # 分支条件：历史用户缺少设置记录时，补一份默认设置。
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

    # 分支条件：请求传入 nickname 时更新昵称。
    if payload.nickname is not None:
        user.nickname = payload.nickname
    # 分支条件：请求传入 email 时先检查唯一性再更新。
    if payload.email is not None:
        existing = db.scalar(
            select(User).where(
                User.email == payload.email,
                User.id != user.id,
                User.deleted_at.is_(None),
            )
        )
        # 分支条件：邮箱被其他未删除用户占用时，返回冲突。
        if existing is not None:
            raise AppException("邮箱已被使用", status_code=409, code="EMAIL_ALREADY_USED")
        user.email = payload.email
    # 分支条件：请求传入 avatarUrl/avatarUuid 时更新头像字段。
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
        # 分支条件：notification_checkin 为布尔入参时，转换成数据库 0/1。
        if field_name == "notification_checkin":
            value = 1 if value else 0
        setattr(settings, field_name, value)

    db.commit()
    db.refresh(settings)
    return UserSettingsResponse.model_validate(settings).model_copy(
        update={"notification_checkin": settings.notification_checkin == 1}
    )


async def cancel_account(user_uuid: str, sms_code: str, db: Session) -> AccountCancelResponse:
    """申请注销账号：校验短信后进入 7 天可撤销状态。"""
    from app.auth.service import validate_sms_code

    user = get_user_by_uuid(db, user_uuid)
    # 分支条件：UUID 找不到未删除用户时，返回用户不存在。
    if user is None:
        raise AppException("用户不存在", status_code=404, code="USER_NOT_FOUND")
    # 分支条件：账号已经处于注销中时，拒绝重复提交注销。
    if user.status == CANCELLING_STATUS:
        raise AppException("账号已在注销中", status_code=409, code="ACCOUNT_ALREADY_CANCELLING")
    # 分支条件：账号已封禁时，不允许发起注销流程。
    if user.status == BANNED_STATUS:
        raise AppException("账号已被禁用", status_code=403, code="ACCOUNT_BANNED")
    # 分支条件：账号未绑定手机号时，无法用短信验证码确认注销。
    if not user.phone:
        raise AppException("当前账号未绑定手机号，无法短信校验", status_code=400, code="PHONE_NOT_BOUND")

    await validate_sms_code(user.phone, sms_code)
    user.status = CANCELLING_STATUS

    redis = await get_redis_client()
    # Redis key 过期即代表宽限期结束；后台物理清理任务后续阶段再迁移。
    from datetime import datetime, timedelta

    deadline = datetime.now() + timedelta(seconds=app_settings.account_cancel_grace_seconds)
    deadline_text = deadline.strftime("%Y-%m-%d %H:%M:%S")
    await redis.setex(
        f"{CANCEL_KEY_PREFIX}{user_uuid}",
        app_settings.account_cancel_grace_seconds,
        deadline_text,
    )
    db.commit()
    return AccountCancelResponse(cancelDeadline=deadline_text)


async def revoke_cancel_account(user_uuid: str, db: Session) -> None:
    """撤销账号注销申请：宽限期 Redis key 存在时恢复正常状态。"""
    user = get_user_by_uuid(db, user_uuid)
    # 分支条件：UUID 找不到未删除用户时，返回用户不存在。
    if user is None:
        raise AppException("用户不存在", status_code=404, code="USER_NOT_FOUND")
    # 分支条件：账号不是注销中状态时，不能撤销注销。
    if user.status != CANCELLING_STATUS:
        raise AppException("账号不在注销中", status_code=409, code="ACCOUNT_NOT_CANCELLING")

    redis = await get_redis_client()
    cancel_key = f"{CANCEL_KEY_PREFIX}{user_uuid}"
    # 分支条件：Redis 宽限期 key 不存在时，说明撤销窗口已过。
    if not await redis.exists(cancel_key):
        raise AppException("注销撤销已过期", status_code=409, code="CANCEL_REVOKE_EXPIRED")

    user.status = ACTIVE_STATUS
    await redis.delete(cancel_key)
    db.commit()
