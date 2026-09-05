# Vago 架构说明

> 最后更新：2026-09-05
>
> 当前状态：Remould Phase 8，iOS Travel Tracking 已形成第一版可真机验证闭环
> 目标架构：FastAPI Modular Monolith + React Web + Native iOS

## 1. 架构目标与原则

Vago 是面向个人的旅行智能应用：用户的知识资料、计划、正式行程、足迹和未来回忆都属于同一位用户的私有旅行上下文。AI 规划与检索为这些事实数据服务，而非替代它们。

- **Personal-first**：所有领域记录以 `user_uuid` 隔离；不把公共社区关系带入新领域。
- **Human-in-the-loop**：AI 只能生成候选计划；用户确认后才写入 Plan、Trip 或未来的 Memory。
- **Context retrieval, not RAG-first**：明确选择的资料走 Direct Context，结构化旅行事实走 SQL，模糊的大规模文本检索才走 RAG/Qdrant。
- **事实优先**：GPS 样本和打卡是可追溯事实；地图路线和迷雾区域是其派生展示，不能反向篡改原始记录。
- **渐进迁移**：先在 FastAPI 新建并切换调用方，再删除 Java 兼容能力；不进行 big-bang 重写。
- **Mobile-native**：Web 负责知识、规划与完整编辑；iOS 优先服务旅行中的查看、采集、同步与打卡。

## 2. 当前可运行架构

```text
React Web (Vite :5173)                   SwiftUI iOS (iOS 17+)
         │                                         │
         │ Vite proxy                              │ HTTPS / URLSession
         ▼                                         ▼
                  FastAPI vago-ai (:8000)
         ┌───────────────┼─────────────────────┐
         │               │                     │
  Auth / Users     Travel / Knowledge     Footprints / AI
         │               │                     │
         └───────────────┼─────────────────────┘
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
           MySQL       Redis       Qdrant
                                     │
                                  OpenAI / LLM

React Web 未迁移 API
         │
         ▼
Spring Boot vago-backend (:8080)
  legacy public community / collection compatibility
```

### 2.1 客户端职责

| 客户端 | 当前职责 | 与后端的关系 |
|---|---|---|
| React + Vite | 个人知识库、AI 对话与规划、Plan/Trip/Itinerary 编辑、个人资料 | 已迁移路径代理至 FastAPI；旧社区兼容路径仍代理至 Spring Boot |
| SwiftUI iOS | 手机号登录、Keychain 会话、当前行程、前台 GPS 采样、离线缓冲、地图轨迹、打卡 | 直接请求 FastAPI `/api/v1`，不经过 Vite 或 Spring Boot |

### 2.2 FastAPI 模块与真实路由

| 模块 | 路由前缀 | 当前职责 |
|---|---|---|
| `auth` / `users` | `/api/v1/auth`、`/api/v1/users`，兼容 `/api/v1/user` | 手机号验证码、登录、刷新令牌、当前用户与设置 |
| `travel` | `/api/v1/travel` | Plan、Trip、每日行程、计划转正式行程、开始/结束生命周期 |
| `knowledge` | `/api/v1/knowledge` | KnowledgeSource 文本与 `.md/.txt` 导入、索引状态、可选 RAG 索引；旧 `/guides` 仅兼容窗口使用 |
| `footprints` | `/api/v1/footprints` | GPS 批量同步、轨迹读取、手动打卡与用户/行程归属校验 |
| `routers.ai` / `routers.chat` | `/api/v1/ai`、`/api/v1/ai/chat` | AI 计划、SSE 对话、结构化输出与现有 Agent 能力 |

FastAPI 采用 SQLAlchemy 2.x、Pydantic v2 与 Alembic；MySQL 保存领域事实和状态，Redis 承担认证/限流等运行期能力。所有移动端和 Web 的领域请求均使用 JWT，并由依赖项解析当前 `user_uuid`。

### 2.3 Personal Context Retrieval

```text
用户意图
   │
   ├── Direct Context：用户明确选中的少量知识资料
   ├── SQL Context：Trip / Plan / Itinerary / Footprint 等结构化事实
   ├── RAG Context：规模较大的个人文本知识，使用 Qdrant
   └── No Personal Context：普通旅行问题不强制读取用户资料
                         │
                         ▼
                   AI Companion / LLM
                         │
                         ▼
                用户确认后的结构化写入
```

`KnowledgeSource` 不依赖 Qdrant：纯文本资料和 `.md/.txt` 文件可独立存在；`parse_status` 与 `index_status` 分开表达资料可读性与可选索引能力。RAG 未启用或向量库不可用时，资料 CRUD 仍正常工作，索引 API 明确返回不可用状态。

### 2.4 Travel Footprint 数据流

