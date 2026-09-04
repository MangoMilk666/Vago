---
name: project-remould-skill
date: 2026-08-28
description: 重塑 Vago 项目的产品定位、功能边界与技术架构，将其从偏旅行社区的混合技术栈项目逐步演进为以个人旅行知识、AI Agent、旅行足迹与旅行回忆为核心的 AI-Native 个性化旅行应用。
---

# Project Remould Skill

## Purpose

本 Skill 用于指导 Codex 对现有 Vago 项目进行**渐进式产品重塑与架构迁移**。

目标不是简单重写代码，也不是为了“技术栈统一”而机械迁移，而是在尽量复用已有成果的前提下，将 Vago 从一个包含旅行社区、旅行管理与 AI 功能的混合型项目，重新聚焦为：

> **AI-Native Personal Travel Companion — 以用户个人旅行知识为核心，贯穿旅行前规划、旅行中记录与旅行后回忆的个性化旅行搭子。**

重塑后的核心闭环：

```text
Personal Travel Knowledge
        ↓
Personal RAG
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

本项目是个人作品与求职展示项目，因此优先级依次为：

1. 产品主线清晰；
2. 核心功能形成完整闭环；
3. AI 能力真正进入业务核心；
4. 架构合理且容易解释；
5. Web 与 iOS 端职责明确；
6. 技术复杂度与个人维护规模匹配；
7. 避免为了展示技术而引入无实际必要的微服务或框架。

---

# Product Positioning

## Target Positioning

Vago 不再以 **Travellers' Community / 旅行社区** 为核心定位。

新的产品定位：

> **Vago is an AI-native personal travel companion that turns a user's fragmented travel knowledge into personalized plans, records real-world journeys, and transforms them into reusable travel memories.**

中文表达：

> **Vago（叠迹）是一个 AI-Native 个性化旅行搭子，将用户零散的旅行知识沉淀为个人知识库，通过 AI 辅助旅行规划，并将实际旅行过程中的地点、照片和记录转化为长期可回顾、可复用的旅行记忆。**

## Product Principles

### Personal-first

优先服务单个用户自己的：

- 攻略；
- 偏好；
- 行程；
- 足迹；
- 照片；
- 回忆；
- 历史旅行数据。

不要再围绕公共 Feed 或陌生人社交设计核心流程。

### AI-native, not AI-added

AI 不应只是独立的聊天页面或附加按钮。

AI 应参与核心工作流：

- 理解旅行需求；
- 检索个人知识；
- 生成个性化建议；
- 形成结构化行程；
- 根据实际旅行数据生成回忆；
- 在未来利用历史旅行形成更强的个性化。

### Human-in-the-loop

AI 可以：

- 推荐；
- 检索；
- 总结；
- 生成草稿；
- 提议结构化行程。

AI 不应未经用户确认直接：

- 创建正式行程；
- 修改重要旅行计划；
- 覆盖用户记录。

结构化 AI 输出进入正式业务数据前，应保留用户确认步骤。

### Mobile-native experience

移动端不复制完整 Web。

Web 侧重点：

- 攻略整理；
- 知识库管理；
- 复杂 AI Planning；
- 行程编辑；
- 历史旅行管理；
- 大屏足迹/回忆浏览。

iOS 侧重点：

- 当前行程查看；
- GPS 足迹采集；
- 迷雾地图；
- 拍照与照片关联；
- 快速笔记；
- 轻量 AI 问答；
- 旅行回忆浏览；
- 移动端分享。

---

# Feature Scope

对现有功能进行 `KEEP / REMOVE / BUILD / DEFER` 分类。

## KEEP — 保留并迁移

以下功能属于 Vago 新定位的核心资产，应保留。

### User and Authentication

保留：

- 用户账户；
- JWT 鉴权；
- 用户级数据隔离；
- 个人设置。

迁移时可以重新实现，但对外行为应尽量保持兼容。

### Personal Travel Knowledge Base

保留并强化：

- 攻略文本导入；
- URL 内容导入；
- 文本清洗；
- Metadata extraction；
- Chunking；
- Embedding；
- Qdrant；
- `user_uuid` 级向量隔离；
- 攻略删除与重新索引；
- 语义检索；
- 来源引用。

这是 Vago 的核心长期数据资产之一。

但必须明确：

> **RAG 不是 Vago 的核心产品卖点，也不是所有个性化请求的默认执行路径。**

Vago 的核心能力是 **Personal Travel Intelligence / Personal Context Orchestration**。

RAG 只负责其中一类问题：

> 从用户长期积累的大量、非结构化旅行资料中，检索当前任务真正相关的个人上下文。

因此不要把：

```text
Personalization = RAG
```

作为产品或架构假设。

更准确的模型是：

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

RAG 只对应其中的 **Unstructured Personal Knowledge retrieval**。

### AI Travel Companion

保留：

- 自然语言旅行问答；
- Personal Context Retrieval；
- Tool Calling；
- SSE streaming；
- 多轮交互；
- Structured Output；
- 结构化行程生成；
- 用户确认后保存为 Plan / Trip。

其中 Personal Context Retrieval 可以来自：

- 直接传入的用户选中资料；
- SQL 中的历史 Trip / Spot / Budget / GPS 数据；
- 用户 Profile / Preferences；
- 对大量非结构化攻略、笔记、回忆执行的语义检索 / RAG。

重塑过程中应避免把它退化成简单的 `prompt -> LLM -> text`，也不要把所有个性化请求强制绑定到 RAG。

### Trip / Plan / Itinerary

保留：

- Trip；
- Plan；
- Itinerary Day；
- Spot；
- Transportation；
- Accommodation；
- Notes；
- Budget 等当前仍有实际用途的数据。

迁移时允许重新整理 schema，但不要无理由破坏已有用户数据模型。

### Personal Profile / Preferences

保留个人设置，并逐步扩展：

- travel preferences
- preferred pace；
- interests；
- budget tendencies；
- historical destination signals。

该模块未来可以成为 Personalization / Agent Memory 的输入。

---

# REMOVE — 不再迁移或继续开发

以下功能不再作为新 Vago 的产品主线。

## Public Travel Community

原则上停止维护并逐步移除：

- Public Feed；
- 类小红书信息流；
- 用户发帖社区；
- 点赞；
- 关注；
- 评论；
- 面向陌生用户的社交关系图；
- 社区推荐算法；
- 为社区增长而设计的运营模块。

### Migration Rule

如果这些功能仍存在于旧代码中：

- 不要迁移到新的 FastAPI backend；
- 不要为了兼容旧社区接口而扩大新架构；
- 在确认没有新核心模块依赖后再删除旧实现；
- 如有可复用的数据模型、UI 或上传能力，可以抽取后复用；
- 不要因为“已经写过”而继续保留失去产品价值的模块。

## Social Sharing is NOT removed

“社区”被弱化，但“分享”可以保留。

未来可以支持：

- 分享某次旅行；
- 分享足迹地图；
- 分享 AI 旅行回忆；
- 分享 itinerary；
- 生成静态旅行卡片；
- `PRIVATE / UNLISTED / PUBLIC` 可见性。

分享是旅行结果的输出能力，不应重新演变为一个完整社交平台。

---

# BUILD — 后续核心开发

## Travel Footprint

开发旅行足迹体系：

- GPS location sampling；
- visited places；
- check-in；
- route / trajectory；
- city / region / country statistics；
- trip 与 location record 关联；
- map visualization。

必须考虑：

- 定位权限；
- 数据隐私；
- 采样频率；
- 电量消耗；
- 后台定位；
- 离线缓存；
- 网络恢复后的同步。

服务器仍是长期数据 source of truth

## Fog-of-World Style Map

开发迷雾地图体验：

- 用户移动后解锁区域；
- 当前旅行范围；
- 历史旅行范围；
- 世界 / 国家 / 城市维度探索统计。

第一版优先保证：

- 可运行；
- 数据结构清晰；
- 地图渲染稳定。

不要为了视觉效果过早引入复杂 GIS 基础设施。

## Travel Photo and Notes

开发：

- 拍照；
- 从相册选择；
- 时间戳；
- 经纬度；
- Trip / Day / Spot 绑定；
- Caption / Note；
- 服务端持久化。

照片二进制资源不建议直接存关系型数据库。

## AI-generated Travel Memory

这是新的核心 AI 功能之一。

输入可以包括：

- structured itinerary；
- actual GPS footprint；
- visited spots；
- photos metadata；
- user notes；
- trip duration；
- statistics；
- optional user preferences。

输出可以包括：

- 旅行总结；
- timeline；
- highlights；
- memorable moments；
- city / route summary；
- AI-generated narrative；
- shareable travel card data。

要求：

- AI 生成内容与事实数据分离；
- 不得让模型虚构用户未到访地点；
- 对由 GPS / 用户记录支持的事实尽量保持 grounded；
- 用户可以编辑 AI 生成文本。

## Personal Travel Memory

逐步把过去旅行转化为可复用上下文：

- visited destinations；
- favorite categories；
- preferred itinerary density；
- recurring preferences；
- travel history summaries。

未来 AI planning 可以使用这些信息进行个性化，但初期不要过度设计复杂“长期自主 Agent”。

## iOS App

新增原生 iOS 客户端。

推荐技术：

```text
Swift
SwiftUI
async/await
URLSession
Codable
MapKit
Core Location
Photos / PhotosUI
UserNotifications
```

iOS App 直接调用新的 FastAPI public API。

不要让 iOS App 依赖旧 Spring Boot 服务。

---

# DEFER — 暂缓

以下功能不是当前 remould 阶段重点：

- Android；
- React Native；
- 大规模公开社交；
- 推荐 Feed；
- 多 Agent 为了多 Agent 而多 Agent；
- Kubernetes；
- Service Mesh；
- API Gateway；
- 服务发现；
- 复杂事件总线；
- 大规模 GIS 服务；
- 商业订阅体系；
- App Store 正式发布；
- 高级离线地图；
- OCR / screenshot ingestion；
- 复杂多模态 Agent。

除非用户后续明确要求，否则不要主动扩大 scope。

---

# Target Architecture

最终后端目标：

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
Business      AI         Personalization
Modules       Modules       Modules
   │           │            │
   └───────────┼────────────┘
               │
     ┌─────────┼─────────┐
     │         │         │
 Relational   Redis    Qdrant
    DB                    │
                          LLM
```

