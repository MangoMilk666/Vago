# Vago 架构说明

> 最后更新：2026-09-14
> 当前状态：FastAPI Modular Monolith + React Web + Native SwiftUI iOS
> 本文明确区分当前可运行架构与目标 Agent 架构；目标图不代表已存在的 Python module。

## 1. 架构原则

Vago 围绕 **Personal Travel Intelligence** 建设：用户的知识、计划、正式行程、足迹、打卡和未来回忆属于同一用户的私有旅行上下文。AI 服务于这些旅行事实与用户目标，而不替代或篡改它们。

- **Personal-first**：领域记录按 `user_uuid` 隔离；不恢复公共 Feed 或陌生人社交关系。
- **Facts first**：GPS、Check-in 与未来 Photos / Notes 是原始旅行事实；路线、Memory 和偏好信号均为派生结果。
- **Context-aware, not RAG-first**：Direct Context、SQL structured retrieval 与 semantic RAG 按任务分工。
- **Human-in-the-loop**：重要持久化旅行状态或外部操作由用户批准后再执行。
- **Modular Monolith**：FastAPI 统一承载领域模块与 AI 能力，不为展示而拆微服务。
- **Progressive evolution**：保留已运行的 API 与领域资产，逐步引入 Agent Runtime，不进行 big-bang rewrite。

## 2. 当前可运行架构

```text
React Web (Vite :5173)                   SwiftUI iOS (iOS 17+)
         │                                         │
         │ Vite proxy                              │ URLSession
         └─────────────────┬───────────────────────┘
                           ▼
                 FastAPI vago-ai (:8000)
         ┌─────────────────┼──────────────────────────┐
         │                 │                          │
 Auth / Users      Travel / Knowledge       Footprints / AI chat
         │                 │                          │
         └─────────────────┼──────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
            MySQL        Redis        Qdrant
                                           │
                                      OpenAI / LLM
```

`services/vago-backend` 已从仓库移除；当前没有仍在运行的 Spring Boot 兼容后端。React 已经通过 FastAPI 的领域接口工作，iOS 直接请求 FastAPI `/api/v1`。

### 2.1 当前模块与职责

| 模块 | 路由或入口 | 当前职责 |
| --- | --- | --- |
| `auth` / `users` | `/api/v1/auth`、`/api/v1/users` 及兼容前缀 | 登录、刷新令牌、用户资料、设置与用户隔离 |
| `travel` | `/api/v1/travel` | Plan、Trip、Itinerary、计划转行程与 Trip 生命周期 |
| `knowledge` | `/api/v1/knowledge` | KnowledgeSource 文本/`.md/.txt` 导入、状态与可选索引 |
| `footprints` | `/api/v1/footprints` | GPS 批量同步、读取、Check-in 和归属校验 |
| `routers.chat` | `/api/v1/ai/chat` | SSE 对话、可选个人知识检索、来源引用 |
| `routers.ai` | `/api/v1/ai` | 现有 AI 规划入口与结构化计划保存适配；完整规划生成仍在演进 |

当前对话链路已经使用 Tool Calling 形式按需搜索个人知识，但它不是跨领域协调、审批或重规划的完整 Agent Runtime。

### 2.2 当前数据边界

| 数据域 | 主要存储 | 当前边界 |
| --- | --- | --- |
| 用户、Plan、Trip、Itinerary | MySQL | 结构化旅行事实；已结束 Trip 只读 |
| KnowledgeSource | MySQL + local storage abstraction | MySQL 保存元数据/文本/状态，原始文件由存储抽象保存 |
| 语义向量 | Qdrant | 仅服务于非结构化个人知识的可选 semantic retrieval |
| GPS 与 Check-in | MySQL | 用户旅行事实；服务端按认证用户与 `client_uuid` 处理归属和幂等 |
| iOS 待传足迹 | UserDefaults | 短期、按用户隔离的 pending 队列，不是历史数据库 |
| 会话、限流 | Redis + iOS Keychain | Token 不存入 UserDefaults |

`KnowledgeSource` 与 Qdrant 解耦：资料的创建、读取、更新和删除不依赖向量库。RAG 不可用时，资料 CRUD 仍可工作；索引能力以明确状态和错误降级。

### 2.3 当前 Travel Observation 数据流

```text
Core Location（仅用户明确开始、前台）
        ↓
LocationTrackingStore → 本地 pending 队列 → 100 条/批幂等同步
                                                   ↓
                                                FastAPI
                                                   ↓
                                         MySQL location_samples
                                                   ↓
                                    MapKit 合并本地与远端事实后渲染

一次手动打卡 → FastAPI checkins → MySQL checkins → MapKit annotation
```

定位、打卡与未来照片/笔记是 **Travel Observations**。它们可成为 Personal Travel Context 的 grounded 输入，但 AI 不应写回或覆盖原始事实。iOS 当前优先负责采集、同步与显示，并不承载 Agent Runtime。

## 3. Personal Travel Context

> Personal Travel Context 是 Agent 为完成当前任务从多个来源组合出的状态视图；它不是统一表、统一向量库或一段固定 prompt。

```text
Long-term personal context     Current trip context     Live travel context
preferences / history          trip / itinerary         location / footprint / check-ins
            \                         |                         /
             \                        |                        /
              └──── Personal knowledge + task intent ────┘
                                │
                    optional external / ephemeral context
                                ▼
                     task-scoped Personal Travel Context
```

