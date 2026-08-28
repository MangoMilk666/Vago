# Vago（叠迹）产品需求文档（PRD）

**文档版本**：v0.4-remould
**最后更新**：2026-08-28
**状态**：Remould draft，作为后续迁移与实现基准

## 1. 产品定位

### 1.1 一句话

> Vago（叠迹）是一个 AI-Native 个性化旅行搭子，将用户零散的旅行知识沉淀为个人知识库，通过 AI 辅助旅行规划，并将实际旅行过程中的地点、照片和记录转化为长期可回顾、可复用的旅行记忆。

英文表达：

> Vago is an AI-native personal travel companion that turns a user's fragmented travel knowledge into personalized plans, records real-world journeys, and transforms them into reusable travel memories.

### 1.2 不再是什么

Vago 不再以公共旅行社区为核心，不再围绕陌生人 Feed、关注、点赞、评论或社区增长设计核心流程。

分享能力可以保留，但它是旅行结果的输出能力，例如分享某次旅行、足迹地图、AI 旅行回忆或 itinerary，不应重新演变为完整社交平台。

### 1.3 核心闭环

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

### 1.4 产品原则

| 原则 | 说明 |
|------|------|
| Personal-first | 优先服务用户自己的攻略、偏好、行程、足迹、照片、回忆和历史数据 |
| AI-native | AI 深入规划、检索、结构化输出、回忆生成，而不是附加聊天入口 |
| Human-in-the-loop | AI 生成建议和草稿，用户确认后才写入正式业务数据 |
| Context-aware | 根据任务选择 Direct Context、SQL、Profile、RAG |
| Mobile-native | Web 管理复杂资料，iOS 采集真实旅途数据 |

## 2. 用户场景

### 2.1 Planner：深度攻略整理与规划用户

Planner 出行前会收集大量攻略、笔记和链接，但资料分散、重复、难以比较。

Vago 需要帮助这类用户：

- 导入和整理个人旅行资料；
- 按目的地、主题、来源组织知识；
- 用 AI 结合个人资料和偏好生成行程草稿；
- 在确认后保存为 Plan 或 Trip；
- 在后续旅行中把实际经历反哺个人记忆。

### 2.2 Tracker：重视旅行记录和足迹用户

Tracker 更重视实际旅行中的地点解锁、照片、笔记和回忆沉淀。

Vago 需要帮助这类用户：

- 查看当前行程；
- 记录 GPS 足迹和打卡点；
- 将照片、时间、位置和笔记绑定到 Trip / Spot；
- 旅行后自动生成 grounded travel memory；
- 形成未来 AI 规划可使用的旅行偏好和历史信号。

## 3. Web 与 iOS 分工

| 功能域 | Web | iOS |
|--------|-----|-----|
| Knowledge | 长文粘贴、URL 导入、资料整理、知识库管理 | 快速摘录、分享链接接力 |
| AI Planning | 复杂多轮规划、结构化预览、行程编辑 | 当前场景轻量问答、局部调整 |
| Plans / Trips | 列表、详情、每日安排、预算、历史管理 | 当前行程查看、当日安排 |
| Footprints | 大屏地图、统计、历史回放 | GPS 采样、打卡、迷雾地图 |
| Photos / Notes | 批量管理、回忆编辑 | 拍照、相册选择、快速笔记 |
| Memories | 浏览、编辑、导出、分享 | 回忆浏览、移动端分享 |
| Profile | 偏好、账号、数据管理 | 轻量设置、权限管理 |

## 4. 功能范围

### 4.1 KEEP / MIGRATE

| 功能 | 说明 |
|------|------|
| User / Auth | 用户账户、JWT、用户级数据隔离、个人设置 |
| Knowledge Base | 攻略文本 / URL 导入、清洗、元数据、分块、Embedding、Qdrant、来源引用 |
| AI Companion | 多轮问答、SSE、Tool Calling、结构化行程输出、用户确认保存 |
| Plan / Trip / Itinerary | 草稿计划、正式行程、每日安排、景点、交通、住宿、预算 |
| Personal Profile / Preferences | 旅行偏好、节奏、兴趣、预算倾向、历史目的地信号 |

