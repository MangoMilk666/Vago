---
name: vago-project-skill
description: 指导 Vago 项目的长期产品演进、Agent 架构、Personal Travel Context、工程边界与 Codex 开发决策。
---

# Vago Project Skill

## Purpose

本 Skill 定义 Vago 的长期产品方向、架构边界和工程原则。

它不保存：

- 历史迁移进度；
- 具体 Feature 实施计划；
- 已完成 Phase；
- 固定 Agent 框架选择。

这些内容分别以当前代码、PRD、architecture、migration inventory 和 `docs/design/` 为准。

若文档与代码冲突，以仓库事实为准；若用户当前 prompt 与本 Skill 冲突，以用户明确要求为准。

------

# 1. Product Positioning

Vago 的长期定位：

> **AI-Native Personal Travel Intelligence / Personal Travel Agent System**

核心不是旅行社区、Chatbot 或单次 AI 行程生成，而是持续积累 **Personal Travel Context**，让真实旅行经历影响当前和未来 Agent 决策。

核心闭环：

```text
Plan
 ↓
Travel
 ↓
Observe
 ↓
Memory
 ↓
Learn
 ↓
Next Plan
```

贯穿整个闭环：

```text
Personal Travel Context
          ↕
     Vago Agent
```

Vago 的主要价值是降低用户在地图、天气、日历、行程、历史记录等信息之间进行人工协调的成本。

原则：

```text
User owns:
- intention
- preferences
- important decisions
- approval

Vago handles:
- context gathering
- coordination
- constraint checking
- tool execution
- replanning
```

------

# 2. Product Principles

## Personal-first

优先服务用户自己的：

- Preferences；
- Knowledge；
- Trips；
- Itineraries；
- Footprints；
- Check-ins；
- Photos / Notes；
- Travel Memories；
- Travel History。

Public Community 不再属于核心产品域。

分享可以存在，但属于旅行结果输出，不重新发展完整社交平台。

## Agent-native, not Chatbot-first

Chat 只是用户表达 Intent 的交互界面。

目标 Agent 流程：

```text
Goal
 ↓
Acquire Context
 ↓
Select Tool
 ↓
Execute
 ↓
Observe
 ↓
Check Constraints
 ↓
Continue / Replan
 ↓
Approval if required
 ↓
Domain Action
```

Agent 应进入真实业务流程，而不是只返回文本。

## Grounded in Real Travel

严格区分：

```text
Observed / Confirmed Facts
≠
AI-generated Narrative
≠
Inferred Preference Signals
```

GPS、Check-in、Trip 状态、Notes、Photo Metadata 等事实不得被模型篡改或凭空补充。

## Human-in-the-loop

Agent 可自主执行低风险读取和检索。

会改变重要持久化状态的操作，例如重要 Itinerary 修改、删除数据、未来 Booking / Payment，应设置用户确认边界。

## Mobile-native

Web 与 iOS 不机械复制。

Web 偏向：

- Knowledge 管理；
- 复杂规划；
- Trip / Itinerary 编辑；
- 历史数据与 Memory 管理。

iOS 偏向：

- 当前旅行；
- Travel Map；
- GPS / Check-in；
- Photos / Notes；
- 实时 Agent Interaction；
- 旅行中 Replanning。

Agent Runtime 保持在 Backend，不放入 iOS UI 层。

------

# 3. Personal Travel Context

Personal Travel Context 是 Agent 针对当前任务组合出的用户旅行状态，不是单一数据库，也不等于 RAG。

主要来源：

### Long-term Context

- Preferences；
- Past Trips；
- Visited Places；
- Travel Memories；
- Learned Preference Signals。

### Current Trip Context

- Current Trip；
- Itinerary；
- Hotel / Transport；
- Remaining Activities；
- Trip Constraints。

### Live Context

- Current Location；
- Recent Footprint；
- Check-ins；
- Current Time；
- Travel Progress；
- Photos / Notes。

### Personal Knowledge

- KnowledgeSource；
- Imported Guides；
- Notes；
- Long-form Memories。

### External Context

通过 API / SDK / MCP 获取：

- POI；
- Routes；
- Weather；
- Calendar；
- Flights；
- 其他实时旅行信息。

------

# 4. Retrieval Strategy

不要将 Personalization 等同于 RAG。

## Structured Data

Trip、Itinerary、GPS、Budget、Check-in、Statistics 等：

```text
Domain Service
→ SQL
```

## Direct Context

用户明确选择少量资料时直接提供给 Agent，不为了使用 RAG 再次检索。

## Semantic Retrieval

仅当个人非结构化资料较多且需要跨文档搜索时使用：

```text
Embedding
→ Qdrant
→ Relevant Personal Knowledge
```

## Preferences

明确偏好优先保存为结构化 Profile。

必须区分：

```text
Confirmed Preference
≠
Learned Preference Signal
```

