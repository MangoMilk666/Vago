# Travel Core API

**状态：当前 FastAPI 接口摘要。** 路由在 `services/vago-ai/app/travel/router.py`，请求和响应字段在同目录 `schemas.py`。所有路径以 `/api/v1/travel` 开头，需 `Authorization: Bearer <accessToken>`；业务记录按认证用户隔离。成功响应使用 `{ code, message, data }`。

## Trip

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST / GET | `/trips` | 创建正式行程 / 列出自己的行程 |
| GET | `/trips/history` | 列出历史行程 |
| GET / PUT / DELETE | `/trips/{tripUuid}` | 详情 / 修改 / 软删除 |
| POST | `/trips/{tripUuid}/start` | 开始未开始的行程 |
| POST | `/trips/{tripUuid}/switch` | 在一次服务端事务中结束当前行程并开始指定行程 |
| POST | `/trips/{tripUuid}/finish` | 结束进行中的行程 |
| GET | `/trips/{tripUuid}/days` | 读取正式行程每日安排 |
| PUT | `/trips/{tripUuid}/days/{dayIndex}` | 修改指定日期安排 |

服务端执行业务状态约束；已结束行程的只读边界不能仅靠客户端按钮控制。

## Plan

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST / GET | `/plans` | 创建草稿 / 列出草稿 |
| GET / PUT / DELETE | `/plans/{planUuid}` | 详情 / 修改 / 软删除 |
| POST | `/plans/{planUuid}/convert` | 将计划转换为正式行程 |
| GET | `/plans/{planUuid}/days` | 读取计划每日安排 |
| PUT | `/plans/{planUuid}/days/{dayIndex}` | 修改指定日期安排 |

`/api/v1/ai/plans/save-draft` 和 `/api/v1/ai/plans/save-trip` 是 AI 结构化计划的保存入口，路由在 `app/routers/ai.py`，持久化通过 Travel domain。它们不等于 Agent 已具备自主创建或修改正式行程的审批闭环。

旧文档中的“部分 Travel API 仍在 Spring Boot”是迁移期状态；当前仓库的 Travel Core 由 FastAPI 承载。
