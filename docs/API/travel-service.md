# Travel Core API

**状态：当前 FastAPI 接口摘要。** 路由在 `services/vago-ai/app/travel/router.py`，请求和响应字段在同目录 `schemas.py`。所有路径以 `/api/v1/travel` 开头，需 `Authorization: Bearer <accessToken>`；业务记录按认证用户隔离。成功响应使用 `{ code, message, data }`。

## Trip

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST / GET | `/trips` | 创建正式行程 / 列出自己的行程 |
| GET | `/trips/history` | 列出历史行程 |
| GET / PUT / DELETE | `/trips/{tripUuid}` | 详情 / 修改 / 软删除 |
| POST | `/trips/{tripUuid}/start` | 将指定行程状态设为进行中（兼容旧客户端） |
| POST | `/trips/{tripUuid}/switch` | 兼容旧客户端；只更新目标行程，不联动其他行程 |
| POST | `/trips/{tripUuid}/finish` | 将指定行程状态设为已结束（兼容旧客户端） |
| GET | `/trips/{tripUuid}/days` | 读取正式行程每日安排 |
| PUT | `/trips/{tripUuid}/days/{dayIndex}` | 修改指定日期安排 |

`PUT /trips/{tripUuid}` 可通过 `status` 直接设置 `1=未开始`、`2=进行中` 或 `3=已结束`，每个 Trip 独立变更，允许多个行程同时处于进行中。已结束行程仍不能修改标题、日期等其他资料，除非先将状态切回未结束状态。iOS 前台的唯一足迹记录目标由用户单独选择，不由 Trip 状态推断；服务端写入足迹时校验用户归属，不限制 Trip 状态。

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
