# Vago（叠迹）

> AI-Native Personal Travel Companion — 以个人旅行知识、AI 规划、真实足迹与旅行回忆为核心的个性化旅行搭子。

## 项目简介

**Vago（叠迹）** 是一个面向自由行用户的 AI-Native 个性化旅行应用。它把用户分散在攻略、笔记、历史行程、照片和足迹中的旅行信息沉淀为个人旅行知识，通过 AI 辅助用户完成旅行前规划、旅行中记录和旅行后回忆生成。

当前项目正处于 **remould / 渐进式重塑阶段**：保留已有 React Web、Java 后端、FastAPI AI、MySQL、Redis、Qdrant 等可运行资产，同时将产品与技术架构逐步从“旅行社区 + RAG 攻略规划”调整为：

```text
Personal Travel Knowledge
        ↓
Adaptive Personal Context Retrieval
        ↓
AI Travel Companion
        ↓
Structured Travel Plan
        ↓
User Confirmation
        ↓
Actual Trip
        ↓
GPS / Photos / Notes
        ↓
Travel Footprint
        ↓
AI-generated Travel Memory
        ↓
Personal Travel Profile / Memory
        ↓
Future Personalized Planning
```

## 核心定位

Vago 不再以公共旅行社区或信息流为主线。新的核心能力是 **Personal Travel Intelligence**：

- 整理用户自己的旅行攻略、笔记和资料；
- 根据用户意图选择合适的个人上下文来源；
- 用 AI 生成可确认、可编辑、可落库的结构化行程；
- 在实际旅行中记录 GPS、照片、笔记和打卡；
- 基于真实旅行数据生成可回顾、可分享、可复用的旅行回忆；
- 将历史旅行逐步沉淀为未来规划可用的个人偏好和记忆。

RAG / Qdrant 是其中用于检索大量非结构化个人资料的技术能力，不再作为 Vago 的唯一产品卖点，也不应替代适合 SQL 查询的结构化旅行数据。

## 产品模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 用户与认证 | Phase 2 已迁移 | 手机号 / OAuth、JWT、用户级数据隔离、个人设置 |
| Personal Travel Knowledge | Phase 4A–4F 已落地 | 独立 KnowledgeSource、纯文本与 `.md/.txt` 导入、用户隔离、Web 知识库与可选语义索引 |
| AI Travel Companion | Phase 4 起步整合 | 多轮对话、SSE、Tool Calling、结构化计划输出、用户确认后保存 |
| Plans / Trips / Itinerary | Phase 3 核心 CRUD 已迁移 | 草稿计划、正式行程、每日安排、景点、交通、住宿、预算 |
| Footprints | 后续建设 | GPS 采样、轨迹、打卡、地点统计、地图可视化 |
| Fog-of-World Map | 后续建设 | 基于真实移动轨迹解锁地图区域 |
| Photos / Notes | 后续建设 | 拍照、相册选择、EXIF / 时间 / 位置绑定、Trip / Spot 关联 |
| Travel Memory | 后续建设 | 基于事实数据生成可编辑旅行总结、timeline、highlights、分享卡片 |
| Public Community | 停止作为主线 | Feed、点赞、关注、陌生人社交不迁移到目标后端；分享能力可保留 |
| Native iOS | 后续建设 | SwiftUI 客户端，聚焦当前行程、GPS、地图、照片、轻量 AI |

## 当前架构

当前仓库仍是可运行的混合架构：

```text
React Web (Vite)
    ├── /api/v1/user/**             → FastAPI vago-ai
    ├── /api/v1/travel/trips/**     → FastAPI vago-ai
    ├── /api/v1/travel/plans/**     → FastAPI vago-ai
    ├── /api/v1/knowledge/**        → FastAPI vago-ai
    ├── /api/v1/ai/chat/**          → FastAPI vago-ai
    └── /api/v1/**                  → Spring Boot vago-backend

Spring Boot vago-backend
    ├── Public Guide discover / like
    ├── Collection CRUD
    └── Java → Python guide indexing bridge

FastAPI vago-ai
    ├── Auth / User
    ├── Trip / Plan / Itinerary CRUD
    ├── Personal KnowledgeSource CRUD / local text-file import
    ├── AI structured plan save
    ├── AI chat / SSE
    ├── article ingestion
    ├── cleaner / chunker / embedder
    ├── Qdrant vector store
    ├── RAG / Tool-Calling Agent
    └── structured plan extraction
```

当前架构是迁移起点，不是最终目标。

## 目标架构

目标后端采用 **FastAPI Modular Monolith**，不是微服务：

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

建议目标目录：

```text
services/vago-api/
└── app/
    ├── api/
    ├── core/
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

## 技术方向

| 层次 | 当前 | 目标 |
|------|------|------|
| Web | React + Vite + Tailwind CSS | 保留 |
| iOS | 未实现 | Swift + SwiftUI + MapKit + Core Location |
| Backend | Spring Boot + FastAPI AI | 逐步迁移为 FastAPI Modular Monolith |
| Relational DB | MySQL | 保留 |
| Cache | Redis | 保留 |
| Vector DB | Qdrant | 保留，作为可选 context source |
| AI | LangChain + OpenAI SDK + SSE | 保留可运行能力，重构为 context orchestration |
| Auth | JJWT / Java interceptor | 迁移到 FastAPI auth dependency |

暂不引入 Kubernetes、Service Mesh、复杂事件总线、GraphQL、CQRS 或为了展示而存在的多 Agent 架构。

## 目录结构

```text
Vago/
├── apps/
│   └── vago-web/                 # React Web
├── services/
│   ├── vago-backend/             # 当前 Spring Boot 后端，后续逐步退场
│   ├── vago-ai/                  # 当前 FastAPI AI 服务，后续演进为统一后端基础
│   └── nginx/
├── docs/
│   ├── prd/PRD.md
│   ├── architecture.md
│   ├── remould-migration-inventory.md
│   ├── API/
│   └── database/
├── dev-up.sh
├── .env.example
└── LICENSE
```

## 迁移状态

当前 remould 进度为 **Phase 4 — Knowledge / RAG / AI Companion Integration 已完成 4A–4F**。

迁移优先级：

1. 建立统一 FastAPI backend foundation；已完成基础骨架
2. 迁移 Auth / User；已完成 FastAPI 迁移并通过本地联调
3. 迁移 Trip / Plan / Itinerary；已完成核心 CRUD、AI 结构化计划保存与 Vite proxy 切换
4. 整合 Knowledge / RAG / AI Companion；已完成独立 KnowledgeSource、Guide 回填、Web 知识库与可选 Agent retrieval
5. 清理 legacy community / public-feed 相关能力；
6. 更新 Web 产品体验；
7. 建立 SwiftUI iOS foundation；
8. 实现 iOS Travel Tracking；
9. 基于真实 footprint / notes / photos 生成 Travel Memory。

详见 [remould migration inventory](docs/remould-migration-inventory.md)。

## 文档

- [产品需求文档](docs/prd/PRD.md)
- [项目架构说明](docs/architecture.md)
- [Remould 迁移盘点](docs/remould-migration-inventory.md)
- [数据库文档](docs/database/schema.md)
- [用户服务 API](docs/API/user-service.md)
- [旅行核心 API](docs/API/travel-service.md)
- [个人知识 API](docs/API/knowledge-service.md)

## License

[Apache License 2.0](LICENSE)
