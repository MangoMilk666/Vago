# Vago 仓库工作指引

本文件适用于整个仓库。先理解用户本次要求，查阅与任务直接相关的代码和文档；不要为了遵循本文件而扩大修改范围。用户在当前任务中的明确要求优先。

## 项目定位

Vago（叠迹）是面向个人旅行的 **AI-native Personal Travel Intelligence / Personal Travel Agent System**。产品持续积累用户自己的计划、行程、旅行观察、知识与回忆，按任务组合为 **Personal Travel Context**，服务于旅行前规划、旅行中协调和旅行后回顾。用户保有意图和重要决定权；Vago 负责收集相关上下文、协调信息、检查约束并提出建议。公共社区、通用聊天和一次性生成行程不是核心定位。

Personal Travel Context 是按任务组合的状态视图，不是单一数据库、固定 prompt 或 RAG 的别名。结构化旅行事实通过领域服务读取；用户明确选择的少量资料可直接提供；语义检索按需用于非结构化个人知识。

## 必须守住的边界

- **事实与派生内容分离**：GPS、打卡、用户笔记等观察事实，不得被 AI 伪造或覆盖。轨迹、回忆叙事和偏好信号属于派生结果，应保留来源与不确定性；推断出的偏好不能自动替代用户确认的偏好。
- **用户控制重要操作**：读取和观察通常可以自主执行。Agent 修改重要持久化旅行状态，或执行会产生外部影响的操作前，应按该操作的风险取得用户确认。不要把尚未实现的审批能力描述为现有功能。
- **隐私与归属**：个人旅行和位置数据按用户隔离。服务端根据已认证用户校验 ownership，不依赖客户端提供的 `user_uuid` 授权；检索和本地缓存也应保持用户隔离，避免记录原始 GPS 到普通日志。
- **领域规则归领域服务**：Agent Runtime 负责任务协调、上下文获取、工具调用、观察与约束检查；领域服务负责授权、业务规则和持久化。Agent 通过有明确输入输出的内部 Domain Tools 使用领域能力，不绕过服务直接操作数据库。
- **架构按真实需求演进**：当前工程以 FastAPI 模块化单体、React Web 和原生 SwiftUI iOS 为基础。不要仅为展示技术而引入微服务、多 Agent、MCP、工作流框架或新的基础设施；需要外部能力时再评估 API、SDK 或 MCP。Web 与 iOS 按各自使用场景设计，不机械复制界面或流程。

## 判断当前状态与实施修改

- 区分**已实现、进行中、目标能力**。代码是当前行为的证据，PRD 和设计文档说明需求与目标；两者不一致时，先查明差异，不把规划当成实现，也不以当前实现自动否定明确需求。
- 修改前检查相关调用方、数据归属与兼容性；尽量做范围明确、可验证的改动。修改 API、数据模型、Agent Tool 或写操作时，分别检查调用方、数据迁移、领域边界和确认要求。运行与改动相关的验证，并更新真正受影响的文档。
- 保留现有可用功能和用户未提交的改动。大型替换应先建立新路径并验证，再切换调用方和清理旧实现。

## 文档入口

- 项目概览：[README.md](README.md)
- 产品需求与目标：[docs/prd/PRD.md](docs/prd/PRD.md)
- 当前与目标架构：[docs/architecture.md](docs/architecture.md)
- 模块设计：[docs/modules/](docs/modules/)
- 历史迁移盘点：[docs/evolution/remould-migration-inventory.md](docs/evolution/remould-migration-inventory.md)
- 长期产品与 Agent 架构决策：[vago-project-skill](.agents/skills/remould-skill/SKILL.md)
- 实际修改代码时遵循的编码规范：[vago-coding-skill](.agents/skills/coding-skill/SKILL.md)

只阅读本次任务需要的材料。以上文档可能落后于代码，涉及当前行为时以实际代码和验证结果为准；涉及产品取舍时结合用户要求与产品文档判断。