模型推断不得自动覆盖用户明确设置。

------

# 5. Target Architecture

```text
React Web                 SwiftUI iOS
    │                         │
    └──────────┬──────────────┘
               ▼
            FastAPI
               │
        ┌──────▼──────┐
        │ Agent Runtime│
        └──────┬──────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
 Domain Tools      External Tools
      │               / MCP
      ▼
 Domain Services
      │
 Auth / Travel / Knowledge
 Footprint / Memory / Preferences
      │
      ▼
MySQL / Redis / Qdrant / Object Storage
```

后端继续采用：

> **FastAPI Modular Monolith**

不要因为 Agent 化改成微服务。

------

# 6. Agent Runtime

Agent Runtime 负责：

- Goal / Intent；
- Context acquisition；
- Tool selection；
- Tool execution；
- Observation；
- Constraint checking；
- Replanning；
- Approval；
- Completion；
- Tracing / Evaluation boundary。

Agent Runtime 不应：

- 直接操作数据库；
- 绕过 Domain Service；
- 重复实现业务逻辑；
- 将所有数据都塞进 Prompt。

------

# 7. Domain Tool Boundary

Agent 通过明确的 Domain Tool 使用业务能力。

示例：

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

Tool 应：

- 对应明确业务能力；
- 使用结构化输入输出；
- 执行用户 ownership 校验；
- 隐藏数据库细节；
- 控制副作用。

不要暴露：

```text
execute_sql
update_any_table
delete_any_record
```

这类通用数据库 Tool。

------

# 8. Constraint Checking & Replanning

Vago 的核心 Agent 能力之一是：

> **Constraint-aware Replanning**

对于适合确定性校验的约束，例如：

- Deadline；
- Budget；
- Itinerary Conflict；
- Route Feasibility；
- Duration；
- Explicit Restrictions；

不要完全依赖 LLM 自觉遵守。

推荐流程：

```text
Agent Proposal
      ↓
Constraint Check
   ↙       ↘
Pass     Violation
           ↓
       Observation
           ↓
         Replan
```

Probabilistic Agent Decision 与 Deterministic Business Rule 应保持明确边界。

------

# 9. Travel Observation & Memory

iOS 收集的真实旅行数据是 Personal Travel Context 的重要来源：

- GPS；
- Footprint；
- Check-in；
- Trip Progress；
- Photos；
- Notes；
- Timestamps。

Travel Memory 应建立在这些事实之上：

```text
Travel Facts
     ↓
Grounded Memory
     ↓
Preference / Behavior Signals
     ↓
Personal Travel Context
     ↓
Future Agent Decisions
```

Travel Memory 不只是 AI Summary，而是长期学习闭环的一部分。

------

# 10. Agent Framework Policy

Vago 暂时不绑定固定 Agent Framework。

以下均属于实现选择：

- OpenAI Agents SDK；
- LangChain；
- LangGraph；
- PydanticAI；
- Lightweight Custom Runtime；
- 其他后续稳定方案。

只有真实需求出现时才引入复杂 Runtime。

判断依据包括：

- State；
- Tool Execution；
- Persistence；
- Human Approval；
- Durable Execution；
- Replanning；
- Tracing；
- Evaluation；
- Conditional Workflow。

简单 Tool-calling Loop 足够时，不为了展示技术引入 Graph Framework。

若后续的用户Prompt明确引入某个framework，或者已经有明确的相关代码提交记录，则默认继续使用该framework。

------

# 11. MCP Policy

MCP 不是 Agent，也不是产品卖点。

原则：

```text
Internal Vago Capability
→ Domain Tool

External Capability
→ API / SDK / MCP when justified
```

适合 MCP 的未来外部能力包括：

- Maps；
- Calendar；
- Flights；
- Weather；
- Booking Services。

不要为了展示 MCP：

- 把全部内部 API MCP 化；
- 创建无实际需求的 MCP Server；
- 把 MCP 数量当 Agent 能力指标。

------

# 12. Core Agent Showcase

优先构建：

> **Adaptive Day Planner**

示例：

> “我今天有点累了，重新安排接下来四个小时，晚上 8 点前回酒店。”

目标流程：

```text
Goal
 ↓
Current Location
 ↓
Recent Footprint
 ↓
Current Itinerary
 ↓
Preferences
 ↓
External Context
 ↓
Candidate Plan
 ↓
Constraint Check
 ↓
Replan if needed
 ↓
User Approval
 ↓
Update Itinerary
 ↓
Verify
```

该场景应体现：

- Personal Context；
- Tool Calling；
- Real-world Observation；
- Coordination；
- Constraint Checking；
- Replanning；
- Human-in-the-loop；
- Domain Action。

不要为了复杂度强行 Multi-Agent。

------

# 13. Data Responsibilities

## MySQL

结构化长期业务事实：

- User；
- Trip；
- Itinerary；
- Footprint；
- Check-in；
- Preferences；
- Memory Metadata。

