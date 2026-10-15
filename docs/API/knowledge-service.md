# Personal Knowledge API

**状态：当前 FastAPI 接口摘要。** 路由在 `services/vago-ai/app/knowledge/router.py`，请求和响应字段在同目录 `schemas.py`。所有路径以 `/api/v1/knowledge` 开头，需 Bearer token，并按认证用户隔离；成功响应使用 `{ code, message, data }`。

## KnowledgeSource

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / POST | `/sources` | 列出自己的资料 / 创建纯文本资料 |
| GET / PUT / DELETE | `/sources/{sourceUuid}` | 详情 / 修改 / 软删除 |
| POST | `/sources/files` | 导入 UTF-8 `.md` 或 `.txt` 文件，multipart 表单可带标题、目的地和 JSON 标签数组 |
| POST | `/sources/{sourceUuid}/index` | 显式请求可选语义索引 |

资料的 CRUD 不依赖 Qdrant。修改资料会使旧索引失效；未开启 RAG 或向量服务不可用时，索引请求返回不可用，资料本身仍可管理。`parseStatus` 与 `indexStatus` 分别表达文本解析和可选索引状态。当前文件导入只支持 `.md`、`.txt`，不把 `URL` 来源类型误写成已支持 URL 抓取。

## 旧 Guide 兼容入口

当前代码仍注册 `/guides/mine`、`/guides/{guideUuid}` 的 GET，以及 `/guides` 创建、`/guides/{guideUuid}` 更新/删除、`/guides/{guideUuid}/index`。它们服务于现有旧数据或调用方，不是新 KnowledgeSource 的首选契约。不要沿用迁移期文档所述的“Java 仍承载 discover、like、collections”作为当前部署事实；公共社区能力不属于当前核心产品。
