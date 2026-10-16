# 阶段 2：候选版本持久化与查询

> 2026-10-16 已实现 FastAPI/MySQL 最小路径。候选仍不是正式 Plan/Trip；本阶段不运行 wkf 导入、约束校验或用户确认。

## 当前契约

- `POST /api/v1/agent/conversations/{conversation_uuid}/proposals`：JWT 所属会话下创建候选。请求字段：`idempotencyKey`（8–128 字符）、`targetKind`（`new_plan` / `draft_plan`）、仅编辑草稿时提供的 `targetPlanUuid`、`brief` 与 `content` 两个 JSON 对象。二者完整存储且可回读；当前不把任意 JSON 误称为已校验旅行日程，单次内容上限 256 KiB。
- `GET .../proposals`：按版本倒序列出摘要。`GET .../proposals/versions/{version}`：读完整候选。`GET .../proposals/versions/{version}/status`：单独读持久化状态。响应沿用 Vago `ApiResponse` envelope。
- 服务端生成 `uuid`、会话内版本号与 `PENDING_VALIDATION` 状态；不接受请求体中的 `user_uuid`、旧 wkf `group_id` 作授权。编辑目标必须是当前用户未删除、`status=0` 且未转换的 Plan。所有入口先检查会话归属，版本读取再检查候选归属。
- 同一会话、同一幂等键且内容相同返回原候选；键相同而内容不同返回 409。MySQL `SELECT ... FOR UPDATE` 锁住会话行来分配版本，唯一约束兜底并发。删除会话会一起删除尚未确认的候选；不删除正式旅行数据。
- `brief` 和 `content` 是有界但暂未做旅行语义校验的 JSON。阶段 3 才固定时间线/硬约束结构并保存校验结果；阶段 4 才核实 provider 坐标/许可；阶段 7 才允许确认写入。`targetPlanUpdatedAt` 是创建时快照，**不足以独自证明每日安排未被并发修改**，阶段 7 还要复核完整目标差异。
- `source_system/source_ref` 为后续阶段 2A 的内部溯源留位；公开创建接口固定 `vago`，本轮没有 wkf 历史导入或原 ID 查询 API。

## 迁移与验证

- 新迁移：`20261016_01_create_plan_proposals.py`，接在 `20261015_01` 后。升：`cd services/vago-ai && .venv/bin/alembic upgrade head`；降（**会删除候选数据，应先备份**）：`.venv/bin/alembic downgrade 20261015_01`。`docs/database/db_schema.sql` 已同步新建库脚本。
- 本机 MySQL 已升级至 `20261016_01 (head)`。`caching_sha2_password` 登录所需 `cryptography==43.0.0` 已列入后端 requirements。
- SQLite 隔离迁移升降级、HTTP 双用户归属/幂等/草稿目标测试均通过。显式运行 `VAGO_MERGE_MYSQL_TEST=1 .venv/bin/python -m pytest tests/test_plan_proposals_mysql.py -q`：专用账号写入固定样例，跨 Session 回读，同键重试、两个独立连接并发版本及跨用户拒绝均通过；测试完成删除本次会话和候选，核对两表该账号计数均为 0。
- 当前未提供前端入口、Agent 自动生成候选、确认写入或历史数据迁移；测试账号不能通过短信登录。阶段 2A/3/7 依次处理来源导入、校验、正式确认，不把本阶段状态当作完成闭环。
- 全量后端测试本机结果：109 passed、1 skipped、2 failed。失败分别来自旧测试对“明天”的固定日期 `2026-10-07` 与当前系统日期不符，以及本机 `.env` 的 `EMBEDDING_MODEL` 覆盖了旧变量兼容测试；均不在本轮候选模块调用链内。本轮相关测试另行通过，不将全量套件描述为全绿。
