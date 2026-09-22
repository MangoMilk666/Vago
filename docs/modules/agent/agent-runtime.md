# Vago Agent Runtime 设计与开发参考

> 状态：目标设计。当前已具备 SSE 对话、可选个人知识检索与结构化计划保存；尚未实现完整 Agent Runtime、Travel Memory、跨领域协调或外部工具接入。



## 定位

Vago 是 **AI-Native Personal Travel Intelligence / Personal Travel Agent System**。Agent 的价值不是生成一次行程文本，而是在用户保有意图、重要决定与批准权的前提下，降低资料、行程、实时旅行状态和外部信息之间的协调成本。

```text
Plan → Travel → Observe → Memory → Learn → Next Plan
                  ↕
        Personal Travel Context + Vago Agent
```

## 目标效果

第一条代表性工作流是 **Adaptive Day Planner**：用户提出“我有点累，重新安排接下来四小时，晚上八点前回酒店”，Agent 获取当前行程、近期足迹、打卡、明确偏好与必要外部信息，通过多轮 Tool Calling 获取 observation，检查时间、冲突和路线约束，并在违反约束或工具失败时调整方案；用户确认后才更新日程。

Agent 不拥有旅行决策权，也不伪造 GPS、打卡、照片、用户笔记等事实。

## 目标架构

```text
React Web / SwiftUI iOS
          │
       FastAPI
          │
     Agent Runtime
 think · execute · observe
 replan · approval · terminate
          │
      Tool Registry
       /        \
Vago Domain     External Tools / MCP
   Tools
     │
Domain Services
Travel · Footprint · Knowledge · Preferences · Memory
     │
MySQL · Redis · Qdrant · Object Storage

Agent Runtime
     │
     └── Agent Event Stream ──SSE──> Web / iOS
```

- **Agent Runtime**：维护 Agent loop，根据目标和 observation 决定下一步工具调用、重规划、批准或结束。
- **Tool Registry**：统一注册 Agent 可使用的工具及其 schema、权限和执行入口，避免在 Runtime 中硬编码工具分支。
- **Domain Services**：继续拥有业务规则、用户归属校验和持久化；Agent 不直接操作数据库。
- **Personal Travel Context**：按任务组合长期偏好与历史、当前行程、实时观察、个人知识和必要外部信息。
- **External Tools / MCP**：仅作为外部能力接入边界；内部能力优先使用 Domain Tools。
- **Agent Event Stream**：将工具调用、结果、错误、约束检查、审批和完成状态通过结构化事件实时提供给 Web / iOS。

## Agent Loop

Runtime 采用显式的 **Think / Decide → Execute → Observe** 循环：

```text
Goal
 ↓
Acquire Initial Context
 ↓
Think / Decide
 ↓
Select Tool
 ↓
Execute
 ↓
Observation
 ↓
Think / Decide
 ├── call another tool
 ├── constraint check
 ├── replan
 ├── request approval
 └── complete
```

`Think / Decide` 表示模型根据当前 state 和 observation 决定下一步动作，不向客户端暴露模型内部 chain-of-thought。

每次 Tool 执行结果都作为新的 **Observation** 返回 Runtime，使 Agent 基于真实结果继续决策，而不是预先生成固定执行步骤。

Runtime 必须具有明确终止条件：Goal 完成、等待 Approval、不可恢复错误、达到最大 Loop Step 或用户取消。禁止无上限循环或无限 Tool Retry。

## Tool Registry 与工具边界

Runtime 不应通过大量 `if tool_name == ...` 管理工具。工具统一注册到 Tool Registry，并至少描述：Tool name、description、input/output schema、read/write 属性、approval requirement 与 execution handler。

示例：

```text
Tool Registry
├── get_current_trip
├── get_today_itinerary
├── get_recent_footprint
├── get_checkins
├── get_user_preferences
├── search_personal_knowledge
├── check_itinerary_constraints
├── propose_itinerary_update
└── apply_approved_itinerary_update
```

| Context 类型       | 首选来源                     | 示例工具                                                     |
| ------------------ | ---------------------------- | ------------------------------------------------------------ |
| Long-term          | SQL / future Memory          | `get_travel_history`、`get_user_preferences`                 |
| Current trip       | Travel domain                | `get_current_trip`、`get_today_itinerary`                    |
| Live travel        | Footprint domain             | `get_recent_footprint`、`get_checkins`                       |
| Personal knowledge | Direct Context / 按需 Qdrant | `search_personal_knowledge`                                  |
| Constraint         | Deterministic service        | `check_itinerary_constraints`                                |
| Write action       | Travel domain                | `propose_itinerary_update`、`apply_approved_itinerary_update` |

Tool 使用结构化输入输出，内部完成 user ownership 校验并隐藏 SQL。不要向 Agent 暴露 `execute_sql`、`update_any_table` 等基础设施级工具。

Qdrant 只用于非结构化个人资料语义检索；结构化旅行事实通过 Domain Service / MySQL 获取。

## Tool Failure 与 Replanning

Tool failure 是 Observation，不应默认直接终止整个 Agent。

```text
Tool Call
   ↓
 Success ───────→ Observation
   │
 Failure
   ↓
Error Observation
   ↓
Agent Decision
 ├── retry when justified
 ├── use alternative tool
 ├── replan
 ├── degrade gracefully
 └── terminate with explanation
```

Runtime 应区分可恢复与不可恢复错误，并限制 retry 次数。外部能力不可用时允许降级，但不得编造结果。

## Constraint Checking 与 Replanning

对于适合确定性验证的约束，例如 deadline、budget、itinerary conflict、route feasibility、duration 和 explicit restrictions，不依赖模型自行判断。