后端采用 **Modular Monolith**，不是微服务。

## Suggested Backend Modules

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

不要为了模仿 Spring Boot 而机械创建过深目录，但应保持：

- API / router 与业务逻辑分离；
- 数据访问与 LLM 调用分离；
- Pydantic API schema 与 ORM model 不混为一体；
- AI module 与业务 domain 有明确 interface。

---

# Backend Technology Direction

## Keep

暂时保留：

- React；
- Vite；
- Tailwind CSS；
- MySQL；
- Redis；
- Qdrant；
- LangChain；
- OpenAI SDK；
- SSE。

除非迁移过程中发现明确问题，否则不要顺手更换这些技术。

## Replace

逐步淘汰：

```text
Spring Boot
MyBatis
JJWT
Spring WebClient AI proxy
```

由 Python backend 对应能力替代。

## Suggested Python Backend Stack

```text
FastAPI
Pydantic v2
SQLAlchemy 2.x
Alembic
PyJWT / python-jose / equivalent maintained JWT solution
Redis client
Qdrant client
LangChain / LangGraph only where justified
OpenAI SDK
pytest
```

如果当前 MySQL 可以继续满足需求，则迁移阶段不更换数据库。

不要在同一轮 remould 中同时执行：

- Java → Python；
- MySQL → PostgreSQL；
- React → 新框架；
- LangChain → 新 Agent 框架；

