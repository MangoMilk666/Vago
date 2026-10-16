# 阶段 1：测试账号、溯源与验收

> 2026-10-16，本机 `vago` MySQL。仅新增专用空账号；没有导入 wkf 历史数据或改变业务 API。

## 已指定的测试账号

| 项 | 当前值 |
| --- | --- |
| `users.uuid` | `5519a1d427b249ed90e5fd9851224125` |
| 昵称 | `wkf-merge-test` |
| 登录标识 | 无手机号、邮箱和 OAuth 绑定；只供受控数据导入与服务端验收，不是可直接用短信登录的账号 |
| 初始内容 | 创建后只读核对：Plan 0、Trip 0、AgentConversation 0、TravelFootprint 0；已建默认 UserSettings |

账号是 Vago 数据库中的用户，不是数据库 `root` 用户。数据库管理员只用于本地核查/建号；任何应用读取仍以 JWT 中的用户 UUID 做 owner 校验。不得把 wkf 原始 PII、位置数据或访问凭证写进仓库。阶段 2A 导入前重新检查此账号仍专用且为空/仅含可核对的测试批次。

## 旧到新 ID 溯源契约（阶段 2/2A 实施）

| 来源键 | 目标与规则 |
| --- | --- |
| `source_system=wkf`, 环境/快照、原文件或数据表、SHA-256、导入批次 | 保留不可变来源与重复执行依据；文件哈希不能替代逐条内容/复合键去重。 |
| `legacy_chat_id`, `legacy_user_id`, `legacy_group_id` | 映射到测试账号 `user_uuid` 和新 `conversation_uuid`；旧身份仅作审计/追溯。一个旧会话允许多候选版本，不以 group 覆盖会话隔离。 |
| graph `TripPlan.uuid`, snapshot scope/revision/artifact_id, PostgreSQL `id/version` | 分别保存原始 ID 与原始版本；Vago 候选生成新 `proposal_uuid` 与自身版本。来源版本不能直接当 Vago 新版本号。 |
| 新 `message_uuid` / `proposal_uuid` / 未来 `plan_uuid` | 服务端生成并绑定 `user_uuid`；导入映射以来源系统+来源记录类型+稳定原始 ID（或文件哈希+行号）唯一，重复批次不得重复创建。 |

导入时按 role 分流：可呈现的 user/assistant 消息进入 AgentMessage；tool/system/内部域会话记录不冒充用户对话，进入可审计差异/来源区；13 个 snapshot candidate 不自动宣称是已确认的正式 Plan。PostgreSQL 当前 `itinerary_results` 为 0 行，因此尚无旧结果版本可映射。Neo4j 投影继续隔离，阶段 2A 才处理，不能自动成为用户事实。

## 固定验收样例

参见 [cases.json](cases.json)。三例均为虚构数据，仅用于契约与测试，不对应真实用户或路线：

1. `new_plan`：wkf 表单 + 两天地点候选 → 新草稿 Plan；预算范围、出发地、地点时钟及外部引用仍在候选；未确认时正式库不变。
2. `edit_draft_plan`：目标属于测试账号且未转换 → 展示旧/新日程差异；确认前后再次比较 `updated_at`，并发变更或状态改为 converted 必须拒绝。
3. `existing_trip`：既有 Trip → 仅以 owner 校验后读取日程作上下文；不触发正式更新，亦不将路线写成足迹。

本阶段验收分两层：**契约层**校对字段、日期和损失清单；**实现层**在阶段 2/7 的每个列表、详情、版本、确认入口测试 A=测试账号、B=另一用户。A 可读自己的候选，B 访问相同 ID 必须拒绝或返回不可见；客户端自填 `user_id/group_id` 不改变结果。当前未建立这些入口，不能声称双用户端到端验收已完成。现有旅行和会话 owner 测试可作为基线，但不代替新增候选 API 的隔离测试。

本轮已执行：`cases.json` JSON 解析通过，两个 `wkf_form` 经 wkf `TripPlanRequest` 校验通过；Vago `test_travel_service.py` 与 `test_agent_conversations_service.py` 共 12 个测试通过（另有 1 个依赖弃用警告）。`existing_trip` 为合成的只读边界样例，不是向空测试账号写入了真实 Trip；正式候选和跨用户 API 验收仍待后续阶段。
