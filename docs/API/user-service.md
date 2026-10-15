# 认证与用户 API

**状态：当前 FastAPI 接口摘要。** 路由与字段以 `services/vago-ai/app/auth`、`app/users`、`app/preferences` 的代码和运行时 OpenAPI 为准。[迁移期详细快照](../archive/user-service-2026-08-30.md)保留供追溯，不适合作现行契约。

成功响应采用 `{ "code": 200, "message": "...", "data": ... }`。需登录的路由使用 `Authorization: Bearer <accessToken>`；服务端从令牌确定当前用户。`/api/v1/user` 保留旧前缀兼容入口，新增客户端优先使用 `/api/v1/auth` 和 `/api/v1/users`。

## 认证：`/api/v1/auth`

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/sms/send` | 发送手机号验证码 |
| POST | `/login/phone` | 手机号验证码登录，返回 token 与用户资料 |
| POST | `/register` | 手机号注册 |
| POST | `/login/oauth` | 第三方 OAuth 登录 |
| POST | `/token/refresh` | 用 refresh token 换新 token |
| POST | `/logout` | 使当前 access token 失效；可选同时传 refresh token |

手机号登录请求使用 `phone`、`code`（兼容 `smsCode`）、可选 `clientType` 和 `deviceId`；注册另可传 `nickname`。刷新请求使用 `refreshToken`。登录响应包括 `accessToken`、`refreshToken`、`expiresIn`、`sessionId`、`isNewUser`、`userInfo`。OAuth 请求字段为 `provider`、`authCode`、`redirectUri`、可选 `deviceId`。

## 用户：`/api/v1/users`

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / PUT | `/profile` | 读取或修改当前用户资料 |
| GET / PUT | `/settings` | 读取或修改当前用户设置 |
| GET / PUT | `/travel-preferences` | 读取或修改明确的旅行偏好 |
| DELETE | `/account` | 以 `smsCode` 申请注销，返回宽限期截止时间 |
| POST | `/account/cancel-revoke` | 撤销注销申请 |

这些操作均以认证用户为数据范围。请求字段、长度限制和错误响应请核对 `app/auth/schemas.py`、`app/users/schemas.py`、`app/preferences/schemas.py`；不要沿用归档文档中的 Spring Boot 限流或错误码假设。