除非存在硬性技术原因。

一次只处理一个主要变化维度。

---

# Migration Strategy

使用渐进式迁移，不进行 Big-Bang Rewrite。

## Phase 0 — Repository Inventory

Codex 在修改代码前必须先：

1. 阅读 README；
2. 阅读 PRD；
3. 阅读 architecture docs；
4. 枚举当前 Web routes；
5. 枚举 Spring Boot controllers / services / models；
6. 枚举 FastAPI routers / services；
7. 枚举数据库 schema / migrations / SQL；
8. 标注每个功能：
   - KEEP；
   - REMOVE；
   - MIGRATE；
   - BUILD LATER；
9. 找出 React 对 Java API 的依赖；
10. 找出 Java 对 Python AI API 的依赖。

输出迁移清单后再进入代码修改。

## Phase 1 — Establish New FastAPI Backend Foundation

优先把现有 `vago-ai` 从“AI 子服务”调整为未来主后端，或创建明确的新 FastAPI app 后逐步吸收 AI 模块。

要求：

- 不复制已有 RAG 代码；
- 保留现有可运行 AI 能力；
- 建立统一 configuration；
- 建立 SQLAlchemy；
- 建立 Alembic；
- 建立统一 exception handling；
- 建立 auth dependency；
- 建立 API versioning；
- 建立测试结构。

## Phase 2 — Authentication and User Migration

优先迁移：

- login；
- register；
- JWT；
- current user；
- profile；
- Redis token invalidation，如仍确有需要。

验收：

