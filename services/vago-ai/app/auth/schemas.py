"""认证领域请求/响应 schema。"""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.users.schemas import UserProfile


class SmsSendRequest(BaseModel):
    """短信验证码发送请求。"""

    # 手机号，用于发送短信验证码。
    phone: str = Field(min_length=7, max_length=20)


class SmsSendResponse(BaseModel):
    """短信验证码发送响应。"""

    # 验证码有效期，单位为秒。
    expire_seconds: int = Field(alias="expireSeconds")

    model_config = ConfigDict(populate_by_name=True)


class PhoneLoginRequest(BaseModel):
    """手机号验证码登录请求。"""

    # 手机号，用于匹配验证码和账号。
    phone: str = Field(min_length=7, max_length=20)
    # 短信验证码，兼容 code 与 smsCode 两种入参字段名。
    code: str = Field(
        min_length=4,
        max_length=8,
        validation_alias=AliasChoices("code", "smsCode"),
    )
    # 客户端类型，用于区分 Web 与原生端的登录会话。
    client_type: str = Field(default="web", alias="clientType", max_length=32)
    # 设备安装标识；原生端传入后可维持独立登录状态。
    device_id: str | None = Field(default=None, alias="deviceId", max_length=128)

    model_config = ConfigDict(populate_by_name=True)


class RegisterRequest(PhoneLoginRequest):
    """手机号注册请求，验证码校验通过后创建账号。"""

    # 用户昵称；为空时由服务端生成默认昵称。
    nickname: str | None = Field(default=None, min_length=1, max_length=64)


class OAuthLoginRequest(BaseModel):
    """第三方 OAuth 登录请求。"""

    # 第三方登录提供商标识，例如 github。
    provider: str = Field(min_length=1, max_length=32)
    # OAuth 授权码，用于向第三方换取访问令牌。
    auth_code: str = Field(alias="authCode", min_length=1)
    # OAuth 回调地址，需与第三方应用配置保持一致。
    redirect_uri: str = Field(alias="redirectUri", min_length=1)
    # 客户端设备标识，预留给多设备登录管理。
    device_id: str | None = Field(default=None, alias="deviceId")

    model_config = ConfigDict(populate_by_name=True)


class TokenRefreshRequest(BaseModel):
    """刷新 token 请求。"""

    # 刷新令牌，用于换取新的 access token。
    refresh_token: str = Field(alias="refreshToken", min_length=1)
    # model_config: 描述这个 Pydantic Model 有哪些特殊的解析、验证、序列化行为
    # 除了 alias，也允许使用 Python 字段本身的名字进行赋值。
    model_config = ConfigDict(populate_by_name=True)


class TokenPair(BaseModel):
    """访问 token 与刷新 token。"""

    # 访问令牌，用于调用需要登录态的 API。
    access_token: str = Field(alias="accessToken")
    # 刷新令牌，用于 access token 过期后的续期。
    refresh_token: str = Field(alias="refreshToken")
    # access token 有效期，单位为秒。
    expires_in: int = Field(alias="expiresIn")
    # 设备级会话标识，客户端仅用于定位当前登录会话。
    session_id: str | None = Field(default=None, alias="sessionId")

    model_config = ConfigDict(populate_by_name=True)


class LoginResponse(TokenPair):
    """登录成功响应。"""

    # 是否为首次创建的新用户。
    is_new_user: bool = Field(alias="isNewUser")
    # 登录成功后返回的用户资料快照。
    user_info: UserProfile = Field(alias="userInfo")
