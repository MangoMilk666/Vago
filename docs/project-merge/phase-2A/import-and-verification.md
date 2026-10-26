# 阶段 2A：wkf 历史数据导入

> 2026-10-26，本机目标批次 `20261026-03`，最终来源备份 `20261026-04`，仅归属专用 Vago 测试账号 `5519a1d427b249ed90e5fd9851224125`。历史资料是测试资料，不作为真实旅行事实参与规划。

## 来源与去向

| 来源 | 本次导出 | 目标与实际核数 |
| --- | ---: | --- |
| 主 JSONL 会话 | 1 文件、25 行（含元数据） | 1 个 `AgentConversation`；10 条有正文且没有工具调用的用户/助手消息进入 `AgentMessage`；其余 15 行只进入 `wkf_import_records`。 |
| 领域快照 | 3 文件、39 条内部消息、13 个资源候选 | 3 份快照、39 条内部消息和 13 个资源候选均进入 `wkf_import_records`，未伪装成用户消息或规划版本。 |
| PostgreSQL `itinerary_results` | **0 行** | 导出为空数组；没有历史行程候选可导入，也没有创建虚构候选。 |
| Neo4j | 11 节点、5 关系 | 同库复制为仅带 `WkfMergeTest` 标签和 `WKF_MERGE_REL` 关系的隔离测试图，并标记 Vago 测试账号、来源 element ID 与批次；原节点/关系保持原状。副本不接入 Vago Agent。 |

原始会话哈希与阶段 0 相同：`24d5f5a395f03631500c7121b66835834da19195640c497e12ad94d0b29358e6`。最终图导出 SHA-256：`004939a704a2e48822f85e2eb75da7ccd655b999ae9dc54668197521e0270334`；空 PostgreSQL 导出 SHA-256：`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`。原始文件、导出 JSON 和来源哈希清单保存在 `services/vago-ai/data/wkf-merge-private/20261026-04/`，该目录被 Git 忽略并限制文件权限。`20261026-01`、`20261026-02` 是连接失败时产生的不完整目录，**不能用作导入备份**；`20261026-03` 是首次成功导出，最终导入与图恢复统一使用带完整哈希及 Neo4j 属性类型信息的 `20261026-04`。

## 导入契约

- `20261026_01` Alembic migration 建立 `wkf_import_records`：保存来源键、内容哈希、原记录、目标 UUID 与导入批次。独立来源键使重复执行不产生重复目标；相同来源键内容变化立即报错。
- Vago 会话和规划候选继续由现有 MySQL 表存储。旧 `chat_id` 只作为映射；`user_uuid` 由导入命令固定为测试账号。历史 PostgreSQL 候选若以后出现，以 `PENDING_VALIDATION` 保存完整旧 payload、warnings、旧 ID/版本；旧 `plan_uuid` 不直接当 Vago Plan UUID。
- 领域快照中的 `candidate` 是地点/住宿等资源候选，不是完整 `PlanProposal`；13 个均保留原类型与内容。图记忆副本只由带 `WkfMergeTest` 标签的受控查询读取，不能作为通用生产记忆；原始标签和关系类型分别保存在 `wkf_labels`、`wkf_type`。
- 备份在被忽略的工作区目录，未提供独立于本机的灾难恢复副本。需要跨机器恢复时，应将整个私有目录移入受控备份设施，不能提交 Git。

## 已验证

1. 导出、MySQL 导入和 Neo4j 副本均成功；逐条审计确认来源核数：1 个会话映射、25 行主会话、3 份快照、39 条内部消息、13 个资源候选；目标核数：1 个会话、10 条消息。目标归属与另一个现有账号隔离。
2. 重复运行 MySQL 导入和 Neo4j 复制，目标数量保持不变。使用 `audit_wkf_history --rollback` 撤回 MySQL 批次，再从私有备份恢复；Neo4j 副本也实际撤回，并仅凭备份文件恢复到 11 节点、5 关系，逐节点和逐关系属性与备份一致。原始来源未改动。
3. 相关会话、候选 API 与 migration 测试：`7 passed`；`git diff --check` 通过。没有把图副本连接到生产 Agent，也没有执行 Web/iOS 历史展示验收。

## 运行与撤回

在 `services/vago-ai` 下，先执行 `.venv/bin/alembic upgrade head`。导出使用 wkf 的 Python 环境运行 `app/devtools/export_wkf_history.py`，指定 `--source-root` 和**全新**的 `--backup-dir`；导入使用 Vago 的 Python 环境运行 `-m app.devtools.import_wkf_history`，指定备份目录、测试账号 UUID 和批次 ID。`-m app.devtools.audit_wkf_history` 可核数，加 `--rollback` 仅撤回 MySQL 目标和溯源记录。图副本使用 wkf 的 Python 环境运行 `app/devtools/copy_wkf_graph.py`，传相同批次、账号和备份目录；加 `--rollback` 仅删除对应测试图副本。两个库的撤回分别执行，随后再做数量核对。

如果需要撤销 schema，先撤回导入数据、备份 `wkf_import_records`，再降到 Alembic `20261016_01`；直接降级会删除溯源表。