- React 可以切换到 FastAPI auth；
- 原有账号数据可继续使用，或提供明确 migration；
- 用户级数据隔离测试通过。

通过后才考虑删除对应 Spring Boot module。

## Phase 3 — Trip Domain Migration

迁移：

- Plan；
- Trip；
- Itinerary；
- Days；
- Spots；
- related CRUD。

原则：

- 尽量保持 API contract；
- 如果需要修改 contract，同步更新 Web；
- 增加 API tests；
- 保证 AI structured plan 可以直接进入 FastAPI domain service。

这一步完成后，Java → Python AI proxy 链路应开始消失。

## Phase 4 — Knowledge / RAG Integration

把原 FastAPI AI service 的：

- articles；
- ingestion；
- cleaner；
- chunker；
- embedder；
- vector store；
- RAG；
- agent；
- plan extractor；
- streaming

整合进统一 backend。

目标链路：

```text
React / iOS
    ↓
FastAPI
    ├── relational business data
    ├── RAG
    ├── Agent
    └── structured output
```

不再经过：

```text
Client
  ↓
Spring Boot
  ↓
FastAPI AI
```

## `Phase 4A`

增加第一条正式 Alembic revision，创建 `knowledge_sources`；实现纯 TEXT CRUD，不接触 Qdrant。

## `Phase 4B`

增加 local storage 和 `.md/.txt` 上传、解析；URL 只保留模型能力，暂不实现抓取。

## `Phase 4C`

执行幂等 Guide backfill，保留 UUID；校验用户数、资料数、内容摘要和索引状态映射。

## `Phase 4D`

将索引代码泛化为可选 capability，增加旧 `article_id` 兼容层，修复重新索引残留 chunks。

## `Phase 4E`

React Knowledge 页面和 AI Planning 切换到 `/knowledge/sources`，移除新链路中的社区字段。

## `Phase 4F`

将 Agent 工具改为可选 Personal Knowledge retrieval；暂不实现复杂 Context Router。

## Phase 5 — Remove Legacy Community

社区模块不迁移。冻结并下线 Java community 写链路，再删除 Guide 社区代码、表和旧 Qdrant contract。

在确认核心模块不依赖社区实体后：

- 移除对应后端代码；
- 移除前端页面；
- 移除 routes；
- 移除无用数据库表或标记 legacy；
- 清理 docs；
- 清理 API client；
- 清理 dead code。

数据库 destructive migration 必须谨慎。

如不确定，应先保留 legacy table，不立即 DROP。

## Phase 6 — Update Web Product Experience

Web navigation 应围绕：

```text
Home / Dashboard
Knowledge
AI Companion
Plans
Trips
Footprints
Memories
Profile
```

不再以：

```text
Community
Feed
Post
Follow
Like
```

作为导航主项。

整体web端页面需要做风格优化和统一。

## Phase 7 — iOS Foundation

创建：

```text
apps/vago-ios/
```

使用 Swift + SwiftUI。

第一阶段只实现：

- API configuration；
- login；
- auth token storage；
- current trip；
- itinerary viewing；
- basic profile。

不要第一天就实现完整地图。

目前既然要做ios+web双端，需要考虑重塑登陆校验机制链路，可以参考文档[登陆认证改造prompt](/Users/henrysang/Documents/Vago/local-prompts/登陆认证改造prompt.md)

## Phase 8 — iOS Travel Tracking

随后实现：

- Core Location；
- location permission；
- GPS tracking；
- local buffer；
- sync endpoint；
- MapKit；
- check-in；
- trip binding。

核心原则：

```text
iPhone collects
    ↓
local temporary buffer
    ↓
FastAPI sync
    ↓
server becomes source of truth
```

## Phase 9 — Travel Memory

完成实际旅行数据闭环后再开发 AI Memory。即在进入Phase 9之前还需要完成以下开发效果：

1. iOS端拥有足迹定位、记录、打卡、数据同步和准确渲染等功能。
2. web端足迹页面拥有足迹和打卡数据查询和渲染功能。

避免在没有真实 footprint / notes 数据模型时先做一个纯 Prompt 的“旅行总结生成器”。

---

# API Design Principles

统一使用：

```text
/api/v1/...
```

建议资源：

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

## Mobile Compatibility

API 不应假设调用方是 Web。

不要把：

- browser cookie；
- React state；
- Vite proxy；

作为 backend contract 的必要前提。

Swift iOS 和 React Web 应共享同一套 domain API。

---


# Personal Context and Retrieval Strategy

