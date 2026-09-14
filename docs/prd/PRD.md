# Vago（叠迹）产品需求文档（PRD）

**文档版本**：v0.5-agent-evolution
**最后更新**：2026-09-14
**状态**：定位深化；已实现能力与目标能力分层记录

## 1. 项目定位

### 1.1 一句话

> Vago 是一个 AI-native Personal Travel Intelligence / Personal Travel Agent system：它持续积累并理解用户自己的旅行状态与历史，以 Personal Travel Context 支撑旅行前规划、旅行中协调和旅行后回顾。

Vago 不以旅行社区、通用旅行聊天机器人、单次 LLM 行程生成器或技术框架展示为核心。它也不试图接管用户的旅行决定；用户拥有意图与重要决定，Vago 负责上下文收集、协调、约束检查与重规划建议。

### 1.2 核心闭环

```text
Plan → Travel → Observe → Memory → Learn → Next Plan
                  ↑                         │
                  └── Personal Travel Context ──┘
                               ↕
                          Vago Agent
```

AI Companion 仍可作为对话入口，但不再被理解为只负责生成 Structured Travel Plan 的单一节点。长期目标中的 Agent 需要贯穿整个闭环：旅行前理解限制，旅行中观察变化并协调，旅行后将事实沉淀为回忆和可审视的信号。

### 1.3 项目原则

| 原则 | 说明 |
| --- | --- |
| Personal-first | 用户自己的资料、偏好、行程、足迹、打卡、照片、笔记和回忆优先于公共内容与陌生人社交 |
| Facts first | GPS、Check-in、用户照片与笔记是原始旅行事实；AI 不得篡改或伪造它们 |
| Context-aware | 针对任务组合 Direct Context、SQL structured retrieval、semantic retrieval 与未来外部信息 |
| Human-in-the-loop | 读取和观察可自动完成；重要持久化或外部写操作必须经过适当确认 |
| Grounded memory | Travel Memory 必须以可追溯旅行事实为依据，叙事与事实分离 |
| Progressive evolution | 保留 FastAPI Modular Monolith 和已有领域资产，逐阶段演进，不进行 big-bang rewrite |
| Privacy by default | 个人旅行数据按用户隔离；位置与观察数据默认私有 |

## 2. 价值主张

### 2.1 为什么不是普通 LLM

普通一次性对话通常不持续拥有以下完整状态：

```text
past travel history
+ preferences
+ current trip
+ current itinerary
+ live footprint
+ check-ins
+ personal knowledge
+ travel memories
```

Vago 的差异化资产是持续积累的 **Personal Travel Context**。它让后续建议不只依赖当前的一句话 prompt，而能够在明确边界内理解“这个用户过去怎样旅行、正在经历什么、当前有什么约束”。

### 2.2 为什么不让用户自己在多个 App 间完成

用户可以自行在地图、日历、天气、航班、笔记和行程工具之间完成任务；难点是不断搜索、比较、复制、核对与重新安排。Vago Agent 的目标是降低这部分 **coordination cost**，而不是替用户拥有旅行决定权。

```text
User owns intention and important decisions.
Vago handles coordination, context gathering,
constraint checking and replanning.
```

## 3. Personal Travel Context

> Personal Travel Context = Vago 对“这个用户是谁、过去如何旅行、当前正在经历什么、当前旅行有哪些约束”所掌握的、与任务相关的状态视图。

它不是一个单独数据库，不等同于 RAG，也不要求所有信息先被转写为 prompt 或 embedding。Agent 按任务从多个 domain 和 retrieval source 中取得并组合它。

| Context 类别 | 典型信息 | 数据边界 |
| --- | --- | --- |
| Long-term personal context | explicit preferences、历史 Trip、visited places、Travel Memories、节奏/预算/兴趣倾向 | 明确偏好是用户事实；learned preference signals 是可审视推断，不自动成为永久事实 |
| Current trip context | current Trip、itinerary、交通/住宿、已确认计划、剩余活动与约束 | MySQL 中的结构化领域事实 |
| Live travel context | current location、recent footprint、check-ins、当前时间、旅行进度 | 由 iOS 等观察面产生的 grounded observations |
| Personal knowledge | KnowledgeSource、导入笔记、资料、回忆、用户明确选择的上下文 | Direct Context 或按需 semantic retrieval |
| External / ephemeral context | POI、路线、天气、日历、航班和其他现实世界信息 | 未来外部工具能力；不当作用户事实长期保存 |

### 3.1 Retrieval 的分工

