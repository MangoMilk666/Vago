# Vago Remould 迁移盘点

> 最后更新：2026-09-02
> 当前阶段：Phase 6 — Web Product Experience

## 1. 仓库状态

执行 `git status --short --untracked-files=all` 时发现一个本轮开始前已经存在的工作区改动：

```text
 M .gitignore
```

该 `.gitignore` 改动由用户维护，本轮不会修改或回滚。

## 2. 当前 Web 路由

在 `apps/vago-web/src/App.jsx` 中发现的当前路由：

| 路由 | 页面 | Remould 分类 |
|------|------|--------------|
| `/login` | `LoginPage` | 保留 / 迁移 |
| `/` | `DashboardPage` | 保留 / 重塑 |
| `/trips` | `TripPage` | 保留 / 迁移 |
| `/plans` | `PlanPage` | 保留 / 迁移 |
| `/guides` | `GuidePage` | 保留 / 重塑为 Knowledge |
| `/ai` | `AiPlanPage` | 保留 / 重塑为 AI Companion |
| `/footprints` | `FuturePage` | 新增产品入口 / 等待数据域实现 |
| `/memories` | `FuturePage` | 新增产品入口 / 等待数据域实现 |
| `/profile` | `ProfilePage` | 保留 / 迁移 |
| `/trips/:uuid/itinerary` | `ItineraryPage` | 保留 / 迁移 |
| `/plans/:uuid/itinerary` | `ItineraryPage` | 保留 / 迁移 |

当前 React Router 中没有发现正在使用的公共 Feed / 社区页面路由。

## 3. Spring Boot 盘点

`services/vago-backend/src/main/java/com/vago` 下的 Controller：

| Controller | 当前职责 | Remould 分类 |
|------------|----------|--------------|
| `UserController` | 认证、个人资料、用户设置 | 保留 / 迁移 |
| `TripController` | 正式行程 CRUD | 保留 / 迁移 |
| `PlanController` | 草稿计划 CRUD | 保留 / 迁移 |
| `TripItineraryController` | 正式行程每日安排编辑 | 保留 / 迁移 |
| `PlanItineraryController` | 草稿计划每日安排编辑 | 保留 / 迁移 |
| `GuideController` | 攻略 CRUD、discover、like、index | 保留个人知识核心；移除公共/点赞语义 |
| `CollectionController` | 攻略收藏夹 | 如果重定位为个人知识组织能力，则保留 |
| `AiController` | 将 AI 结构化计划保存为草稿/正式行程 | 保留 / 迁移 |

值得注意的服务与模型：

- `user/*`：用户、OAuth 绑定、用户设置、JWT 鉴权。
- `travel/*`：行程、计划、攻略、收藏夹、每日安排、景点。
- `ai/*`：Java 保存端点，以及 Java 到 Python 的索引桥接层。
- `GuideLike` 和 `LikeFlushTask`：偏公共社区的互动信号，不属于目标核心能力。
- `Collection` / `CollectionItem`：如果从公共社区语义中拆出来，可以复用为个人知识组织能力。

## 4. FastAPI 盘点

`services/vago-ai/app` 下的当前文件：

| 区域 | 文件 | Remould 分类 |
|------|------|--------------|
| Routers | `chat.py`、`articles.py`、`ai.py` | 保留 / 整合进目标后端 |
| Dependencies | `auth.py`、`rate_limit.py` | 保留概念，后续迁入统一 `core` / `auth` |
| Auth domain | `auth/router.py`、`auth/service.py`、`auth/schemas.py`、`auth/oauth.py` | Phase 2 已新增，承接短信登录、注册、OAuth、刷新 token、退出登录 |
| User domain | `users/models.py`、`users/router.py`、`users/service.py`、`users/schemas.py` | Phase 2 已新增，承接资料与设置读取/更新 |
| Travel domain | `travel/models.py`、`travel/router.py`、`travel/service.py`、`travel/schemas.py` | Phase 3 已新增，承接 Trip / Plan / Itinerary 核心 CRUD |
| Shared / Core | `core/redis.py`、`shared/responses.py` | Phase 2 已新增，集中 Redis 连接池与 Java 兼容响应 envelope |
| Models | `models/schemas.py` | 保留，后续按业务域拆分 |
| RAG 管道 | `cleaner.py`、`chunker.py`、`embedder.py`、`indexer.py`、`metadata_extractor.py`、`vector_store.py` | 保留 |
| AI 编排 | `rag_chain.py`、`plan_extractor.py`、`llm.py` | 保留 / 重塑为自适应上下文检索 |