Vago 的个性化能力应建立在 **Hybrid Personal Context** 上，而不是单一 RAG。

## Context Categories

### Structured Personal Data

例如：

- Trip；
- Spot；
- Date；
- Budget；
- Visited / Not Visited；
- Country / City；
- GPS coordinates；
- Trip statistics。

这些数据应优先通过关系型数据库查询。

例如：

```text
“我去过多少个国家？”
“我上次东京去了哪些地方？”
“这次不要重复已经去过的景点。”
```

这些问题不应使用向量检索代替 SQL。

### Unstructured Personal Knowledge

例如：

- 收藏的旅行攻略；
- 长文本 Notes；
- 网页内容；
- AI / 用户生成的长篇 Travel Memory；
- 非结构化旅行资料。

只有当当前任务需要在较大的非结构化个人资料集合中寻找相关内容时，才使用：

```text
Embedding
→ Vector Search
→ RAG Context
```

### Explicit / Learned Preferences

例如：

- prefers museums；
- slow travel；
- budget range；
- avoids early flights；
- preferred food categories；
- preferred itinerary density。

这些偏好应逐步沉淀为结构化 profile / memory，而不是永远依赖 RAG 从长文本中猜测。

## Adaptive Retrieval

不要对所有请求机械执行 RAG。

根据上下文规模和用户意图选择 retrieval strategy。

### Direct Context

如果：

- 用户明确选择了 1～数篇攻略；
- 上下文体量可以安全直接提供给模型；
- 不需要跨大量历史资料检索；

则优先：

```text
Selected Sources
      ↓
Direct Context
      ↓
LLM
```

不要为了“必须使用 RAG”再执行无意义的 embedding search。

### Semantic Retrieval / RAG

如果：

- 用户知识库规模较大；
- 查询范围模糊；
- 需要跨大量攻略 / Notes / Memories 找相关信息；
- 无法合理把全部资料直接放入 context；

则：

```text
User Query
    ↓
Semantic Retrieval
    ↓
Relevant Personal Knowledge
    ↓
LLM / Agent
```

### Structured Retrieval

如果问题主要依赖：

- historical trips；
- visited spots；
- GPS；
- dates；
- budget；
- statistics；

应优先使用 SQL / domain service。

## Context Orchestration

目标架构应更接近：

```text
                 User Query
                     ↓
              Context Router
          ┌──────────┼──────────┐
          ↓          ↓          ↓
    Direct Context   SQL       RAG
                     ↓          ↓
                Past Trips   Guides / Notes
          └──────────┼──────────┘
                     ↓
              Preferences
                     ↓
                LLM / Agent
                     ↓
           Personalized Result
```

Agent 的价值之一是决定：

- 当前任务需要哪些个人上下文；
- 哪些数据应该直接读取；
- 哪些应该走 SQL；
- 哪些才值得执行 semantic retrieval。

## Product Messaging

不要在 README、简历或产品描述中把：

> RAG-based itinerary recommendation

作为 Vago 的主要产品定位。

优先使用：

- Personal Travel Intelligence；
- Personal Context Retrieval；
- Personalized Travel Companion；
- Personal Travel Memory。

RAG / Qdrant 应作为实现非结构化个人知识检索的底层技术，而不是产品本身。

## Codex Migration Rule for Existing RAG

现有 RAG 能力属于可复用技术资产，应保留，但在 remould 时必须重新定位。

Codex 不应：

- 删除已经稳定工作的 RAG pipeline；
- 强制所有 AI 请求经过 RAG；
- 为展示 Qdrant 而扩大向量化数据范围；
- 把适合 SQL 的结构化业务数据全部写入 vector DB；
- 把短小、用户明确选择的资料再次无意义检索。

Codex 应：

- 保留 ingestion / chunking / embedding / vector retrieval；
- 将 RAG 封装为可选择的 context source；
- 允许 direct context；
- 允许 relational retrieval；
- 为未来 Context Router / Agent Tool orchestration 留出清晰 interface；
- 保持来源引用和 user-level isolation。

---

# AI-Native Design Rules

## Personal Context Before Generic Generation

涉及用户个人攻略、历史旅行或偏好时：

- 优先利用用户自己的相关上下文；
- 根据任务选择 Direct Context / SQL / Profile / RAG；
- 明确数据来源；
- 个人数据不足时再 fallback；
- 不要把模型常识伪装成用户知识库结果；
- 不要为了调用 RAG 而调用 RAG。

## Structured Output

Agent 需要触发业务流程时，应优先使用结构化模型输出，而不是让业务代码解析自然语言。

