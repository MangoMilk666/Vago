# Vago 用户服务接口文档（C 端）

**服务**：`vago-service-user`  
**Base URL**：`/api/v1/user`  
**文档版本**：v0.1 | 2026-05-16  
**认证方式**：除登录/注册/发送验证码外，所有接口需在 Header 中携带 `Authorization: Bearer {accessToken}`

---

## 目录

1. [通用说明](#1-通用说明)
2. [短信验证码](#2-短信验证码)
3. [注册与登录](#3-注册与登录)
4. [Token 管理](#4-token-管理)
5. [用户信息管理](#5-用户信息管理)
6. [账户管理](#6-账户管理)
7. [错误码列表](#7-错误码列表)

---

## 1. 通用说明

### 1.1 统一响应结构

所有接口均返回如下 JSON 结构：

```json
{
  "code":    200,
  "message": "success",
  "data":    {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | Integer | 业务状态码（非 HTTP 状态码，200 表示成功） |
| `message` | String | 描述信息 |
| `data` | Object / null | 响应业务数据 |

### 1.2 认证流程

```
1. 调用 POST /sms/send 发送验证码
2. 调用 POST /register 或 POST /login/phone 完成认证，返回 accessToken + refreshToken
3. 后续请求 Header 携带：Authorization: Bearer {accessToken}
4. accessToken 过期后，调用 POST /token/refresh 用 refreshToken 换新 token
5. 退出时调用 POST /logout
```

### 1.3 时间格式

所有时间字段均为 **UTC ISO-8601** 格式：`2026-05-16T08:00:00.000Z`

---

## 2. 短信验证码

### 2.1 发送验证码

```
POST /api/v1/user/sms/send
```

**场景**：注册、登录、注销前的身份验证。

**请求 Header**

| Key | 是否必须 | 说明 |
|-----|---------|------|
| `X-Client-Type` | 否 | 客户端类型：`web` / `ios` / `android` |

**请求 Body**

```json
{
  "phone":   "+8613800138000",
  "scene":   "REGISTER"
}
```

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `phone` | String | ✅ | E.164 格式手机号 |
| `scene` | String | ✅ | 枚举：`REGISTER` / `LOGIN` / `CANCEL_ACCOUNT` |

**响应**

```json
{
  "code": 200,
  "message": "验证码已发送",
  "data": {
    "expireSeconds": 300
  }
}
```

**限流规则**：同一手机号 60 秒内只能发送 1 次；同一 IP 每分钟最多发送 5 次。

**错误码**

| code | 说明 |
|------|------|
| `4001` | 手机号格式不合法 |
| `4291` | 发送频率超限（60s 内重复发送） |
| `5001` | 短信服务暂不可用 |

---

## 3. 注册与登录

### 3.1 手机号注册

```
POST /api/v1/user/register
```

**说明**：手机号首次使用时注册账号，已注册手机号调用此接口返回 `4090`。

**请求 Body**

```json
{
  "phone":      "+8613800138000",
  "smsCode":    "123456",
  "nickname":   "旅行者小明",
  "deviceId":   "d1e2f3a4b5c6"
}
```

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `phone` | String | ✅ | E.164 格式手机号 |
| `smsCode` | String | ✅ | 6 位短信验证码 |
| `nickname` | String | ✅ | 昵称，2–20 个字符 |
| `deviceId` | String | 否 | 设备唯一标识（用于风控） |

**响应**

```json
{
  "code": 200,
  "message": "注册成功",
  "data": {
    "accessToken":  "eyJhbGciOiJIUzI1NiJ9...",
    "refreshToken": "dGhpcyBpcyBhIHJlZnJlc2gg...",
    "expiresIn":    7200,
    "userInfo": {
      "uuid":       "550e8400-e29b-41d4-a716-446655440000",
      "nickname":   "旅行者小明",
      "phone":      "+8613800138000",
      "avatarUrl":  null,
      "planType":   0,
      "status":     1
    }
  }
}
```

**错误码**

| code | 说明 |
|------|------|
| `4001` | 参数格式不合法 |
| `4002` | 验证码错误或已过期 |
| `4090` | 手机号已注册，请直接登录 |

---

### 3.2 手机号登录

```
POST /api/v1/user/login/phone
```

**请求 Body**

```json
{
  "phone":    "+8613800138000",
  "smsCode":  "123456",
  "deviceId": "d1e2f3a4b5c6"
}
```

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `phone` | String | ✅ | E.164 格式手机号 |
| `smsCode` | String | ✅ | 6 位短信验证码 |
| `deviceId` | String | 否 | 设备唯一标识 |

**响应**（同注册响应结构）

**错误码**

| code | 说明 |
|------|------|
| `4002` | 验证码错误或已过期 |
| `4041` | 手机号未注册 |
| `4031` | 账号已被封禁 |
| `4032` | 账号注销中，无法登录 |

---

### 3.3 第三方 OAuth 登录

```
POST /api/v1/user/login/oauth
```

**说明**：客户端完成 OAuth 授权后，将 provider 和 authCode 传入，服务端完成 token 换取与用户关联。首次 OAuth 登录自动完成注册（nickname 取自 OAuth 平台，可后续修改）。

**请求 Body**

```json
{
  "provider":  "wechat",
  "authCode":  "0a1b2c3d4e5f",
  "deviceId":  "d1e2f3a4b5c6"
}
```

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `provider` | String | ✅ | 枚举：`wechat` / `apple` |
| `authCode` | String | ✅ | OAuth 授权码（客户端从第三方获取） |
| `deviceId` | String | 否 | 设备唯一标识 |

**响应**（同注册响应结构，含 `isNewUser: true/false` 字段）

```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "accessToken":  "eyJhbGciOiJIUzI1NiJ9...",
    "refreshToken": "dGhpcyBpcyBhIHJlZnJlc2gg...",
    "expiresIn":    7200,
    "isNewUser":    true,
    "userInfo": { ... }
  }
}
```

**错误码**

| code | 说明 |
|------|------|
| `4001` | provider 不合法 |
| `4003` | authCode 无效或已过期 |
| `5002` | OAuth 服务调用失败 |

---

## 4. Token 管理

### 4.1 刷新 Access Token

```
POST /api/v1/user/token/refresh
```

**说明**：Access Token 过期（HTTP 401）后，用 refreshToken 换取新 token 对。refreshToken 本身有效期为 30 天，换新后旧 refreshToken 立即失效（单次使用）。

**请求 Body**

```json
{
  "refreshToken": "dGhpcyBpcyBhIHJlZnJlc2gg..."
}
```

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "accessToken":  "eyJhbGciOiJIUzI1NiJ9...",
    "refreshToken": "bmV3cmVmcmVzaHRva2Vu...",
    "expiresIn":    7200
  }
}
```

**错误码**

| code | 说明 |
|------|------|
| `4011` | refreshToken 无效 |
| `4012` | refreshToken 已过期，请重新登录 |

---

### 4.2 退出登录

```
POST /api/v1/user/logout
```

**认证**：需要 `Authorization: Bearer {accessToken}`

**说明**：服务端将当前 accessToken 加入黑名单（Redis），refreshToken 同步作废。

**请求 Body**：无

**响应**

```json
{
  "code": 200,
  "message": "已退出登录",
  "data": null
}
```

---

## 5. 用户信息管理

### 5.1 获取当前用户信息

```
GET /api/v1/user/profile
```

**认证**：需要 `Authorization`

**响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid":          "550e8400-e29b-41d4-a716-446655440000",
    "nickname":      "旅行者小明",
    "phone":         "+861380013****",
    "email":         null,
    "avatarUrl":     "https://cdn.vago.com/avatars/xxx.jpg",
    "planType":      0,
    "articleQuota":  50,
    "status":        1,
    "createdAt":     "2026-05-16T08:00:00.000Z",
    "oauthProviders": ["wechat"]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `uuid` | String | 用户业务 ID |
| `phone` | String | 手机号（中间 4 位脱敏） |
| `planType` | Integer | 0=免费版 1=付费版 |
| `articleQuota` | Integer | 攻略库配额上限 |
| `status` | Integer | 1=正常 2=封禁 3=注销中 |
| `oauthProviders` | String[] | 已绑定的第三方平台列表 |

---

### 5.2 修改用户信息

```
PUT /api/v1/user/profile
```

**认证**：需要 `Authorization`

**说明**：仅传入需要修改的字段，未传入字段不更新。

**请求 Body**

```json
{
  "nickname":  "新昵称",
  "email":     "user@example.com",
  "avatarUuid": "photo-uuid-of-uploaded-avatar"
}
```

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `nickname` | String | 否 | 2–20 个字符 |
| `email` | String | 否 | 邮箱格式校验 |
| `avatarUuid` | String | 否 | 已上传头像的图片 UUID |

**响应**

```json
{
  "code": 200,
  "message": "修改成功",
  "data": {
    "uuid":      "...",
    "nickname":  "新昵称",
    "email":     "user@example.com",
    "avatarUrl": "https://cdn.vago.com/avatars/xxx.jpg"
  }
}
```

**错误码**

| code | 说明 |
|------|------|
| `4001` | 昵称格式不合法（长度/特殊字符） |
| `4041` | avatarUuid 对应的图片不存在 |
| `4091` | 邮箱已被其他账号使用 |

---

### 5.3 获取/更新用户偏好设置

```
GET  /api/v1/user/settings
PUT  /api/v1/user/settings
```

**认证**：需要 `Authorization`

**GET 响应**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "gpsMode":             1,
    "fogUnlockRadiusM":    300,
    "defaultVisibility":   0,
    "language":            "zh-CN",
    "timezone":            "Asia/Shanghai",
    "notificationCheckin": true
  }
}
```

**PUT 请求 Body**（仅传需要修改的字段）

```json
{
  "gpsMode":          2,
  "fogUnlockRadiusM": 500,
  "defaultVisibility": 0
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `gpsMode` | Integer | 0=省电 1=标准 2=精细 |
| `fogUnlockRadiusM` | Integer | 迷雾解锁半径（米），范围 100–1000 |
| `defaultVisibility` | Integer | 0=私密 1=链接可见 2=公开 |

---

## 6. 账户管理

### 6.1 申请注销账号

```
DELETE /api/v1/user/account
```

**认证**：需要 `Authorization`

**说明**：
- 注销不立即删除数据，账号进入「注销中」状态（status=3），7 个自然日内可撤销
- 7 日后后台任务触发物理删除（位置数据、攻略库、照片等）
- 注销中状态的账号无法登录

**请求 Body**

```json
{
  "smsCode": "123456",
  "reason":  "不再使用此应用"
}
```

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `smsCode` | String | ✅ | 短信验证码（scene=CANCEL_ACCOUNT） |
| `reason` | String | 否 | 注销原因（用于产品分析，最多 200 字） |

**响应**

```json
{
  "code": 200,
  "message": "注销申请已提交，7日内可撤销",
  "data": {
    "cancelDeadline": "2026-05-23T08:00:00.000Z"
  }
}
```

**错误码**

| code | 说明 |
|------|------|
| `4002` | 验证码错误或已过期 |
| `4093` | 账号已在注销中 |

---

### 6.2 撤销注销申请

```
POST /api/v1/user/account/cancel-revoke
```

**认证**：需要 `Authorization`

**说明**：账号 status=3（注销中）时，在截止日期前可撤销，恢复为 status=1。

**请求 Body**：无

**响应**

```json
{
  "code": 200,
  "message": "注销申请已撤销，账号恢复正常",
  "data": null
}
```

**错误码**

| code | 说明 |
|------|------|
| `4094` | 账号不在注销状态 |
| `4095` | 注销撤销期已过，无法撤销 |

---

## 7. 错误码列表

| code | HTTP Status | 说明 |
|------|------------|------|
| `200` | 200 | 成功 |
| `4001` | 400 | 请求参数格式不合法 |
| `4002` | 400 | 验证码错误或已过期 |
| `4003` | 400 | OAuth authCode 无效 |
| `4011` | 401 | Token 无效（未登录或 token 被吊销） |
| `4012` | 401 | Token 已过期 |
| `4031` | 403 | 账号已封禁 |
| `4032` | 403 | 账号注销中，禁止登录 |
| `4041` | 404 | 资源不存在 |
| `4090` | 409 | 手机号已注册 |
| `4091` | 409 | 邮箱已被占用 |
| `4093` | 409 | 账号已在注销中 |
| `4094` | 409 | 账号不在注销状态 |
| `4095` | 409 | 注销撤销期已过 |
| `4291` | 429 | 请求频率超限 |
| `5001` | 500 | 短信服务不可用 |
| `5002` | 500 | OAuth 服务调用失败 |
| `5000` | 500 | 服务器内部错误 |
