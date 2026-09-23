# Vago Agent Runtime 设计与开发参考

> 状态：Phase 10 基线已实现。当前具备 SSE 对话、持久化会话、可选个人知识检索，以及最小只读 Agent Runtime / Tool Registry / Agent Event Stream。该 Runtime 仍按用户授权预取固定领域上下文，尚未实现 prompt-aware tool selection、跨领域协调、约束检查、审批或外部工具接入。

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
Goal + Conversation Context + Authorization
 ↓
Select Necessary Tools (may be none)
 ↓
Acquire Initial Observation
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

### 授权不是执行指令

`usePersonalContext` 与 `useRag` 的语义是本轮**允许** Runtime 使用哪些资料，不能直接等同于“必须读取所有对应领域”。本轮可调用工具集合是授权上限；实际工具集合由用户目标、最近对话和已有 Observation 决定，且允许为空。

```text
Authorization Ceiling
        ↓
Prompt-aware Tool Selection
        ↓
Selected Tool Plan (0..N)
        ↓
Domain Tool / RAG Tool
        ↓
Task-scoped Personal Travel Context
```

例如，普通目的地知识问题可以不读取任何个人资料；“我今天有点累，接下来怎么安排”才可能需要当前行程、今日日程与近期旅行观察。用户关闭个人资料授权时，选择器不得选择对应工具。

当前 Phase 10 基线仍以授权开关固定读取部分工具，这是兼容既有对话链路的过渡实现。Phase 10.1 起应以本节定义的选择策略替代它。

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

### 工具选择策略

选择器输入只包含当前用户目标、最近少量必要对话、授权范围与工具能力描述；它不会预先读取或注入用户旅行事实。输出应是受 allowlist 和最大步数约束的 `ToolSelectionPlan`：

```text
intent
selected_tools
max_steps
needs_clarification
```

第一版优先采用确定性规则，不为了决定是否读一条 SQL 数据而额外调用 LLM。规则无法判断的模糊复杂请求，后续才可使用受限的结构化 LLM selector；该 selector 也只能选择已授权的工具或 `no_tool`，不能直接访问事实、写数据或绕过 Domain Service。

| 用户目标示例 | 预期初始工具 |
| --- | --- |
| “新加坡十月天气如何？” | 无个人工具 |
| “我当前行程还剩什么？” | `get_current_trip`、`get_today_itinerary` |
| “结合我的旅行习惯推荐目的地” | `get_user_preferences`、`get_recent_travel_history`、必要时 `get_travel_memories` |
| “我今天累了，接下来四小时怎么安排？” | `get_current_trip`、`get_today_itinerary`，确认进行中行程后可读取 `get_recent_footprint` |
| “我保存的京都资料有什么建议？” | `search_personal_knowledge` |

当前 `get_current_trip` 同时返回当前行程和近期历史，粒度过粗；后续必须拆分，避免“查今天日程”顺带注入历史旅行数据。`useRag` 只表示可注册 `search_personal_knowledge`，不应导致每轮固定读取知识库摘要或固定检索 Qdrant。

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

| 阶段 | 目标与最小交付 | 不做什么 |
| --- | --- | --- |
| Phase 9 | 进行中：Grounded Travel Memory、历史上下文、明确偏好与 Web Context 注入；signals 待真实数据验证 | 不把模型推断写成确认事实，不做复杂记忆系统 |
| Phase 10（基线，已实现） | 最小只读 Think-Execute-Observe Runtime、Tool Registry、内部 Domain Tools、SSE Agent Event、错误降级与步数上限 | 不直连数据库，不引入 Multi-Agent / Graph Runtime；该阶段固定预取仍是过渡实现 |
| Phase 10.1 | **Prompt-aware deterministic selection**：以当前 prompt、少量会话上下文和授权范围输出 0..N 个初始工具；把授权从执行指令改为权限上限 | 不增加一次 LLM 调用作为默认选择器；不读取未被本轮计划选中的领域数据 |
| Phase 10.2 | **工具粒度与受控 Observation 链**：拆分当前行程、日程、历史、足迹、打卡等读取边界；工具结果不足时再选择下一步，默认每轮最多 3 次只读调用 | 不把整份 Trip / 全量轨迹 / 全部历史拼入 Prompt；不把知识摘要当作固定步骤 |
| Phase 10.3 | **模糊请求的受限 selector 与可评估性**：仅对规则无法覆盖的复杂问题使用结构化 selector；补充 Trace、token / latency / tool-count 指标与 prompt-to-tools 回归集 | selector 不接触个人事实、不输出 chain-of-thought、不拥有写权限 |
| Phase 11 | **Adaptive Day Planner**：真实旅行 Context、确定性 Constraint Check、Replanning、Approval、Write Action 与 Verification | 不未经确认修改重要旅行状态；不以模型判断代替确定性领域约束 |
| Phase 12 | 为已验证 workflow 接入 POI、路线、天气、Calendar、Flights 等 External Tools / MCP | 不为展示 MCP 创造工作流 |

