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

第一条代表性工作流是 **Adaptive Day Planner**：用户提出“我有点累，重新安排接下来四小时，晚上八点前回酒店”，Agent 获取当前行程、日程、近期足迹、打卡、明确偏好与必要外部信息，检查时间、冲突和路线约束，提出候选调整；用户确认后才更新日程。

Agent 不拥有旅行决策权，也不伪造 GPS、打卡、照片、用户笔记等事实。

## 目标架构

```text
React Web / SwiftUI iOS
            │
          FastAPI
            │
       Agent Runtime
  goal · loop · context · approval
       │             │
 Vago Domain Tools   External Tools / MCP
       │
 Domain Services
 Travel · Footprint · Knowledge · Preferences · Memory
       │
 MySQL · Redis · Qdrant · Object Storage
```

- **Agent Runtime**：解释目标、取得任务相关上下文、选择工具、观察结果、检查约束、重规划、请求批准并完成响应。
- **Domain Services**：继续拥有业务规则、用户归属校验和持久化。Agent 不直接操作数据库。
- **Personal Travel Context**：不是单独数据库或固定 prompt；按任务组合长期偏好与历史、当前行程、实时观察、个人知识和必要外部信息。
- **External Tools / MCP**：仅是未来外部能力的接入边界；内部领域能力优先使用 Domain Tools，不将所有 FastAPI API MCP 化。

## 运行模型

```text
Goal → acquire context → select tool → observe
     → constraint check → propose / replan
     → approval when needed → domain action → verify
```

读取当前 Trip、日程、足迹、打卡、偏好或个人知识通常可自动执行。创建或修改 Trip、Itinerary、删除数据，以及未来的预订或支付，必须先形成结构化 proposal 并取得用户确认。外部信息、个人资料或检索不可用时，Agent 应说明缺口并降级，不得编造结果。

## Context 与工具边界

| Context 类型 | 首选来源 | 示例内部工具 |
| --- | --- | --- |
| Long-term | SQL / future Memory | `get_travel_history`、`get_user_preferences` |
| Current trip | Travel domain | `get_current_trip`、`get_today_itinerary` |
| Live travel | Footprint domain | `get_recent_footprint`、`get_checkins` |
| Personal knowledge | Direct Context / 按需 Qdrant | `search_personal_knowledge` |
| Write action | Travel domain | `propose_itinerary_update`、`apply_approved_itinerary_update` |

工具使用结构化输入输出，内部完成 user ownership 校验并隐藏 SQL。Qdrant 只用于非结构化个人资料的语义检索；结构化旅行事实通过领域服务和 MySQL 读取。必须区分 confirmed facts、generated narrative 与 learned preference signals，后者不能自动覆盖用户明确偏好。

## 分阶段开发

| 阶段 | 目标与最小交付 | 不做什么 |
| --- | --- | --- |
| Phase 9 | Grounded Travel Memory、历史旅行上下文、明确偏好与可审视 signal | 不把模型推断写成确认事实，不做复杂记忆系统 |
| Phase 10 | 最小 Runtime loop、内部 Domain Tools、context acquisition、审批 proposal、tool/constraint tracing 与测试 | 不直连数据库，不为了框架引入多 Agent 或图编排 |
| Phase 11 | Adaptive Day Planner：读取当前旅行状态、确定性约束检查、候选重规划、确认后日程更新与验证 | 不未经确认修改重要旅行状态 |
| Phase 12 | 只为已验证 workflow 接入 POI、路线、天气、日历、航班等外部能力 | 不为展示 MCP 创造工作流 |

## 技术与验证

- 后端保持 **FastAPI Modular Monolith**；Runtime、Domain Tools 与领域模块按清晰 Python 边界组织，不拆微服务。
- 复用现有 OpenAI SDK、LangChain、SSE、Pydantic、SQLAlchemy、MySQL 与 Redis。Agent framework 暂不绑定；简单 tool-calling loop 足够时不引入 Graph Runtime。
- 逐步记录 tool call、使用的 context、constraint result、approval event 和最终 outcome，作为调试与评估边界。
- 测试不只看回复文本：覆盖上下文是否正确、用户隔离、工具选择、约束违规后的重规划、写操作审批、事实 grounding 与外部信息失败回退。

## 完成标准

完成一个真实 workflow 时，应能证明：Agent 使用了正确的个人旅行上下文；通过领域工具而非 SQL 改变业务状态；确定性约束被检查；重要写入已获批准；操作后状态被再次验证。框架数量、MCP 数量或“自主性”不是完成标准。
