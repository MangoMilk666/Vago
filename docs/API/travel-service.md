# Vago Travel Core API

> 最后更新：2026-08-31
> 当前阶段：Remould Phase 3 — Trip / Plan / Itinerary Migration

本接口文档描述已从 Spring Boot 迁入 FastAPI 的旅行核心域能力。前端仍使用 `/api/v1/travel` 作为业务前缀，Vite proxy 已将 `trips`、`plans` 及其 itinerary 子路径切到 FastAPI。

## 1. 响应 Envelope

所有接口继续返回 Java 兼容的统一响应结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

鉴权继续使用 `Authorization: Bearer <accessToken>`，并通过 current user dependency 做用户级数据隔离。

## 2. Trips

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/travel/trips` | 创建正式行程 |
| `GET` | `/api/v1/travel/trips` | 查询当前用户行程列表 |
| `GET` | `/api/v1/travel/trips/history` | 查询历史行程 |
| `GET` | `/api/v1/travel/trips/{tripUuid}` | 查询行程详情 |
| `PUT` | `/api/v1/travel/trips/{tripUuid}` | 更新行程 |
| `DELETE` | `/api/v1/travel/trips/{tripUuid}` | 软删除行程 |

Trip 创建时会生成新的业务 `uuid`，默认 `status=1`、`isDeleted=0`。查询和更新均限定当前用户，跨用户访问会返回无权限错误。

## 3. Plans

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/travel/plans` | 创建草稿计划 |
| `GET` | `/api/v1/travel/plans` | 查询当前用户计划列表 |
| `GET` | `/api/v1/travel/plans/{planUuid}` | 查询计划详情 |
| `PUT` | `/api/v1/travel/plans/{planUuid}` | 更新计划 |
| `DELETE` | `/api/v1/travel/plans/{planUuid}` | 软删除计划 |
| `POST` | `/api/v1/travel/plans/{planUuid}/convert` | 将计划转换为正式行程 |

Plan 创建时默认 `status=0`。转换为 Trip 后会把 plan 下的 itinerary days 和 spots 复制到新 Trip，并将 Plan 标记为已转换。

## 4. AI Structured Plan Save

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/ai/plans/save-draft` | 将 AI 结构化行程保存为草稿 Plan |
| `POST` | `/api/v1/ai/plans/save-trip` | 将 AI 结构化行程保存为正式 Trip |

这两个接口保持旧 Java `AiPlanSaveVO` contract，成功时返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "uuid": "created-plan-or-trip-uuid",
    "type": "plan"
  }
}
```

保存逻辑已进入 FastAPI travel domain：AI structured plan 的 `days` 和 `spots` 会直接写入 `itinerary_days` / `itinerary_spots`。保存正式 Trip 时要求 `start_date` 与 `end_date` 必填且格式合法。

## 5. Itinerary Days

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/travel/trips/{tripUuid}/days` | 查询正式行程每日安排 |
| `PUT` | `/api/v1/travel/trips/{tripUuid}/days/{dayIndex}` | 更新正式行程某一天 |
| `GET` | `/api/v1/travel/plans/{planUuid}/days` | 查询草稿计划每日安排 |
| `PUT` | `/api/v1/travel/plans/{planUuid}/days/{dayIndex}` | 更新草稿计划某一天 |

查询 days 时会根据 Trip / Plan 的日期范围懒初始化缺失的 `itinerary_days`。更新 day 时，如果请求体包含 `spots`，会先删除该天旧 spots，再按请求顺序重建；如果未传 `spots`，则只更新 day 字段并保留原 spots。

## 6. 暂未迁移

以下 `/api/v1/travel` 子域仍保留在 Spring Boot，等待 Knowledge remould 阶段处理：

- `/api/v1/travel/guides/**`
- `/api/v1/travel/collections/**`
- guide discover / like / public ranking 等社区语义