- **Direct Context**：用户明确选择少量资料时直接使用。
- **SQL structured retrieval**：Trip、Spot、Footprint、预算和历史旅行等结构化事实通过领域服务读取。
- **Semantic RAG retrieval**：仅在大量非结构化个人知识需要语义搜索时，使用 embedding 与 Qdrant。
- **No Personal Context**：普通旅行知识问题不强制使用用户资料。

Qdrant / RAG 是 Personal Context 的可选能力，不是 KnowledgeSource 的主存储，更不是所有个人上下文的统一存储。

## 4. Agent Runtime 与领域边界

### 4.1 当前已实现的 AI 能力

当前 FastAPI 已提供 SSE 对话、可选个人知识语义检索、来源引用、现有 Tool Calling 形式的对话链路，以及结构化计划输入后的确认保存路径。这些能力仍主要服务于聊天、检索和计划草稿，不应被描述成完整的 Agent Runtime。

### 4.2 目标 Agent Runtime

```text
User Goal / Intent
        ↓
Acquire relevant context
        ↓
Interpret constraints
        ↓
Select tools → Execute read actions → Observe results
        ↓
Check constraints → Plan / Replan
        ↓
Request approval where required
        ↓
Execute domain action → Observe updated state → Complete
```

Agent Runtime 的职责是目标理解、循环与步骤协调、上下文获取、工具选择、约束检查、观察、重规划、审批边界和最终响应。它不直接操作数据库，也不以是否采用某个 Agent framework 或 MCP 作为能力定义。

### 4.3 Domain Services 与 Domain Tools

真实业务规则继续由 FastAPI 领域模块承担：Auth / User、Travel、Plan / Trip / Itinerary、Footprint / Check-in、Knowledge，以及未来的 Memory 与 Preferences。

Agent 应通过明确的内部 Domain Tools 使用这些能力，例如概念上的：

```text
get_current_trip
get_today_itinerary
get_recent_footprint
get_travel_history
get_user_preferences
search_personal_knowledge
update_itinerary
create_plan
```

这些是目标边界示例，不是本版本已新增的 API 或 Python package。Domain Tools 应调用领域服务；Agent 不应绕过服务直接读写 MySQL。

### 4.4 Human-in-the-loop

| Action 类型 | 例子 | 原则 |
| --- | --- | --- |
| Read / observe | 读取当前 Trip、日程、足迹、偏好、知识资料或未来天气/路线 | 通常可由 Agent 自主执行 |
| Proposed write | 修改 itinerary、创建 Trip、删除数据、未来 booking/payment | 在改变重要持久化旅行状态或产生外部影响前请求用户确认 |

当前阶段保持保守：会改变重要持久化旅行状态的 Agent action，执行前要求用户确认。本轮只建立该设计原则，不实现 approval engine。

## 5. Before / During / After Trip 场景

### 5.1 Scenario A：Personalized Trip Planning

用户提出出行目标、日期或限制后，Agent 未来可结合个人偏好、过往旅行、KnowledgeSource、已有计划约束和必要的外部旅行信息，形成可编辑的 context-aware plan。

这不同于一次 prompt 直接生成 itinerary：Agent 应说明关键约束与资料来源，并在写入 Plan / Trip 前请求确认。

**状态：目标能力。** 当前已有对话、可选知识检索和计划保存基础，但尚未实现完整跨领域 context acquisition 与 planning loop。

### 5.2 Scenario B：Adaptive Day Planner

示例：

> “我今天有点累了，重新安排接下来四个小时，晚上 8 点前回酒店。”

未来 Agent 需要综合：

```text
current location
+ recent footprint
+ current itinerary
+ remaining activities
+ user preferences
+ time constraints
+ external weather / routes / POI
```

并完成：

```text
observe → check constraints → search information → compare options
→ replan → ask for confirmation → update itinerary
```

**状态：目标能力。** 当前未实现 Adaptive Day Planner、外部信息接入或批准后的 itinerary 更新。

### 5.3 Scenario C：Travel Memory & Learning

```text
Trip facts + footprint + check-ins + photos / notes
        ↓
Grounded Travel Memory
        ↓
Preference / behavior signals
        ↓
Personal Travel Context
        ↓
Future Agent decisions
```

Travel Memory 不只是总结文章。它必须区分 confirmed facts、generated narrative 与 inferred preference signals。推断信号不自动等同于用户确认的偏好，未来可通过置信度、可见性或用户确认机制处理。

**状态：目标能力。** 当前尚未有 Memory、Photos 或 Notes domain。

## 6. 领域需求与状态

