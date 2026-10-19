# Vago 文档索引

从这里查找文档。**当前规范**描述现行契约或长期边界；**目标设计**描述尚待实现的能力；**历史记录**仅用于追溯；**待决提案**不代表已批准的需求。文档中的阶段和状态可能落后于代码，涉及现行行为时须核对代码与验证结果。

## 产品与架构

| 文档 | 状态 | 用途 |
| --- | --- | --- |
| [PRD](prd/PRD.md) | 当前产品目标，含未来能力 | 产品定位、领域需求及目标状态；具体完成度须核对代码 |
| [架构说明](architecture.md) | 当前原则与目标设计 | 系统边界、数据流和 Agent 演进方向；阶段表不是实时进度 |
| [Agent Runtime 设计](modules/agent/agent-runtime.md) | 当前实现与目标设计 | Agent 工具、事件、上下文和后续工作，文内区分已实现与目标 |
| [登录与身份认证设计](modules/authentication/README.md) | 当前实现设计 | 手机号与 OAuth 登录、JWT 会话、客户端凭据保存和用户身份校验 |

## 开发参考

| 文档 | 状态 | 用途 |
| --- | --- | --- |
| [API 索引](API/README.md) | 当前规范 | FastAPI 当前路由入口及各领域契约；字段细节以 schema / OpenAPI 为准 |
| [数据库使用说明](database/README.md) | 当前规范 | 区分全新数据库 DDL 与已有数据库的 Alembic 迁移；勿在有数据的库运行清表脚本 |
| [iOS 足迹模块](modules/footprint/ios/README.md) | 当前规范与待验收项 | 地图设计、足迹渲染与后续验收入口 |
| [足迹测试数据工具](modules/footprint/test-data-tool.md) | 已实现 CLI，含目标设计 | 本地测试场景和清理方式；地图编辑器仍是提案 |

## 历史与提案

| 文档 | 状态 | 用途 |
| --- | --- | --- |
| [版本记录](CHANGELOG.md) | 历史记录 | 已记载版本的变更；不能代替当前代码状态 |
| [迁移盘点](evolution/remould-migration-inventory.md) | 历史记录 | 早期 Java 至 FastAPI 迁移过程；不作为当前架构说明 |
| [归档索引](archive/README.md) | 历史记录 | 旧数据库草案、迁移期 API 与足迹文档完整快照 |

根目录 [AGENTS.md](../AGENTS.md) 是仓库默认工作边界。具体产品和 Agent 架构决策另参考 [vago-project-skill](../.agents/skills/remould-skill/SKILL.md)。未纳入索引的工作草案应先确认状态，再决定是否成为正式文档。
