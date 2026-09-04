# Vago 架构说明

> 最后更新：2026-08-31
> 当前状态：Remould Phase 7 — SwiftUI iOS Foundation
> 目标架构：FastAPI Modular Monolith + React Web + Native iOS

## 1. 架构原则

Vago 的新架构服务于一个更聚焦的产品定位：

> AI-Native Personal Travel Companion — 以个人旅行知识、AI 规划、真实足迹与旅行回忆为核心的个性化旅行搭子。

架构原则：

- **Personal-first**：以单个用户的攻略、行程、足迹、照片、笔记、回忆和偏好为中心。
- **AI-native**：AI 嵌入规划、检索、结构化输出和回忆生成链路，而不是孤立聊天页。
- **Human-in-the-loop**：AI 生成草稿，用户确认后才写入正式 Plan / Trip / Memory。
- **Adaptive Context Retrieval**：根据任务选择 Direct Context、SQL、Profile、RAG，而不是所有请求都强制 RAG。
- **Modular Monolith**：个人项目规模优先采用模块化单体，避免过早微服务化。
- **Mobile-native**：Web 和 iOS 分工明确，iOS 聚焦旅行中采集与轻量体验。

## 2. 当前架构

当前仓库仍采用 React Web + Spring Boot + FastAPI 的渐进迁移架构：

```text
Browser / React SPA (:5173)
    │
    ├── /api/v1/user/**             → FastAPI vago-ai (:8000)
    ├── /api/v1/ai/plans/**         → FastAPI vago-ai (:8000)
    ├── /api/v1/travel/trips/**     → FastAPI vago-ai (:8000)
    ├── /api/v1/travel/plans/**     → FastAPI vago-ai (:8000)
    ├── /api/v1/knowledge/**        → FastAPI vago-ai (:8000)
    ├── /api/v1/ai/chat/**          → FastAPI vago-ai (:8000)
    │
    └── /api/v1/**                  → Spring Boot vago-backend (:8080)

Spring Boot vago-backend
    ├── MySQL
    ├── Redis
    └── WebClient bridge → FastAPI /api/v1/articles/*

FastAPI vago-ai
    ├── Auth / User domain
    ├── Trip / Plan / Itinerary domain
    ├── Personal Travel Knowledge domain
    ├── Redis auth / rate limit checks
    ├── Qdrant
    └── OpenAI / LangChain
```

当前实现中的关键事实：

- Web 路由包括 `/login`、`/`、`/trips`、`/plans`、`/guides`、`/ai`、`/profile`、`/trips/:uuid/itinerary`、`/plans/:uuid/itinerary`。
- AI chat / stream 由前端经 Vite proxy 直连 Python FastAPI。
- 用户、计划、行程核心 CRUD、AI 结构化计划保存已迁移到 FastAPI；新的 `KnowledgeSource` CRUD 与 `.md/.txt` 导入已在 FastAPI 落地。
- 公开攻略发现、点赞、收藏夹暂留 Java Spring Boot；Java 到 Python 的攻略索引桥接链路仍处于兼容窗口。
- 数据库当前落地表集中在 `users`、`user_oauth_bindings`、`user_settings`、`trips`、`plans`、`guides`、`knowledge_sources`、`itinerary_days`、`itinerary_spots`。

这套架构是迁移起点，不再作为最终架构描述。

## 3. 目标架构

目标后端为统一 FastAPI Modular Monolith：

```text
React Web                SwiftUI iOS
    │                        │
    └──────────┬─────────────┘
               │ HTTPS
               ▼
          FastAPI Backend
               │
   ┌───────────┼────────────┐
   │           │            │
Business      AI       Personalization
Modules       Modules  Modules
   │           │            │
   └───────────┼────────────┘
               │
     ┌─────────┼─────────┐
     │         │         │
   MySQL     Redis     Qdrant
                         │
                        LLM
```

建议目录：

```text
services/vago-api/
└── app/
    ├── main.py
    ├── api/
    ├── core/
    │   ├── config.py
    │   ├── security.py
    │   ├── database.py
    │   └── exceptions.py
    ├── auth/
    ├── users/
    ├── trips/
    ├── itineraries/
    ├── knowledge/
    ├── footprints/
    ├── memories/
    ├── personalization/
    ├── agents/
    ├── rag/
    ├── llm/
    └── shared/
```

模块边界：

| 模块 | 职责 |
|------|------|
| `auth` / `users` | 登录、JWT、current user、profile、settings、用户隔离 |
| `trips` / `itineraries` | Plan、Trip、Day、Spot、交通、住宿、预算、状态流转 |
| `knowledge` | 攻略 / Notes 导入、清洗、元数据、索引状态、来源引用 |
| `rag` | Chunking、Embedding、Qdrant 检索、用户级向量隔离 |
| `personalization` | 偏好、历史旅行信号、Context Router |
| `agents` | AI Companion、Tool Calling、结构化输出编排 |
| `footprints` | GPS 采样、轨迹、打卡、区域统计 |
| `memories` | 基于事实数据生成、编辑、分享旅行回忆 |
| `llm` | OpenAI SDK、模型配置、流式输出、结构化 schema validation |

