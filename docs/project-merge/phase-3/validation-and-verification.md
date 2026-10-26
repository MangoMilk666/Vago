# 阶段 3：候选时间线与确定性约束校验

> 2026-10-26。Vago 候选仍与正式 Plan、Trip、足迹分离；本阶段没有用户确认或正式写入接口。

## 合并的能力

- 沿用 wkf `build_itinerary` 的时间线计算原则：以每日地点顺序、停留时间、相邻路线耗时和缓冲时间检查固定开始时刻与冲突，不自动挪动预约。原始候选正文保留；计算只产生校验报告。
- 借鉴 wkf `ItinerarySnapshot` 与 `check_constraints` 的三态结果：`pass`、`fail`、`unverifiable`。适配其 `snapshot.days` 及 `points/routes` 内容，并结合 Vago 的 `brief`、会话归属与 MySQL `PlanProposal` 保存逐项结果。
- 检查连续日序、当地日历日与旅行日期、时区和跨午夜显式日期、地点 ID/相邻路线、住宿城市、已知预算与缺失价格、旅行结束时间、交通上限、城市覆盖、景点数量、禁忌及标签。wkf Snapshot 的价格按其既有 CNY 契约解释；普通 Vago 候选必须明确提供价格币种。

## 当前候选输入与结果

`brief` 使用 `startDate`、`endDate`、`timezone`、`partySize`、`budgetCurrency`、`hardConstraints[]`。每条硬约束含 `type` 和 `value`，标签规则另含 `scope`，指定日期的规则可含 `day`。`content.days[]` 含 `day`、`date`、可选 `timezone`、有序 `items[]` 与相邻 `legs[]`；地点可含 `startTime`、`endTime`、跨午夜 `endDate`、`durationMinutes`、`price`、`currency`、`tags`、`sourceUrl`。路线可含端点 ID、`routeDurationMinutes`、`bufferMinutes`、`durationMinutes`、`provider`、`routeChoiceId`、带偏移量的 `queriedAt`。输入仍保留阶段 2 的原始 JSON，缺字段会产生 `unverifiable` 或明确的结构错误，不补造来源或价格。

创建候选后，服务端保存 `validation_result` 与 `validated_at`。详情和状态接口返回 `validation`：`scope`、总体 `outcome`、`hardChecksPassed`、逐项 `checks` 和信息缺口。未通过的硬约束，包括 `unverifiable`，状态为 `BLOCKED`；通过当前确定性检查时状态为 `VALIDATED`。历史未校验版本保持 `PENDING_VALIDATION`，可由所属用户调用 `POST /api/v1/agent/conversations/{conversation_uuid}/proposals/versions/{version}/validate` 重新校验。该操作只更新报告与状态，不改候选正文；另一个用户不能调用。后续阶段 7 正式写入前仍须重新校验选中版本及目标草稿状态，不能依据旧报告直接保存。

`VALIDATED` 仅表示**当前输入的确定性一致性检查通过**，不表示地点、路线、价格已由外部 provider 核实，更不是可直接确认的正式 Plan。当前 Vago 尚无受控路线目录，客户端传来的 `provider`/`routeChoiceId` 不能作为真实路线证据；包含路线的候选会保留阻断性的 `route_provenance=unverifiable`，阶段 4 完成 provider 适配后再补验证。缺来源的地点以醒目警告记录；若用户明确要求报告信息缺口，未说明的无来源地点由硬约束阻断。未知硬约束也不能默认为通过。

## 验证与迁移

迁移 `20261026_02_add_proposal_validation.py` 在 `plan_proposals` 增加两个可空字段，既有版本保持可回读。已在本机 MySQL 执行 `alembic upgrade head`；降回 `20261026_01` 会删除校验报告，应先备份。`docs/database/db_schema.sql` 已同步。

纯函数和 API 验证覆盖多日、两种当地时区、跨午夜、固定开始时间冲突、路线缺失/逆序、预算超限/缺价、禁忌和未知硬约束；SQLite 迁移升降级通过。本机 MySQL 测试使用专用测试账号跨 Session 回读并重算报告，随后清理测试会话，不影响阶段 2A 导入的历史数据。