### Phase 10.1 — Prompt-aware deterministic selection

**实施状态：已完成。**

**目标：** 让“无工具”成为正常结果，且仅在用户问题确实涉及个人旅行状态时读取对应领域。

- Runtime 接收当前用户消息及最近少量必要会话上下文，而不是只接收授权开关。
- 新增纯函数式 `ToolSelectionPolicy`，输入为 prompt、会话指代信息、授权范围与可用工具；输出为 `ToolSelectionPlan`。
- 选择器首先处理明确意图：通用旅行知识、当前行程/日程、历史回顾、实时旅行进度、明确偏好、个人资料检索及需要澄清的问题。
- SSE 只发送真实执行的 `tool.started / completed / failed`；没有调用工具时只能显示通用准备或完成状态，不能伪造读取轨迹。
- 单元测试以“prompt → expected tools / no tool”为主，并覆盖关闭授权、跨账号与多轮指代。

### Phase 10.2 — 工具粒度与受控 Observation 链

**目标：** 避免一个粗粒度工具带入无关事实，同时允许后续读取建立在前一条真实 Observation 上。

- 将 `get_current_trip` 的“当前行程 + 近期历史”职责拆分为 `get_current_trip`、`get_today_itinerary`、`get_recent_travel_history`；按现有 Domain Service 逐步补齐最小读取接口。
- 将 `get_recent_footprint`、`get_checkins` 保持为行程归属明确后才能执行的后续工具，避免盲查无关或跨行程事实。
- 将个人知识改为真正按需的 `search_personal_knowledge`；`useRag` 只注册能力，不能固定读取 metadata 或强制向量检索。
- Runtime 将前一工具输出保存为 Observation；只有结果表明信息不足、存在进行中 Trip 或任务依赖成立时，才选择下一工具。
- 保持 Domain Service 的授权、隐私过滤与查询上限；初始默认上限为每轮 3 次只读工具调用，超限必须说明信息边界或请求澄清。

### Phase 10.3 — 模糊请求的受限 selector 与评估

**目标：** 在不为每轮增加不必要模型调用的前提下，处理规则难以识别的复杂、多意图或省略指代问题。

- 只在确定性 Policy 无法给出可靠计划时调用结构化 selector；它的输入不包含真实个人事实，只包含用户目标、允许工具的描述和授权范围。
- selector 输出必须是 allowlist 中的工具名、最大步数或 `no_tool`；Runtime 继续负责参数构造、Domain Service 调用和权限校验。
- 建立评估集与观测指标：工具选择准确率、误调用率、零工具比例、输入 token、P50/P95 延迟、RAG 命中率与任务完成质量。
- 将 selector 结论和实际执行轨迹分别记录，便于比较“计划工具”与“真实工具”，但不记录或向客户端展示模型 chain-of-thought。

### Phase 11 — Context-aware Coordination & Replanning

**目标：** 在 Phase 10 的按需读取能力之上实现 Adaptive Day Planner，而不是重新引入固定上下文预取。

```text
用户目标
  → 选择必要事实工具
  → Observation
  → 确定性约束检查
  → 方案 / 重规划
  → 用户确认
  → Domain Write Action
  → 再读取验证
```

初始场景以“我今天有点累，重新安排接下来四个小时，晚上八点前回酒店”为代表。Agent 只读取解决该问题所需的当前行程、剩余日程、近期观察和必要外部信息；重要 itinerary 更新必须在结构化 proposal 经用户确认后执行。

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