当前 FastAPI 仍主要是 AI 服务。目标状态是统一的模块化单体后端，逐步吸收 auth、trip、knowledge、AI、footprint、memory 等业务域。

## 5. 数据库 / Schema 盘点

当前可执行 DDL 位于 `docs/database/db_schema.sql`，包含以下表：

| 表 | 当前职责 | Remould 分类 |
|----|----------|--------------|
| `users` | 用户账号 | 保留 / 迁移 |
| `user_oauth_bindings` | OAuth 账号绑定 | 保留 / 迁移 |
| `user_settings` | 用户设置 | 保留 / 扩展为偏好 |
| `trips` | 正式行程 | 保留 / 迁移 |
| `plans` | 草稿计划 | 保留 / 迁移 |
| `guides` | 旅行社区攻略 | 兼容期保留；新个人知识迁至 `knowledge_sources` |
| `knowledge_sources` | 用户私有知识来源 | 保留 / Phase 4A–4D 已新增 |
| `itinerary_days` | 每日行程 | 保留 / 迁移 |
| `itinerary_spots` | 景点 / 活动 | 保留 / 迁移 |

`docs/database/schema.md` 中包含 AI sessions、GPS tracks、fog tiles、photos、archives、statistics 等更完整的未来设计。当前应将其视为目标草案，而 `db_schema.sql` 代表较小的当前实现。

## 6. React API 依赖

当前 Web API client：

| 文件 | Base path | 当前目标 | 迁移说明 |
|------|-----------|----------|----------|
| `apps/vago-web/src/api/user.js` | `/api/v1/user` | Python FastAPI | Phase 2 已通过 Vite proxy 切到 FastAPI auth/users |
| `apps/vago-web/src/api/travel.js` | `/api/v1/travel/trips`、`/api/v1/travel/plans` | Python FastAPI | Phase 3 已通过 Vite proxy 切换 Trip / Plan / Itinerary |
| `apps/vago-web/src/api/travel.js` | `/api/v1/knowledge/guides/*` | Python FastAPI | legacy 兼容；Phase 4E 将切至 `/knowledge/sources` |
| FastAPI Knowledge API | `/api/v1/knowledge/sources/*` | Python FastAPI | Phase 4A–4D 已完成，暂未切换 React |
| `apps/vago-web/src/api/travel.js` | `/api/v1/travel/guides/discover`、`/api/v1/travel/guides/*/like`、`/api/v1/travel/collections` | Java Spring Boot | 暂留 Java，等待社区清理或个人知识组织重设计 |
| `apps/vago-web/src/api/ai.js` | `/api/v1/ai/chat*` | Python FastAPI | AI 整合期间保持路径稳定 |
| `apps/vago-web/src/api/ai.js` | `/api/v1/ai/plans/save-*` | Python FastAPI | Phase 3/4 交界已迁移到 FastAPI travel domain |

## 7. Java 到 Python 依赖

Java 当前依赖 Python AI 服务维护攻略向量索引：

- `VagoAiClient.ingestGuide()` 调用 `POST /api/v1/articles/ingest`。
- `VagoAiClient.deleteGuide()` 调用 `DELETE /api/v1/articles/{articleId}?user_uuid=...`。
- `AiServiceImpl.indexGuideAsync()` 协调 Java 攻略持久化与 Python 向量索引。
- `GuideServiceImpl` 在攻略创建、更新、删除后触发异步索引或删除。

当 Knowledge / RAG 完整整合进目标 FastAPI 后端后，这条 Java 到 Python 的桥接链路应逐步消失。

## 8. 功能分类

| 功能 | 分类 | 说明 |
|------|------|------|
| User / Auth | 保留 / 迁移 | FastAPI 地基稳定后，从 Spring Boot 迁移 |
| JWT / Redis token invalidation | 保留概念 | 迁移期间保持与 Java 的兼容 |
| Guides / knowledge import | 保留 / 重塑 | 产品语言调整为 Personal Travel Knowledge |
| RAG / Qdrant | 保留 | 作为非结构化个人知识的可选上下文来源 |
| AI chat / SSE | 保留 | 继续作为 AI Companion 核心能力 |
| Structured plan extraction | 保留 | 以结构化校验和用户确认为边界 |
| Plan / Trip / Itinerary | Phase 3 已迁移核心 CRUD | 核心业务域 |
| Collections | 有条件保留 | 重定位为个人知识组织，而不是社区功能 |
| Guide likes / discover | 从核心移除 | 除非未来分享能力确实需要，否则不迁入目标后端 |
| Public feed / follow / comments | 移除 | 当前 Web 路由未发现，不应进入目标架构 |
| Footprints | 后续建设 | 需要新增 API、数据库模型和 iOS 支持 |
| Fog-of-world map | 后续建设 | 第一版保持简单，避免过早引入复杂 GIS |
| Photos / notes | 后续建设 | 二进制照片使用对象存储 |
| Travel Memory | 后续建设 | 必须基于真实事实数据生成 |
| Native iOS | 后续建设 | SwiftUI 直接调用 FastAPI public API |

