# Vago Knowledge API

> 最后更新：2026-08-31
> 当前阶段：Remould Phase 4A–4D

`KnowledgeSource` 是用户拥有的一份个人旅行知识来源。它独立于 Qdrant、Embedding 和 RAG：即使未启用语义索引，资料仍可以创建、阅读、编辑和管理。

## 1. 响应与鉴权

所有接口使用 `{ code, message, data }` envelope，并通过 `Authorization: Bearer <accessToken>` 做用户级隔离。

## 2. Personal Knowledge Sources

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/knowledge/sources` | 查询当前用户的知识源列表 |
| `GET` | `/api/v1/knowledge/sources/{sourceUuid}` | 查询知识源详情 |
| `POST` | `/api/v1/knowledge/sources` | 创建纯文本知识源 |
| `POST` | `/api/v1/knowledge/sources/files` | 导入 UTF-8 `.md` / `.txt` 文件 |
| `PUT` | `/api/v1/knowledge/sources/{sourceUuid}` | 更新知识源并使旧索引失效 |
| `DELETE` | `/api/v1/knowledge/sources/{sourceUuid}` | 软删除知识源并尽力清理本地原文件/向量 |
| `POST` | `/api/v1/knowledge/sources/{sourceUuid}/index` | 显式请求语义索引 |

`sourceType` 仅表示来源方式：`TEXT`、`URL`、`FILE`。文件格式由 `mimeType` 表示；本阶段实际可上传 `text/plain` 和 `text/markdown`。

## 3. 状态语义

| 字段 | 值 | 说明 |
|------|----|------|
| `parseStatus` | `PENDING` / `PARSING` / `READY` / `FAILED` | 原始资料能否转为可读文本 |
| `indexStatus` | `NOT_INDEXED` / `PENDING` / `INDEXING` / `INDEXED` / `FAILED` | 可选语义索引能力状态 |

创建 TEXT 或成功导入 `.md/.txt` 后，`parseStatus=READY`、`indexStatus=NOT_INDEXED`。只有调用 index 接口后才进入索引队列；关闭 `RAG_ENABLED` 时 CRUD 与文件导入仍可用，索引接口返回不可用。

新 API 不返回 `like`、`liked`、`likeCount`、`viewCount`、`publish`、作者资料、收藏夹或旧 `status/aiStatus` 字段。

## 4. Compatibility Window

`/api/v1/knowledge/guides/*` 仍保留给现有 React 页面和 legacy `guides` 数据使用，但已不再是新的 Knowledge Domain contract。Java 继续承担 discover、like 和 collections；Phase 5 确认其下线后，才会清理旧表、Java bridge 与 `article_id` 兼容字段。
