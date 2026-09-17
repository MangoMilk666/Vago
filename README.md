<h1 align="center">Vago（叠迹）</h1>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.111.0-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI 0.111.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/MangoMilk666/Vago?style=flat-square" alt="Apache License 2.0"></a>
</p>

> AI-native Personal Travel Intelligence：以持续积累的个人旅行状态和历史为基础，支持旅行规划、旅行中协调与旅行后回顾的个人旅行 Agent 系统。

## 项目简介

**Vago（叠迹）** 不是旅行社区，也不只是一个旅行聊天机器人或一次性行程生成器。本项目围绕用户自己的旅行资料、计划、行程、足迹、打卡和未来旅行回忆，持续形成 **Personal Travel Context**。

它的长期目标是让 **Vago Agent** 在用户保有旅行意图和重要决定权的前提下，承担跨资料、行程和旅行状态的协调工作：收集相关上下文、检查约束、比较方案、提出重规划建议，并在得到确认后调用领域能力完成操作。

```text
Plan → Travel → Observe → Memory → Learn → Next Plan
                  ↑                         │
                  └── Personal Travel Context ──┘
                               ↕
                          Vago Agent
```

Personal Travel Context 不是单独的数据库，也不等同于 RAG。它是针对当前任务，从个人资料、结构化旅行事实、实时观察和必要外部信息组合出的状态视图。

## 核心价值

普通 LLM 通常不持续拥有用户的历史旅行、当前行程、实时足迹、个人资料和旅行回忆。用户当然也能在地图、日历、天气、笔记和行程应用之间自行完成旅行安排，但需要反复搜索、比较、复制与检查。

Vago 的价值不在于替用户做旅行决定，而在于降低这种 **coordination cost**：

```text
用户拥有意图与重要决定
Vago 负责上下文收集、协调、约束检查和重规划建议
```

## 当前能力与目标能力

| 范围 | 当前已实现 | 后续目标 |
| --- | --- | --- |
| Personal Travel Knowledge | KnowledgeSource、纯文本与 `.md/.txt` 导入、用户隔离、可选语义索引 | 更丰富的个人资料与知识整理能力 |
| AI 对话 | SSE 对话、来源引用、按需个人知识语义检索 | Agent Runtime 的跨领域上下文获取、协调和多步执行 |
| Plan / Trip / Itinerary | 计划、正式行程、每日安排、行程生命周期与编辑 | Agent 在确认后提出或执行受控的日程更新 |
| Travel Observations | iOS 前台 GPS、离线队列、幂等同步、轨迹、当前位置与手动打卡 | Photos / Notes 等更多 grounded observations |
| Travel Memory | 尚未实现 | 基于真实旅行事实生成可编辑回忆，并形成可审视的偏好信号 |

## Personal Travel Context

| 类别 | 典型信息 | 当前或未来来源 |
| --- | --- | --- |
| Long-term personal context | 明确偏好、历史行程、去过的地点、旅行回忆、节奏与预算倾向 | MySQL 领域事实；未来的 learned preference signals |
| Current trip context | 当前 Trip、itinerary、已确认安排、住宿、交通与剩余活动 | Travel domain |
| Live travel context | 当前位置、近期足迹、打卡、当前时间与旅行进度 | iOS Travel Map / Footprints |
| Personal knowledge | 用户资料、导入笔记、知识源、未来回忆 | Direct Context、SQL、可选 RAG |
| External / ephemeral context | POI、路线、天气、日历、航班等 | 未来 External Tools / MCP 候选能力 |

Direct Context、SQL structured retrieval 和 semantic RAG 各有边界：明确选择的资料直接使用；结构化旅行事实通过领域服务读取；只有规模较大的非结构化个人文本才按需走 Qdrant 语义检索。RAG 不是 Personal Travel Context 的主存储，也不是每次请求的必经路径。