例如：

```python
TravelPlanDraft
TravelMemoryDraft
SuggestedSpot
PreferenceSignal
```

## Agent Tool Boundary

Tool 应对应明确业务能力，例如：

- `search_personal_guides`
- `get_trip`
- `get_travel_history`
- `get_footprint_summary`

不要把所有数据库访问都暴露给 Agent。

## Grounded Travel Memory

生成旅行回忆时，必须区分：

```text
Facts
- GPS
- timestamps
- visited spots
- user notes
- photo metadata

Generated Narrative
- prose
- summary
- stylistic description
```

AI 不可无依据新增用户经历。

---

# Engineering Principles

## No Premature Microservices

本项目默认采用 Modular Monolith。

不要新增：

- gateway service；
- auth service；
- trip service；
- RAG service；
- memory service；

作为独立部署单元。

只有出现明确的独立扩缩容、部署、团队或故障隔离需求时，才重新评估服务拆分。

## Preserve Working Features During Migration

迁移过程中：

1. 新实现；
2. 测试；
3. 切换调用方；
4. 验证；
5. 再删除旧实现。

禁止先大面积删除 Spring Boot 再补功能。

## Avoid Technology Resume-Driven Design

不要为了增加简历关键词而：

- 加 Kafka；
- 加 Kubernetes；
- 换 MongoDB；
- 强行 Multi-Agent；
- 强行 MCP；
- 强行 GraphQL；
- 强行 CQRS。

只有功能真的需要时才引入。

## Tests

至少覆盖：

- auth；
- user isolation；
- trip CRUD；
- structured AI plan validation；
- RAG user scoping；
- footprint ownership；
- travel memory grounding-critical logic。

---

# Documentation Remould

代码迁移同时逐步更新：

- `README.md`
- `docs/prd/PRD.md`
- `docs/architecture.md`
- API docs
- local development docs

README 最终应突出：

```text
AI-Native Personal Travel Companion
Personal Travel Intelligence
Adaptive Personal Context Retrieval
AI Planning
Travel Footprint
Travel Memory
Web + Native iOS
FastAPI Modular Monolith
```

RAG / Qdrant 可以在技术架构与实现细节中出现，但不要继续作为产品主标题或唯一的 personalization 解释。

不要继续把 Spring Boot + FastAPI 混合架构描述为最终架构。

如果迁移尚未完成，应明确区分：

- Current Architecture
- Target Architecture
- Migration Status

不得让 README 描述超前于代码实际状态。

---

# Codex Execution Rules

每次调用本 Skill 时：

1. 先检查当前仓库状态；
2. 不假设上一次迁移已经完成；
3. 查看 git diff / status，避免覆盖用户未提交修改；
4. 明确本次只处理哪个 Phase；
5. 优先提交小范围、可验证的改变；
6. 修改 API 时同步检查 React client；
7. 修改 schema 时检查已有数据兼容性；
8. 删除代码前全局搜索依赖；
9. 每个阶段结束后运行可用测试；
10. 更新必要文档；
11. 输出：
   - Changed
   - Preserved
   - Removed
   - Migration risks
   - Next recommended step

如果仓库实际情况与本 Skill 的假设冲突：

> **以仓库事实为准，保持本 Skill 的产品目标，但调整具体迁移方式。**

如果用户在具体 prompt 中提供与本 Skill 冲突的新要求：

> **以用户当前 prompt 为最高优先级。**

---

# Definition of Done

Vago remould 的目标不是“所有计划功能全部完成”，而是达到以下稳定状态：

```text
React Web
       \
        → FastAPI Modular Monolith
       /
SwiftUI iOS

FastAPI
├── Auth / User
├── Knowledge
├── RAG
├── AI Companion
├── Plan / Trip / Itinerary
├── Footprint
├── Travel Memory
└── Personalization-ready data

Storage
├── MySQL
├── Redis
├── Qdrant
└── media/object storage
```

并满足：

- Spring Boot 不再是运行依赖；
- public community 不再是核心产品域；
- Agent 能根据任务组合 Direct Context、结构化业务数据、Preferences 与必要的 RAG 上下文；
- iOS 可以访问统一 FastAPI API；
- 旅行中真实数据可以沉淀；
- 旅行后 AI 可以基于真实数据生成可编辑回忆；
- 产品可以用一句话清楚解释；
- 技术架构与个人项目规模匹配；
- 面试时每项核心技术都能对应明确问题，而不是单纯堆栈。