## Redis

短期运行状态：

- Session；
- Cache；
- Rate Limit；
- 必要的 Temporary Agent State。

Redis 不作为长期事实主存储。

## Qdrant

仅负责非结构化 Personal Knowledge 的 Semantic Retrieval。

不要将所有结构化数据向量化。

## Object Storage

用于 Photos、Documents 和其他 Binary Assets。

------

# 14. Engineering Principles

## Modular Monolith First

默认 FastAPI Modular Monolith。

没有明确需求时不要增加：

- Microservices；
- Kafka；
- Kubernetes；
- Service Mesh；
- Gateway；
- Distributed Event Architecture。

## No Resume-driven Architecture

不要为了简历关键词强行：

- Multi-Agent；
- MCP；
- LangGraph；
- GraphQL；
- CQRS；
- 新数据库；
- 新 Agent Framework。

每项技术必须回答：

> 它解决了 Vago 的什么具体问题？

## Preserve Working Features

重构遵循：

```text
Implement
→ Test
→ Switch Caller
→ Verify
→ Remove Legacy
```

## Avoid Premature Abstraction

不要提前构建：

- Generic Workflow Engine；
- Universal Plugin System；
- Complex Event Bus；
- Generic MCP Layer；
- Advanced GIS Infrastructure。

先实现真实 Use Case，再从重复问题中抽象。

------

# 15. Privacy & Isolation

旅行数据属于高隐私数据。

必须保证：

- 用户级数据隔离；
- Server 根据 Authenticated User 判断 Ownership；
- 不信任客户端 `user_uuid` 作为权限依据；
- GPS 不进入普通日志；
- RAG 按用户 Scope；
- Local Cache 按账号隔离；
- Logout 后不得泄漏其他账号缓存；
- Production 使用 HTTPS。

------

# 16. Testing & Agent Evaluation

业务测试至少覆盖：

- Auth；
- Ownership；
- Trip / Itinerary；
- Knowledge Isolation；
- Footprint Sync；
- Memory Grounding。

Agent 不应只测试最终文本质量。

逐步评估：

- Context 是否正确；
- Tool 是否正确；
- Constraint 是否满足；
- Violation 后是否 Replan；
- Write Action 是否正确请求 Approval；
- 是否 Grounded；
- 是否完成用户 Goal。

Agent Runtime 应逐步支持记录：

- Tool Calls；
- Observations；
- Constraint Results；
- Approval Events；
- Final Outcome。

------

# 17. Documentation Boundary

长期规则：

```text
vago-project-skill
vago-coding-skill (coding落地时调用)
```

产品：

```text
README.md
docs/prd/PRD.md
```

架构：

```text
docs/architecture.md
```

迁移状态：

```text
docs/remould-migration-inventory.md
```

Feature 设计：

```text
docs/design/
```

例如未来按需建立：

```text
agent-runtime.md
personal-travel-context.md
travel-memory.md
adaptive-day-planner.md
```

不要将历史 Phase 或具体 Feature 实现重新塞入本 Skill。

------

# 18. Codex Execution Rules

每次修改项目前：

1. 先理解用户当前要求；
2. 检查相关代码和仓库状态；
3. 阅读当前任务直接相关的文档；
4. 查看 git status / diff；
5. 明确本次 scope；
6. 优先小范围、可验证修改；
7. 不顺手扩大需求；
8. 修改 API 时检查调用方；
9. 修改 Schema 时检查数据兼容；
10. 修改 Agent Tool 时保持 Domain Boundary；
11. 修改 Write Action 时检查 Approval；
12. 删除代码前搜索依赖；
13. 运行相关测试；
14. 更新真正受影响的文档。

始终区分：

```text
Implemented
In Progress
Target / Future
```

不得把 roadmap 或目标架构描述成当前已实现能力。

------

# 19. Long-term Definition of Done

Vago 最终应能够证明：

```text
Plan
 ↓
Travel
 ↓
Observe
 ↓
Memory
 ↓
Learn
 ↓
Future Decision
```

并至少有一个真实 Agent 场景完整体现：

```text
Goal
→ Context
→ Tool
→ Observation
→ Constraint Check
→ Replan
→ Approval
→ Domain Action
→ Verification
```

最终项目应满足：

- Personal Travel Context 是核心长期资产；
- Agent 不退化成 Chatbot；
- RAG 只是 Context Retrieval 能力；
- 真实旅行 Observation 能进入 Agent Context；
- Travel Memory 基于事实；
- 历史旅行能够影响未来决策；
- Agent 能协调 Internal / External Tools；
- Constraint Checking 与 LLM Decision 有明确边界；
- 重要 Write Action 保留 Human-in-the-loop；
- MCP 只在真实外部集成需求出现时使用；
- 架构复杂度与个人项目规模匹配；
- 当前能力与 Future Capability 始终明确区分。