### 4.2 BUILD

| 功能 | 说明 |
|------|------|
| Travel Footprint | GPS sampling、route、visited places、check-in、城市/区域/国家统计 |
| Fog-of-World Map | 根据用户移动解锁区域，支持当前旅行和历史旅行视图 |
| Travel Photos / Notes | 拍照、相册、时间戳、经纬度、Trip / Day / Spot 绑定 |
| AI-generated Travel Memory | 基于事实数据生成 timeline、highlights、summary、narrative、share card |
| Native iOS | SwiftUI、URLSession、Codable、MapKit、Core Location、PhotosUI |

### 4.3 REMOVE FROM CORE

| 功能 | 处理 |
|------|------|
| Public Feed | 不迁移到目标 FastAPI 后端 |
| Follow / Comment | 不作为核心业务继续开发 |
| Like / public ranking | 仅在分享能力需要时重新评估 |
| Community recommendation | 暂停，不作为 remould 阶段目标 |

### 4.4 DEFER

Android、React Native、Kubernetes、Service Mesh、复杂事件总线、大规模 GIS、自主多 Agent、商业订阅体系、App Store 正式发布、高级离线地图、OCR / screenshot ingestion 均暂缓。

## 5. Personal Context Retrieval

Vago 的个性化由多类上下文共同组成：

```text
Current User Intent
+ Structured Travel Data
+ Unstructured Personal Knowledge
+ Explicit / Learned Preferences
```

### 5.1 Direct Context

用户明确选择 1 到数篇攻略、笔记或历史回忆时，优先直接提供给 LLM，不为了形式感再次向量检索。

### 5.2 Structured Retrieval

以下问题优先通过 SQL / domain service：

- 我去过多少个国家？
- 上次东京去了哪些地方？
- 这次不要重复去过的景点。
- 最近几次旅行预算大概是多少？

### 5.3 Semantic Retrieval / RAG

当用户知识库规模较大，或需要从大量攻略、Notes、Memories 中寻找相关内容时，使用 Embedding + Qdrant + RAG。

RAG 要求：

- 按 `user_uuid` 严格隔离；
- 保留来源引用；
- 不把适合 SQL 的结构化数据全部写入 vector DB；
- 不把模型常识伪装成用户知识库结果。

## 6. 核心需求

### 6.1 Personal Travel Knowledge

需求：

- 支持文本粘贴和 URL 导入；
- 支持标题、目的地、标签、来源、正文；
- 支持清洗、metadata extraction、chunking、embedding、Qdrant upsert；
- 支持删除攻略时清理对应向量；
- 支持索引状态；
- 支持用户级隔离；
- 支持来源引用。

当前实现中该能力主要由 Java `guides` 表和 Python `articles` router / RAG pipeline 共同完成。后续应迁入统一 FastAPI 后端。

### 6.2 AI Travel Companion

需求：

- 支持自然语言问答；
- 支持多轮上下文；
- 支持 SSE streaming；
- 支持 Tool Calling；
- 支持结构化 `TravelPlanDraft` 输出；
- 支持来源引用；
- 支持用户确认后保存为 Plan / Trip；
- 支持 Direct Context、SQL、Profile、RAG 的可选编排。

AI 不应未经确认直接创建正式行程、修改重要计划或覆盖用户记录。

### 6.3 Plans / Trips / Itinerary

需求：

- Plan 表示规划阶段草稿，可无完整日期；
- Trip 表示确定出行的正式行程，必须有起止日期；
- Itinerary Day 支持每日交通、住宿、餐饮、预算、备注；
- Spot 支持地点名称、地址、类型、排序、预计停留、来源说明；
- AI 结构化草稿保存后进入普通编辑流程。

