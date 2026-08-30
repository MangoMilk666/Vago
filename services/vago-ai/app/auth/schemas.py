"""认证领域请求/响应 schema。"""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.users.schemas import UserProfile


class SmsSendRequest(BaseModel):
    """短信验证码发送请求。"""

    phone: str = Field(min_length=7, max_length=20)


class SmsSendResponse(BaseModel):
    """短信验证码发送响应。"""

    expire_seconds: int = Field(alias="expireSeconds")

    model_config = ConfigDict(populate_by_name=True)


class PhoneLoginRequest(BaseModel):
    """手机号验证码登录请求。"""

    phone: str = Field(min_length=7, max_length=20)
    code: str = Field(
        min_length=4,
        max_length=8,
        validation_alias=AliasChoices("code", "smsCode"),
    )

    model_config = ConfigDict(populate_by_name=True)


class RegisterRequest(PhoneLoginRequest):
    """手机号注册请求，验证码校验通过后创建账号。"""

    nickname: str | None = Field(default=None, min_length=1, max_length=64)


class TokenRefreshRequest(BaseModel):
    """刷新 token 请求。"""

    refresh_token: str = Field(alias="refreshToken", min_length=1)
    # model_config: 描述这个 Pydantic Model 有哪些特殊的解析、验证、序列化行为
    # 除了 alias，也允许使用 Python 字段本身的名字进行赋值。
    model_config = ConfigDict(populate_by_name=True)


class TokenPair(BaseModel):
    """访问 token 与刷新 token。"""

    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    expires_in: int = Field(alias="expiresIn")

    model_config = ConfigDict(populate_by_name=True)


class LoginResponse(TokenPair):
    """登录成功响应。"""

    is_new_user: bool = Field(alias="isNewUser")
    user_info: UserProfile = Field(alias="userInfo")
