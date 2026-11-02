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

向量模型维度与现有 Qdrant collection 不一致时，启动检查会使 RAG 暂不可用；显式索引请求返回 `RAG_UNAVAILABLE`，检索工具显示实际维度差异。更换模型后，先设置与新模型输出一致的 `EMBEDDING_DIM`，再从 `services/vago-ai` 执行 `sh deploy.sh --rebuild-knowledge-index <新collection名称>`。脚本从 MySQL 中已解析的个人知识原文重新索引到新 collection，核对文本块数量；它不删除旧 collection，也不自动切换读取配置。核对新索引后，将 `QDRANT_COLLECTION` 改为新名称并重启服务。普通 `launch.sh` 不触发重建。

也可设置环境变量 `REBUILD_RAG_INDEX_IF_DIM_CHANGE=true`：服务启动时调用当前模型确认真实维度；发现现有 collection 维度不同后，将 RAG 标记为暂不可用，并启动一次后台重建。核对文本块数量后，本进程自动切换到新 collection。重建失败则保持不可用并记录异常，旧 collection 保留。默认值为 `false`，此时维度冲突直接报错且不重建。若模型真实维度也与 `EMBEDDING_DIM` 不同，自动重建会在本进程使用真实维度，维护人员仍须更新环境变量。自动重建成功后应将日志中的新名称写入 `QDRANT_COLLECTION`，供下次启动使用；生产环境若启用多个服务进程，应先保证只有一个进程承担重建任务。

## 旧 Guide 兼容入口

当前代码仍注册 `/guides/mine`、`/guides/{guideUuid}` 的 GET，以及 `/guides` 创建、`/guides/{guideUuid}` 更新/删除、`/guides/{guideUuid}/index`。它们服务于现有旧数据或调用方，不是新 KnowledgeSource 的首选契约。不要沿用迁移期文档所述的“Java 仍承载 discover、like、collections”作为当前部署事实；公共社区能力不属于当前核心产品。