| 领域 | 当前已实现 | 继续建设 |
| --- | --- | --- |
| User / Auth | JWT、用户隔离、资料与会话 | 明确偏好与数据管理 |
| Personal Travel Knowledge | KnowledgeSource、文本/`.md/.txt`、可选索引 | URL 与更多资料来源的受控导入 |
| Plan / Trip / Itinerary | 核心 CRUD、计划转行程、生命周期和日程编辑 | 约束表达、受确认的 Agent action |
| Footprint / Check-in | 前台采样、离线同步、服务端事实、MapKit 轨迹与打卡 | 历史地图、详情、Fog 实验与观察扩展 |
| Photos / Notes | 未开发 | 绑定 Trip / Day / Spot / Check-in，二进制走对象存储 |
| Travel Memory | 未开发 | grounded summary、timeline、highlights 与可编辑 narrative |
| Preferences | 用户设置基础存在 | explicit preferences 与 learned signals 的边界 |

### 6.1 旅行观察与事实保护

GPS、Check-in、未来照片和用户笔记是 Travel Observations。它们是 Agent 理解旅行进度的重要输入，但原始事实不可被 AI 覆盖。地图路线、探索区域、Memory summary 与偏好信号均是基于事实的派生结果，应保留来源与不确定性边界。

### 6.2 Travel Memory 要求

- 以 itinerary、GPS、打卡、照片 metadata、用户笔记、时间与统计等真实旅行事实为输入。
- 不生成用户未到访地点或未发生事件。
- 事实数据、AI narrative 和用户编辑内容分离。
- 用户可编辑生成文本；未来共享前需遵循位置隐私边界。

## 7. External Tools / MCP

External Tools 是未来补足现实世界临时信息的能力边界。候选集成包括 place search / routes / weather、Google Calendar、航班搜索（例如 Kiwi.com）及后续旅行服务。

> MCP 是标准化接入外部工具的一种方式，不是 Agent 本身，也不是 Vago 内部 Domain Service 必须采用的协议。

内部的 `get_trip`、`get_recent_footprint`、`update_itinerary` 等能力优先保持为内部 Domain Tools。只有在有明确用户价值的 Agent workflow 后，才评估以 MCP 或其他适配方式连接外部能力。

**状态：未来候选能力。本版本没有 MCP 配置、外部 Provider 集成或外部写操作。**

## 8. 非功能性要求

| 类型 | 要求 |
| --- | --- |
| Privacy | 位置、知识、照片和回忆按用户隔离；分享时需额外设计坐标脱敏与可见性 |
| Security | JWT、当前用户归属校验、关键写操作确认、删除权与审计边界 |
| Reliability | AI/外部信息不可用时明确降级；GPS 可离线缓存并按幂等键重试 |
| Explainability | Agent 应说明关键约束、使用的资料或信息不可用原因，不伪造观察结果 |
| Maintainability | FastAPI Modular Monolith；domain service、domain tool、Agent Runtime 与存储边界清晰 |
| Testability | 领域归属、事实 grounding、工具调用、审批边界、失败回退与重规划应可单独测试 |

## 9. 路线图

历史 Phase 0–8 保留为已发生的 remould 与双端建设过程，不重新编号。

| Phase | 目标 | 状态 |
| --- | --- | --- |
| 9 | **Travel Memory & Personal Context Foundation**：grounded Memory、历史旅行上下文、明确偏好与可审视行为信号 | 未来 |
| 10 | **Agent Runtime & Vago Domain Tools**：Agent loop、context acquisition、工具边界、观察、约束检查、审批原则、最小 tracing/testability 设计 | 未来 |
| 11 | **Context-aware Coordination & Replanning**：以 Adaptive Day Planner 为代表，在确认后更新 itinerary | 未来 |
| 12 | **External Tool / MCP Integration**：在已有有意义的 workflow 上渐进接入地图、日历、天气或航班等外部能力 | 未来 |

不以多 Agent、MCP、复杂 GIS 或微服务数量作为里程碑完成条件。每一阶段应首先验证用户协调成本是否被真实降低。

## 10. 当前边界

- FastAPI 是当前唯一后端，并继续演进为模块化单体。
- React Web 与 Native SwiftUI iOS 的分工保持不变。
- MySQL 保存结构化旅行事实；Qdrant 仅保存可选语义检索所需向量数据；原始媒体未来使用对象存储。
- 当前仅支持纯文本与 `.md/.txt` KnowledgeSource；PDF、DOCX 和复杂 ingestion platform 不在本阶段范围。
- 不实现后台持续定位、多 Agent、复杂 GIS、自动 booking/payment 或未经确认的 Agent 写操作。