## 9. Phase 1 地基状态

Phase 1 选择继续以 `services/vago-ai` 作为未来统一 FastAPI 后端的迁移种子，而不是立刻创建新的服务目录。这样可以保留已经可运行的 AI / RAG 代码，同时在其周围建立后端地基。

已新增的地基能力：

- `app/main.py`：FastAPI app factory 与应用装配入口。
- `main.py`：兼容现有 `uvicorn main:app` 启动命令的 ASGI 入口。
- `app/api/v1.py`：v1 API 聚合路由，并保持当前外部路径稳定。
- `app/core/config.py`：统一类型化配置，并通过旧 `app.config` re-export 保持兼容。
- `app/core/database.py`：SQLAlchemy `Base`、engine、sessionmaker 和 `get_db` 依赖。
- `app/core/exceptions.py`：统一应用异常和响应 envelope。
- `app/core/security.py`：为后续 domain router 准备类型化 `CurrentUser`。
- `alembic.ini` 与 `migrations/`：Alembic 迁移地基，暂不迁移业务表。
- `pytest.ini` 与 `tests/test_foundation.py`：轻量 foundation 测试。

Phase 1 中刻意保留：

- 现有 RAG ingestion、chunking、embedding、Qdrant vector retrieval 代码。
- 现有 `/api/v1/articles/*`、`/api/v1/ai/chat*`、`/api/v1/ai/plan` 路径。
- 现有由 Java 负责的 auth、user、trip、plan、itinerary API。

测试中发现并修复的重要问题：

- `app.services.chunker` 已改为懒加载 tiktoken encoder，避免导入 FastAPI app 时在 health check 或非 RAG 路由启动前触发网络下载。

## 10. Phase 2 状态

Phase 2 已将用户和认证边界迁入 FastAPI，并已完成本地联调：

- 已基于当前 MySQL schema 定义 `users`、`user_oauth_bindings`、`user_settings` 的 SQLAlchemy ORM models。
- 已新增 `/api/v1/auth/*` 和 `/api/v1/users/*` 路由。
- 已同时挂载 `/api/v1/user/*` 兼容前缀，方便未来 React client 从 Java 切到 FastAPI 时降低改动面。
- 已保持 JWT payload 中 `userUuid`、`userId` 字段，与 Java 侧当前 token 语义兼容。
- 已对齐 Java `LoginVO` 的 `accessToken`、`refreshToken`、`expiresIn`、`isNewUser`、`userInfo` 响应字段。
- 已将短信验证码、刷新 token、JWT 黑名单使用的 Redis 连接收拢到 `core/redis.py`。
- 已迁移 GitHub OAuth 登录，支持按 provider/openId 登录、按 email 绑定老用户、首次 OAuth 自动注册。
- 已迁移账号注销与撤销注销，沿用 `vago:cancel:{userUuid}` Redis 宽限期 key。
- 已补用户资料/设置隔离测试、JWT claim 兼容测试、OAuth 测试、账号生命周期测试，以及 `/api/v1/user/*` 路由层兼容测试。

Phase 2 切换状态：

- React `apps/vago-web/src/api/user.js` 继续使用 `/api/v1/user` 路径，本地 Vite proxy 已将该前缀切到 FastAPI。
- 登录链路前后端联调已完成，暂无问题发现。

## 11. Phase 3 当前状态

Phase 3 已开始将 Trip / Plan / Itinerary 核心业务域迁入 FastAPI：