```text
Agent Proposal
      ↓
Constraint Check
   ↙         ↘
 PASS      VIOLATION
              ↓
         Observation
              ↓
            Replan
              ↓
       Constraint Check
```

Constraint Result 作为 Observation 返回 Agent。Probabilistic Agent Decision 与 Deterministic Business Rule 保持明确边界。

## Approval 与 Domain Action

读取当前 Trip、日程、足迹、打卡、偏好或个人知识通常可以自动执行。

重要持久化写操作必须先形成结构化 Proposal，并进入 `AWAITING_APPROVAL`。例如创建或修改 Trip / Itinerary、删除用户数据，以及未来 Booking / Payment。

用户批准后才调用真正的 Write Tool，并在执行后重新读取状态进行验证。

## Agent Event Stream

现有 SSE 不应只承担 LLM 文本 token streaming。Agent Runtime 应逐步提供结构化 **Agent Events**：

```text
agent.started
agent.status

tool.started
tool.completed
tool.failed

constraint.checked

approval.required
approval.resolved

response.delta

agent.completed
agent.failed
```

示例：

```json
{
  "type": "tool.started",
  "tool": "get_recent_footprint",
  "label": "正在查看今天的旅行足迹"
}
```

```json
{
  "type": "tool.completed",
  "tool": "get_recent_footprint",
  "summary": "已获取今天的旅行足迹"
}
```

前端可以据此展示用户可理解的执行轨迹，例如：

```text
✓ 获取当前行程
✓ 查看今天足迹
✓ 获取旅行偏好
✓ 搜索附近地点
✓ 计算返回路线
✓ 检查时间约束

正在重新规划...
```

客户端展示的是 **Execution / Action Trace**，而不是模型内部 reasoning 或 chain-of-thought；这样的设计有助于提升用户体验。

同一套 Event Model 应尽量同时服务 Web / iOS Agent Activity UI、Debugging、Tracing、Approval 与 Evaluation。事件不得泄露 chain-of-thought、敏感 Prompt、Access Token、原始 GPS 等不必要敏感数据或数据库内部信息。

## RAG 在 Agent 中的定位

RAG 是 Agent 可选择使用的 Personal Context Tool，而不是固定执行步骤。

```text
Agent
 ├── Current Trip → Domain Tool
 ├── Footprint → Domain Tool
 ├── Preferences → Domain Tool
 ├── Personal Knowledge → RAG Tool when needed
 └── External Context → External Tool when needed
```

只有任务需要跨大量非结构化个人资料检索时，才调用 `search_personal_knowledge`。

必须区分 confirmed facts、generated narrative 与 learned preference signals；learned signal 不得自动覆盖用户明确偏好。

## Runtime State

第一版保持简单状态：

```text
IDLE
 ↓
THINKING
 ↓
EXECUTING
 ↓
THINKING
 ↓
...
 ↓
AWAITING_APPROVAL
 ↓
EXECUTING
 ↓
DONE
```

任意执行阶段可以进入 `ERROR`。状态用于 Runtime 控制和客户端展示，不要求把每个内部步骤都建成复杂状态机。

## 分阶段开发

| 阶段     | 目标与最小交付                                               | 不做什么                                                 |
| -------- | ------------------------------------------------------------ | -------------------------------------------------------- |
| Phase 9  | Grounded Travel Memory、历史旅行上下文、明确偏好与可审视 signal | 不把模型推断写成确认事实，不做复杂记忆系统               |
| Phase 10 | 最小 Think-Execute-Observe Runtime、Tool Registry、内部 Domain Tools、Agent Event Stream、错误与最大步数控制、Tracing | 不直连数据库，不为了框架引入 Multi-Agent / Graph Runtime |
| Phase 11 | Adaptive Day Planner：真实旅行 Context、确定性 Constraint Check、Replanning、Approval、Write Action 与 Verification | 不未经确认修改重要旅行状态                               |
| Phase 12 | 为已验证 workflow 接入 POI、路线、天气、Calendar、Flights 等 External Tools / MCP | 不为展示 MCP 创造工作流                                  |

## 技术与验证

- 后端保持 **FastAPI Modular Monolith**；Runtime、Tool Registry、Domain Tools 与 Domain Services 保持清晰 Python 边界。
- Agent framework 暂不绑定；简单 Tool-calling Loop 足够时不引入 Graph Runtime。
- 复用现有 SSE，并从纯文本 streaming 扩展为 Agent Event Stream。
- Tool Result、Tool Error、Constraint Result 都作为 Observation 进入 Runtime。
- 记录 Tool Call、Context Source、Constraint Result、Approval Event、Failure 和 Final Outcome。
- 测试不仅验证回复文本，还覆盖 Tool Selection、User Isolation、Failure Recovery、最大步数、Constraint Replanning、Write Approval 和 Grounding。

## 完成标准

完成一个真实 Agent Workflow 时，应能证明：

1. Agent 根据 Goal 获取了正确的 Personal Travel Context；
2. Agent 可以执行多轮 `Decide → Tool → Observe`，而不是固定 Pipeline；
3. Tool 通过 Registry 和 Domain Boundary 执行，不直接访问数据库；
4. Tool Failure 可以成为 Observation，并触发合理 Retry / Replan / Fallback；
5. RAG 仅在需要 Personal Knowledge 时被选择；
6. Deterministic Constraint 被检查，Violation 能触发 Replanning；
7. 重要 Write Action 已获得用户 Approval；
8. 操作后的 Domain State 被再次验证；
9. Web / iOS 可以通过 Agent Event Stream 展示用户可理解的执行轨迹；
10. Runtime 有明确 Termination / Max Step 机制。

框架数量、MCP 数量、Tool 数量或“自主性”不是完成标准。