```text
Core Location 前台回调
       │  约 20 米距离过滤，保留精度/速度/记录时间
       ▼
LocationTrackingStore
       │
       ├── UserDefaults：按 user_uuid 隔离的待同步样本队列
       └── POST /footprints/location-samples/sync（最多 100 条/批）
                                      │
                                      ▼
                         MySQL location_samples
                         唯一键：(user_uuid, client_uuid)
                                      │
                                      ▼
       GET /footprints/trips/{trip_uuid}/locations
                                      │
                                      ▼
MapKit：时间排序、15 米渲染降采样、长间隔/远跳断段、平滑 polyline

一次手动打卡
       │  请求并冻结一条新坐标
       ▼
POST /footprints/checkins
       │  仅进行中 Trip；30 米内重复打卡拒绝
       ▼
MySQL checkins → MapKit annotation
```

第一版只做前台定位，不启用后台持续定位。GPS 样本同步失败不会从本地队列删除；服务端按客户端幂等键去重，因此网络重试不会产生重复轨迹。`location_samples` 不保存国家、省市等反向地理编码结果，避免为高频且敏感的定位事实扩张数据面。

## 3. 数据边界

| 数据域 | 主要存储 | 说明 |
|---|---|---|
| 用户、计划、行程、日程 | MySQL | 结构化事实；已结束 Trip 只读 |
| 个人知识源 | MySQL + local storage abstraction | MySQL 保存元数据、状态和当前阶段的文本；原文件由 storage abstraction 保存 |
| 向量索引 | Qdrant | 仅为 KnowledgeSource 提供可选 semantic retrieval，不是知识源主存储 |
| GPS 样本、打卡 | MySQL | `location_samples`、`checkins` 为用户旅行事实；不直接引入 GIS、分区或 chunk 表 |
| iOS 待传位置 | UserDefaults | MVP 队列，按用户隔离；当前数据量与失败恢复需求下无需提前迁移 SwiftData/Core Data |
| 会话和限流 | Redis + iOS Keychain | 服务端维护 refresh/session 与限流；客户端 token 不存入 UserDefaults |

当前 Alembic head 为 `20260904_03`。全新数据库可使用 [db_schema.sql](database/db_schema.sql)；已有数据库必须执行 Alembic 增量迁移。

## 4. 兼容窗口与目标状态

Spring Boot 仍承接 legacy public community、收藏夹及旧路由兼容。新的 FastAPI Knowledge Domain 不再暴露点赞、浏览、发布、发现或社区作者等语义；`guides` 表和旧 Java API 必须待 Java community 链路确认下线后再做破坏性清理。

目标不是拆成微服务，而是让 `services/vago-ai` 演进为统一的 FastAPI 模块化单体：模块共享基础设施，但领域服务不跨越边界直接泄漏存储细节。React 与 iOS 最终共享同一组 domain API contract。

## 5. 迁移进度

| Phase | 目标 | 当前状态 |
|---|---|---|
| 1 | FastAPI foundation | 已完成 |
| 2 | Auth / User | 已完成，保留旧用户路径兼容 |
| 3 | Trip / Plan / Itinerary | 已完成核心 CRUD 与生命周期 |
| 4 | Knowledge / Context Retrieval / AI | KnowledgeSource、文本文件导入和可选索引已完成；Context Router 深化待后续实施 |
| 5 | Legacy community 收敛 | 新 FastAPI 不再承接社区语义；Java 兼容数据和旧表等待最终下线 |
| 6 | Web 产品体验 | 已回归简洁入口布局，后续按产品需求持续优化 |
| 7 | iOS foundation | 已完成认证、会话、当前行程与个人资料 |
| 8 | iOS Travel Tracking | 基础闭环已完成；后续继续推进 Check-in 详情、历史行程地图和简单迷雾 |
| 9 | Travel Memory | 未开始 |

## 6. 当前约束与后续方向

- RAG、chunk、embedding 与 Qdrant 是保留的技术资产，但不得成为 Knowledge Domain 的强依赖。
- 当前仅支持 `.md`、`.txt` 和纯文本知识源；PDF、DOCX、复杂解析管道不在本阶段范围。
- 轨迹线是基于 GPS 样本的展示插值，不是道路匹配或导航结果；大跨度样本必须断段，不能画出虚假路线。
- World Fog 将先以客户端有限半径覆盖层验证体验，不引入 PostGIS、GIS 服务或 vector tile 基础设施。
- Photos、Notes、Travel Memory 需要以已确认的旅行事实为依据，不能由模型凭空补写。

相关文档：[PRD](prd/PRD.md)、[迁移盘点](remould-migration-inventory.md)、[iOS Travel Map 实施计划](ios-development-plan.md)、[足迹 API](API/footprint-service.md)。