- 已基于当前 MySQL schema 定义 `trips`、`plans`、`itinerary_days`、`itinerary_spots` 的 SQLAlchemy ORM models。
- 已新增 `/api/v1/travel/trips/*`、`/api/v1/travel/plans/*` 路由，并保持前端当前路径稳定。
- 已迁移 Trip 创建、列表、历史、详情、更新、软删除。
- 已迁移 Plan 创建、列表、详情、更新、软删除，以及 Plan 转正式 Trip。
- 已迁移 Trip / Plan 下的 itinerary days 查询与单日更新。
- 查询 days 时会按日期范围懒初始化缺失 day；更新 day 时支持 spots 整体替换。
- 已通过 Vite proxy 将 `/api/v1/travel/trips` 与 `/api/v1/travel/plans` 切到 FastAPI。
- 已将 `/api/v1/ai/plans/save-draft` 与 `/api/v1/ai/plans/save-trip` 切到 FastAPI，使 AI structured plan 可直接进入 travel domain service。
- Guides / Collections / discover / like 等偏社区或知识组织能力暂不迁移，等待 Knowledge remould。
- 已补 travel service 与 travel API 测试，覆盖用户隔离、计划转换、itinerary 懒初始化与响应 envelope。

## 12. Phase 4 当前状态

Phase 4 已从 AI 保存链路开始整合：

- AI chat / stream 继续由 FastAPI 提供。
- AI structured plan save 已由 Java Spring Boot 迁移到 FastAPI，保存时直接写入 Plan / Trip / Itinerary 表。
- 前端仍调用 `/api/v1/ai/plans/save-*`，但 Vite proxy 已将该前缀切到 FastAPI。
- 新 `KnowledgeSource` 已落地到独立 `knowledge_sources` 表，支持 TEXT 与 `.md/.txt` FILE 来源；创建资料不自动触发 RAG。
- 首条 Alembic revision 会幂等回填未删除 Guide，保留 UUID 以复用兼容期 Qdrant points；旧 `guides` 与 Java 社区链路不删除。
- RAG indexing 已重构为可选 capability：新 payload 写入 `source_uuid` 并保留 `article_id` 兼容别名，重建索引前会清理旧 chunks。
- Java 仍保留公开 discover / like / collections，以及兼容期的 Guide indexing bridge。
- 当前仍不迁移 guide discover / like / public ranking。

## 13. Phase 4E–4F 已完成

- React `/guides` 已切换为个人旅行知识库，仅调用 FastAPI `/api/v1/knowledge/sources/*`，不再暴露 discover、点赞、收藏或发布语义。
- AI 页面不再内嵌 legacy Guide 管理面板；资料整理统一进入个人知识库页面。
- AI 对话支持 `useRag` 开关；关闭时服务端不会向 Agent 注册个人资料检索工具。开启时也仅在 Agent 判断个人资料确有帮助时检索。
- Java community API、legacy `/knowledge/guides/*` 与旧 Guide 前端组件仍在兼容窗口保留，但不再属于主导航路径。

## 14. Phase 5 已完成

- Java Guide、点赞、收藏夹及其 Redis 点赞刷盘任务已下线，不再提供 community 写链路。
- Java 到 Python 的 Guide indexing bridge 与 `/api/v1/articles/*` 兼容入口已移除。
- React 主路径已不使用社区 API；旧社区组件已删除。
- `guides`、`guide_likes`、`collections`、`collection_items` 仍作为 legacy 数据保留，暂不执行 destructive DROP；新功能仅使用 `knowledge_sources`。

## 15. Phase 6 已完成

- 固定 Web 顶部导航收敛为首页、知识库、AI 搭子、计划、行程、足迹、回忆和个人资料，不再出现社区入口。
- 首页保留简洁的多入口卡片布局，并以新版个人旅行领域名称进入对应模块。
- 新增足迹与回忆的稳定路由入口；在对应 FastAPI 数据域、iOS 采集链路尚未落地前，它们不会伪装成已可用功能。
- 行程、计划、知识库、AI 和个人资料页使用统一的页面背景、内容宽度和面板样式，保留既有紫色色调。

## 16. 推荐下一步

- 开始 Phase 7：建立 SwiftUI iOS 基础工程，并接入当前 FastAPI 的登录、个人资料和行程查看能力。
- 在 Phase 8 实现真实的足迹采集与同步后，再将 Web 足迹入口替换为可浏览的领域页面。
- 在 Phase 9 有足够的真实行程、足迹与笔记数据后，再实现 AI 旅行回忆生成与编辑。

## 17. Trip 生命周期状态

- 正式 Trip 使用 `未开始(1) / 进行中(2) / 已结束(3)`，而 Plan 仍使用独立的草稿/已转换状态。
- 直接创建、计划转换及 AI 保存的正式行程默认均为未开始；每位用户最多同时有一个进行中的 Trip。
- 已结束 Trip 归入历史行程，只允许回顾，不允许更新、删除或编辑每日安排。