- **Long-term personal context**：明确偏好、历史行程、visited places、Travel Memories 与旅行倾向。learned preference signals 必须与用户确认事实区分。
- **Current trip context**：当前 Trip、itinerary、已确认安排、交通、住宿、时间与剩余活动。
- **Live travel context**：当前位置、近期 GPS、Check-in、当前时间与旅行进度。
- **Personal knowledge**：KnowledgeSource、导入资料、用户选择的资料与未来回忆。
- **External / ephemeral context**：未来 POI、路线、天气、日历、航班等临时现实世界信息。

## 4. 目标 Agent 架构

以下是目标概念架构，不表示 `app/agents`、`app/memories` 或 MCP server 已经实现。

```text
React Web                    SwiftUI iOS
    │                            │
    └────────────┬───────────────┘
                 ▼
              FastAPI
                 │
        ┌────────▼────────┐
        │   Agent Runtime │
        │ goal / loop     │
        │ context / tools │
        │ constraints     │
        │ replan          │
        │ approval        │
        └───┬─────┬───────┘
            │     │
     ┌──────┘     └────────────┐
     ▼                         ▼
Personal Travel Context    External Tools / MCP
     │                         │
     ▼                         ▼
Vago Domain Tools       candidate integrations
     │                  maps / weather / calendar / flights
     ├── Travel
     ├── Itinerary
     ├── Footprint
     ├── Knowledge
     ├── Preferences
     └── Memory
            │
            ▼
 MySQL / Redis / Qdrant / Object Storage
```

### 4.1 Agent Runtime 的职责

Agent Runtime 负责：

```text
interpret user goal
→ acquire task-relevant context
→ select read tools
→ observe results
→ check constraints
→ plan or replan
→ request approval when required
→ execute approved domain action
→ observe updated state and complete
```

它不直接访问数据库，不把所有上下文转换成 embedding，也不以某个框架、MCP 或多 Agent 数量作为设计目标。

### 4.2 Domain Services 与内部 Domain Tools

Domain Services 继续拥有真实业务规则、授权与持久化，例如 Travel service 检查 Trip 生命周期，Footprint service 检查归属与幂等。Agent 通过内部 Domain Tools 调用这些服务，例如概念上的 `get_current_trip`、`get_today_itinerary`、`get_recent_footprint`、`search_personal_knowledge`、`update_itinerary` 和 `create_plan`。

内部工具不是要求把 FastAPI 的每个 endpoint MCP 化。它们是 Agent Runtime 与领域规则间明确、可测试的调用边界。

### 4.3 Human-in-the-loop 与事实边界

- **Read / observe actions**：读取当前 Trip、行程、足迹、偏好、个人资料或未来外部信息，通常可自主执行。
- **Proposed write actions**：修改 itinerary、创建 Trip、删除数据、未来的 booking/payment，需按风险要求确认。
- **Travel facts**：GPS、Check-in、照片 metadata 和用户笔记不会被 Agent 直接篡改；Memory 和 signal 必须保留事实来源与派生性质。

当前目标保持保守：重要持久化旅行状态的写操作，执行前必须获得用户确认。approval engine 是未来能力，尚未实现。

## 5. MCP 与外部工具的位置

MCP 是接入外部工具的一种标准化协议，不是 Agent Runtime 本身，也不是内部领域服务的必选协议。未来只有在已有明确 Agent workflow 时，才评估接入地图/POI、路线、天气、Google Calendar、航班搜索（例如 Kiwi.com）或其他旅行服务。

当前没有 MCP 配置、外部 provider 或外部写操作。外部信息不可用时，Agent Runtime 应能明确说明信息缺失并降级，而不是伪造结果。

## 6. 演进路线

历史 Phase 1–8 记录 FastAPI foundation、领域迁移、Web 收敛、iOS foundation 与 Travel Tracking 的真实完成过程，不重新编号。

| Phase | 目标 | 当前状态 |
| --- | --- | --- |
| 9 | Travel Memory & Personal Context Foundation：grounded Memory、历史上下文、明确偏好与可审视 signal | 进行中：已完成 Memory / 显式偏好 / Web Context 注入；signals 待后续真实数据验证 |
| 10 | Agent Runtime & Vago Domain Tools：Agent loop、上下文获取、工具边界、约束检查、审批原则、最小 tracing/testability | 未来 |
| 11 | Context-aware Coordination & Replanning：以 Adaptive Day Planner 为代表的旅行中协调与确认后更新 | 未来 |
| 12 | External Tool / MCP Integration：在有真实 workflow 后接入外部能力 | 未来 |

## 7. 当前约束

- 不引入不必要微服务、复杂事件总线、多 Agent、GIS 或 MCP 基础设施。
- 不把 RAG 描述为 Memory，也不把 Qdrant 当作所有 Personal Travel Context 的存储。
- 当前仅支持纯文本和 `.md/.txt` 知识源；复杂文档解析不在当前范围。
- Travel Memory 已具备事实快照与用户叙事的最小基础；Photos、Notes、Preference signals、Adaptive Day Planner、MCP 和外部工具仍属于未来能力。
- 当前 Alembic head 为 `20260922_01`；全新数据库使用 [db_schema.sql](database/db_schema.sql)，已有数据库使用 Alembic 增量升级。
