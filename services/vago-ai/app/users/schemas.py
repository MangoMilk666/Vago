"""用户领域请求/响应 schema。"""

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """返回给客户端的用户资料。"""

    # 用户业务 UUID，对外暴露的用户唯一标识。
    uuid: str
    # 用户昵称。
    nickname: str
    # 用户手机号；OAuth 首次登录时可能为空。
    phone: str | None = None
    # 用户邮箱；短信注册用户可能为空。
    email: str | None = None
    # 用户头像 URL 或兼容旧头像字段的展示值。
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    # 账号套餐类型。
    plan_type: int = Field(alias="planType")
    # 攻略/知识条目配额。
    article_quota: int = Field(alias="articleQuota")
    # 账号状态。
    status: int
    # 账号创建时间。
    created_at: datetime = Field(alias="createdAt")
    # 已绑定的第三方登录提供商列表。
    oauth_providers: list[str] = Field(default_factory=list, alias="oauthProviders")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class UserProfileUpdate(BaseModel):
    """用户资料更新请求；None 表示不更新该字段。"""

    # 新昵称；未传表示不修改。
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    # 新邮箱；未传表示不修改。
    email: str | None = Field(default=None, max_length=128)
    # 新头像展示值，兼容 avatarUrl 与旧 avatarUuid 入参。
    avatar_url: str | None = Field(
        default=None,
        max_length=512,
        alias="avatarUrl",
        validation_alias=AliasChoices("avatarUrl", "avatarUuid"),
    )

    model_config = ConfigDict(populate_by_name=True)


class UserSettingsResponse(BaseModel):
    """用户偏好设置响应。"""

    # GPS 记录模式。
    gps_mode: int = Field(alias="gpsMode")
    # 迷雾地图解锁半径，单位为米。
    fog_unlock_radius_m: int = Field(alias="fogUnlockRadiusM")
    # 默认可见性。
    default_visibility: int = Field(alias="defaultVisibility")
    # 用户界面语言。
    language: str
    # 用户时区。
    timezone: str
    # 是否开启打卡提醒。
    notification_checkin: bool = Field(alias="notificationCheckin")
    # 设置最近更新时间。
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class UserSettingsUpdate(BaseModel):
    """用户偏好设置更新请求。"""

    # GPS 记录模式；未传表示不修改。
    gps_mode: int | None = Field(default=None, alias="gpsMode", ge=0, le=2)
    # 迷雾地图解锁半径；未传表示不修改。
    fog_unlock_radius_m: int | None = Field(
        default=None,
        alias="fogUnlockRadiusM",
        ge=100,
        le=1000,
    )
    # 默认可见性；未传表示不修改。
    default_visibility: int | None = Field(default=None, alias="defaultVisibility", ge=0, le=2)
    # 用户界面语言；未传表示不修改。
    language: str | None = Field(default=None, min_length=2, max_length=16)
    # 用户时区；未传表示不修改。
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    # 是否开启打卡提醒；未传表示不修改。
    notification_checkin: bool | None = Field(default=None, alias="notificationCheckin")

    model_config = ConfigDict(populate_by_name=True)


class AccountCancelRequest(BaseModel):
    """账号注销申请请求。"""

    # 注销确认短信验证码。
    sms_code: str = Field(
        alias="smsCode",
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )
    # 用户填写的注销原因，可为空。
    reason: str | None = Field(default=None, max_length=200)

    model_config = ConfigDict(populate_by_name=True)


class AccountCancelResponse(BaseModel):
    """账号注销申请响应。"""

    # 注销宽限期截止时间。
    cancel_deadline: str = Field(alias="cancelDeadline")

    model_config = ConfigDict(populate_by_name=True)