### 6.4 Travel Footprint

需求：

- iOS 采集 GPS location samples；
- 支持行程关联；
- 支持离线缓存和恢复同步；
- 支持手动 check-in；
- 支持 route / trajectory；
- 服务端为长期 source of truth；
- 采样策略考虑隐私、电量、频率和权限。

第一版优先保证数据结构清晰、同步可靠、地图可运行。

### 6.5 Photos / Notes

需求：

- iOS 拍照或从相册选择；
- 读取时间戳和可用 EXIF 位置；
- 绑定 Trip / Day / Spot / Check-in；
- 用户可添加 caption / note；
- 服务端持久化 metadata；
- 照片二进制资源走对象存储，不直接写入关系型数据库。

### 6.6 AI-generated Travel Memory

输入：

- structured itinerary；
- GPS footprint；
- visited spots；
- photos metadata；
- user notes；
- trip duration；
- statistics；
- optional preferences。

输出：

- trip summary；
- timeline；
- highlights；
- memorable moments；
- city / route summary；
- editable narrative；
- shareable travel card data。

约束：

- 事实数据和 AI 生成文本分离；
- 不生成用户未到访地点；
- 对 GPS、时间戳、用户笔记、照片 metadata 支持的事实保持 grounded；
- 用户可以编辑生成内容。

## 7. 非功能性需求

| 类型 | 要求 |
|------|------|
| Privacy | 位置、攻略、照片、记忆按用户隔离；分享时坐标可脱敏 |
| Security | JWT、当前用户依赖、重要操作二次确认、删除权 |
| Reliability | AI 可降级，GPS 可离线缓存，上传可重试 |
| Performance | AI streaming，地图渲染稳定，批量 GPS 同步 |
| Maintainability | FastAPI modular monolith，API / service / persistence / LLM boundary 清晰 |
| Testability | auth、user isolation、trip CRUD、RAG scoping、footprint ownership、memory grounding 均需测试 |

## 8. 目标数据域

```text
users
  ├── profile / preferences
  ├── knowledge sources
  ├── plans
  ├── trips
  │     ├── itinerary days
  │     ├── spots
  │     ├── footprints
  │     ├── photos / notes
  │     └── memories
  └── travel history / personalization signals
```

存储分工：

- MySQL：用户、计划、行程、地点、足迹 metadata、照片 metadata、回忆 facts / narrative；
- Redis：token invalidation、rate limit、短期缓存；
- Qdrant：非结构化个人知识 chunk embedding；
- Object storage：照片和媒体文件。

## 9. 里程碑

| Phase | 目标 | 验收 |
|------|------|------|
| 0 | 仓库盘点和文档重塑 | README / PRD / architecture / inventory 对齐 |
| 1 | FastAPI backend foundation | config、DB、Alembic、auth dependency、exceptions、tests skeleton |
| 2 | Auth / User migration | React 可切换到 FastAPI auth，用户隔离测试通过 |
| 3 | Trip domain migration | Plan / Trip / Itinerary API 和 Web 调用切换 |
| 4 | Knowledge / RAG integration | 统一后端承接 ingestion、RAG、AI Companion |
| 5 | Remove legacy community | 不迁移 public feed / like / follow，清理无依赖代码 |
| 6 | Web experience remould | 导航聚焦 Dashboard、Knowledge、AI、Plans、Trips、Footprints、Memories、Profile |
| 7 | iOS foundation | SwiftUI app 完成 API config、login、current trip、basic profile |
| 8 | iOS tracking | Core Location、local buffer、sync、MapKit、check-in |
| 9 | Travel memory | 基于真实足迹 / 笔记 / 照片生成 grounded memory |

## 10. 当前实现边界

当前代码尚未完成统一 FastAPI 后端、iOS、Footprint、Travel Memory。README 和架构文档必须区分当前架构与目标架构，不能把尚未迁移完成的能力描述成已上线事实。