## 4. Personal Context Orchestration

Vago 的个性化不是简单的 `Personalization = RAG`。

目标模型：

```text
Personalization
=
Current User Intent
+
Structured Travel Data
+
Unstructured Personal Knowledge
+
Explicit / Learned Preferences
```

Context Router 应根据用户任务选择上下文来源：

```text
                 User Query
                     │
                     ▼
              Context Router
          ┌──────────┼──────────┐
          ▼          ▼          ▼
 Direct Context     SQL        RAG
 selected sources   trips      sources / notes / memories
          └──────────┼──────────┘
                     ▼
              Preferences
                     ▼
                LLM / Agent
                     ▼
           Personalized Result
```

检索规则：

- 用户明确选择少量攻略或笔记时，优先 Direct Context。
- 查询历史旅行、去过地点、预算统计时，优先 SQL / domain service。
- 面对大量非结构化攻略、笔记、回忆时，使用 RAG / Qdrant。
- 结构化输出进入业务数据前必须经过用户确认。
- Travel Memory 必须区分事实数据和 AI 生成叙事，不能虚构未到访地点。

## 5. API 方向

目标 API 统一为：

```text
/api/v1/auth
/api/v1/users
/api/v1/knowledge
/api/v1/ai
/api/v1/plans
/api/v1/trips
/api/v1/footprints
/api/v1/memories
```

API contract 不应依赖浏览器 cookie、React state 或 Vite proxy。React Web 和 SwiftUI iOS 应共享同一套 domain API。

## 6. 技术选型

保留：

- React、Vite、Tailwind CSS；
- MySQL；
- Redis；
- Qdrant；
- LangChain / OpenAI SDK / SSE；
- 当前已稳定工作的 ingestion、chunking、embedding、vector retrieval。

逐步替换：

- Spring Boot；
- MyBatis；
- JJWT；
- Java WebClient AI bridge。

目标 Python 后端栈：

- FastAPI；
- Pydantic v2；
- SQLAlchemy 2.x；
- Alembic；
- PyJWT / python-jose / equivalent maintained JWT solution；
- Redis client；
- Qdrant client；
- OpenAI SDK；
- pytest。

## 7. 迁移路线

| Phase | 目标 | 状态 |
|------|------|------|
| 0 | Repository inventory + docs alignment | 已完成 |
| 1 | 建立 FastAPI backend foundation | 已完成基础骨架 |
| 2 | 迁移 Auth / User | 已完成并通过本地联调 |
| 3 | 迁移 Trip / Plan / Itinerary | 核心 CRUD 与 AI 保存入口已迁移 |
| 4 | 整合 Knowledge / RAG / AI Companion | 4A–4D 已完成：独立 KnowledgeSource、文本/文件导入、Guide 回填、可选索引 capability |
| 5 | 清理 legacy community / public-feed 能力 | 已完成代码与 API 下线；旧表暂保留 |
| 6 | 更新 Web 产品体验和导航 | 待开始 |
| 7 | 建立 SwiftUI iOS foundation | 已完成：API 配置、手机号登录、Keychain 令牌存储、当前行程/日程与基础个人资料 |
| 8 | 实现 iOS Travel Tracking | 待开始 |
| 9 | 实现 grounded Travel Memory | 待开始 |

迁移原则：

- 先新实现、测试、切换调用方，再删除旧实现。
- 不为了统一技术栈而一次性重写全部系统。
- 不把 public community 迁入新 FastAPI 后端。
- 不把结构化旅行数据塞进向量库代替关系型查询。
- 数据库 destructive migration 需要单独确认。

## 8. 当前风险

- Java 与 Python 共享 JWT secret / Redis 黑名单，迁移 auth 时需保证兼容窗口。
- Web API client 当前按 `/api/v1/user`、`/api/v1/travel`、`/api/v1/ai` 拆分，切换 FastAPI 时需要逐模块迁移 proxy。
- `guides` 表含 `view_count`、`like_count`、`status=published` 等社区语义，兼容窗口内由 Java 继续维护；新 `knowledge_sources` 不暴露这些字段。
- 收藏夹能力可作为个人知识组织能力复用，但不应演变为公共社区关系。
- `docs/database/schema.md` 中有部分未来表设计，`docs/database/db_schema.sql` 是当前较小实现，两者需要在后续 schema remould 中对齐。

更多盘点见 [remould migration inventory](remould-migration-inventory.md)。
