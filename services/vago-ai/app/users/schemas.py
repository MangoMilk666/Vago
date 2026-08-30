"""用户领域请求/响应 schema。"""

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """返回给客户端的用户资料。"""

    uuid: str
    nickname: str
    phone: str | None = None
    email: str | None = None
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    plan_type: int = Field(alias="planType")
    article_quota: int = Field(alias="articleQuota")
    status: int
    created_at: datetime = Field(alias="createdAt")
    oauth_providers: list[str] = Field(default_factory=list, alias="oauthProviders")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class UserProfileUpdate(BaseModel):
    """用户资料更新请求；None 表示不更新该字段。"""

    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=128)
    avatar_url: str | None = Field(
        default=None,
        max_length=512,
        alias="avatarUrl",
        validation_alias=AliasChoices("avatarUrl", "avatarUuid"),
    )

    model_config = ConfigDict(populate_by_name=True)


class UserSettingsResponse(BaseModel):
    """用户偏好设置响应。"""

    gps_mode: int = Field(alias="gpsMode")
    fog_unlock_radius_m: int = Field(alias="fogUnlockRadiusM")
    default_visibility: int = Field(alias="defaultVisibility")
    language: str
    timezone: str
    notification_checkin: bool = Field(alias="notificationCheckin")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class UserSettingsUpdate(BaseModel):
    """用户偏好设置更新请求。"""

    gps_mode: int | None = Field(default=None, alias="gpsMode", ge=0, le=2)
    fog_unlock_radius_m: int | None = Field(
        default=None,
        alias="fogUnlockRadiusM",
        ge=100,
        le=1000,
    )
    default_visibility: int | None = Field(default=None, alias="defaultVisibility", ge=0, le=2)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    notification_checkin: bool | None = Field(default=None, alias="notificationCheckin")

    model_config = ConfigDict(populate_by_name=True)
