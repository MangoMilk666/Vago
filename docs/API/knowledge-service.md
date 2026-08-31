# Vago Knowledge API

> 最后更新：2026-08-31
> 当前阶段：Remould Phase 4 — Knowledge / RAG Integration

本接口文档描述已迁入 FastAPI 的 Personal Travel Knowledge 能力。Phase 4 先复用旧 `guides` 表，将“我的攻略”重定位为个人旅行知识源，并保留旧前端字段结构。

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

## 2. Personal Guides

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/knowledge/guides/mine` | 查询当前用户自己的知识源列表 |
| `GET` | `/api/v1/knowledge/guides/{guideUuid}` | 查询当前用户自己的知识源详情 |
| `POST` | `/api/v1/knowledge/guides` | 创建知识源 |
| `PUT` | `/api/v1/knowledge/guides/{guideUuid}` | 更新知识源 |
| `DELETE` | `/api/v1/knowledge/guides/{guideUuid}` | 软删除知识源 |
| `POST` | `/api/v1/knowledge/guides/{guideUuid}/index` | 手动触发知识源向量化 |

创建或更新为 `status=1` 时，FastAPI 会将 `aiStatus` 置为 `PENDING(0)`，并通过后台任务调用现有 RAG indexing pipeline。更新为 `status=0` 或删除时，会清理对应 Qdrant chunks。

## 3. 状态语义

| 字段 | 值 | 说明 |
|------|----|------|
| `status` | `0` | 草稿，仅作为 MySQL 资料保存，不进入 RAG |
| `status` | `1` | 已发布/可索引，可进入个人知识库 |
| `aiStatus` | `null` | 草稿未索引 |
| `aiStatus` | `0` | 等待索引 |
| `aiStatus` | `1` | 正在索引 |
| `aiStatus` | `2` | 已完成索引 |
| `aiStatus` | `3` | 索引失败 |

## 4. 暂未迁移

以下功能仍留在 Spring Boot，等待后续产品重塑或清理：

- `/api/v1/travel/guides/discover`
- `/api/v1/travel/guides/{uuid}/like`
- `/api/v1/travel/guides/{uuid}/like` 的取消点赞
- `/api/v1/travel/collections/**`

这些能力带有公共社区或收藏夹组织语义，暂不进入 FastAPI Knowledge 核心。