## 功能模块

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 用户与认证 | 已实现 | JWT、用户级数据隔离、个人设置与设备级会话 |
| Personal Travel Knowledge | 已实现 | 独立 KnowledgeSource、文本/`.md/.txt` 导入和可选索引 |
| AI 对话与检索 | 已实现 | SSE、多轮对话、可选个人知识检索与来源引用 |
| AI 规划 | 开发中 | 结构化计划输入与确认保存链路存在；完整 context-aware planning 仍在演进 |
| Plans / Trips / Itinerary | 已实现 | 草稿计划、正式行程、每日安排、景点、交通、住宿与生命周期 |
| Travel Footprints | 已实现 | iOS 前台采样、离线缓冲、幂等同步、分段轨迹、方向指示与手动打卡 |
| Photos / Notes | 未开发 | 将作为旅行中的 grounded observations |
| Travel Memory | 后续建设 | 基于事实数据的可编辑回忆与学习输入 |
| Vago Agent Runtime | 后续建设 | 上下文获取、约束检查、重规划、审批边界与领域工具调用 |

## 技术栈

| 层次 | 当前使用 | 后续方向 |
| --- | --- | --- |
| Web | React 18、Vite 5、Tailwind CSS | 知识管理、规划与历史旅行管理 |
| iOS | Swift 6、SwiftUI、MapKit、Core Location、URLSession、Keychain | 可靠采集、旅行观察与移动端旅行体验 |
| Backend | FastAPI 0.111、Pydantic v2、SQLAlchemy 2.x、Alembic | 保持 Modular Monolith，逐步增加领域工具与 Agent Runtime |
| Relational DB | MySQL | 结构化旅行事实主存储 |
| Cache | Redis | 会话、限流和短期运行状态 |
| Vector DB | Qdrant | 非结构化个人知识的可选 semantic retrieval |
| AI | LangChain、OpenAI SDK、SSE | Context-aware Agent 工作流，不绑定特定框架或 MCP |

## 目录结构

```text
Vago/
├── apps/
│   ├── vago-web/                 # React Web
│   └── vago-ios/                 # SwiftUI iOS
├── services/
│   ├── vago-ai/                  # FastAPI 模块化单体、领域服务与 Alembic
│   └── nginx/
├── docs/
│   ├── API/                      # API 文档
│   ├── database/                 # DDL 与数据库说明
│   ├── design/                   # 设计与实施文档
│   └── prd/                      # 项目需求文档
├── dev-up.sh
├── .env.example
└── LICENSE
```

## 双端当前能力

| 能力域 | React Web | SwiftUI iOS |
| --- | --- | --- |
| 登录与会话 | 手机号 / OAuth、浏览器会话 | 手机号登录、Keychain 凭证与刷新会话 |
| 知识与 AI | KnowledgeSource 管理、资料导入、AI 对话与规划入口 | 暂不复制复杂资料管理与规划流程 |
| 计划与行程 | Plan / Trip / Itinerary CRUD、日程编辑 | 查看进行中行程与每日安排 |
| 旅行足迹 | 稳定入口，真实 Web 浏览仍待建设 | 前台定位、本地待传队列、幂等同步、分段路线、当前位置与打卡 |

## 后续路线

| 阶段 | 方向 | 状态 |
| --- | --- | --- |
| Phase 9 | Travel Memory & Personal Context Foundation：grounded memory、历史旅行上下文与可审视偏好信号 | 未来 |
| Phase 10 | Agent Runtime & Vago Domain Tools：上下文获取、领域工具边界、观察、约束检查与审批原则 | 未来 |
| Phase 11 | Context-aware Coordination & Replanning：以 Adaptive Day Planner 为代表的旅行中协调 | 未来 |
| Phase 12 | External Tools / MCP Integration：在有明确工作流后接入地图、日历、天气或航班等外部能力 | 未来 |

## 数据库初始化

全量 DDL 位于 [db_schema.sql](docs/database/db_schema.sql)，适用于全新本地数据库：

```bash
mysql -u <user> -p <database_name> < docs/database/db_schema.sql
```

已有数据库应使用 FastAPI 服务目录中的 Alembic 增量迁移：

```bash
cd services/vago-ai
.venv/bin/alembic upgrade head
```

## 文档

- [项目需求文档](docs/prd/PRD.md)
- [项目架构说明](docs/architecture.md)
- [重塑迁移盘点](docs/evolution/remould-migration-inventory.md)
- [iOS Travel Map 实施计划](docs/modules/footprint/ios/implementation-plan.md)
- [版本更新记录](docs/CHANGELOG.md)
- [数据库文档](docs/database/schema.md)

## License

[Apache License 2.0](LICENSE)
