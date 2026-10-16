# 阶段 0：基线与复用边界

> 记录于 2026-10-16。只读盘点本机 Postgres.app 与 Neo4j Desktop 的原生数据库；未导入历史数据、未部署 wkf API。后续重新核数时应记录数据源、时间及导出批次。

## 代码与验证

| 项目 | 锁定的 HEAD | 工作区与命令 | 本次结果 |
| --- | --- | --- | --- |
| Vago | `17e5016783feb28e4663d44db8ce274566649621` | 原有 `project-merge-advice.md` 已修改、`Project-Merge-Progress.md` 未跟踪；本轮保留。后端：在 `services/vago-ai` 执行 `.venv/bin/python -m pytest tests/test_travel_service.py tests/test_agent_runtime.py -q` | 21 passed；1 条依赖弃用警告 |
| Vago Web | 同上 | 在 `apps/vago-web` 执行 `npm run test:footprints` | 7 passed |
| Vago iOS | 同上 | `xcodebuild -quiet -project apps/vago-ios/VagoIOS.xcodeproj -scheme VagoIOS -destination 'platform=iOS Simulator,id=493CC6E4-5BED-4826-9ECE-7CB25242FCBA' -derivedDataPath /private/tmp/VagoMergeBaseline test CODE_SIGNING_ALLOWED=NO` | 11 passed；模拟器 iPhone 17 / iOS 26.5 |
| wkf | `35c458419552545950d403dfde05f848b062251b` | 工作区干净；在 wkf 根目录执行 `.venv/bin/python -m pytest tests/orchestration/test_checks.py tests/store/test_itinerary_store.py -q` | 70 passed；只读目录导致 pytest 缓存警告 |
| wkf Web | 同上 | 在 wkf `frontend` 执行 `npm test -- --run` | 21 passed；首次受目录写权限限制，允许 Vite 写临时文件后通过 |

以上是选定测试的基线，不代表双方端到端规划流程已验收。Vago iOS 与 wkf 当前测试在各自现有环境运行；未来改动应复测受影响路径。

## 历史数据源清单

| 来源 | 当前可核实数量与位置 | 迁移前备份、复核方式 |
| --- | --- | --- |
| wkf Web 会话 | `app/session/session-web-web-chat-1791889819313.jsonl`：1 文件、24 条消息（用户 6、助手 8、工具 10）及 1 条元数据；文件被 Git 忽略；SHA-256 `24d5f5a395f03631500c7121b66835834da19195640c497e12ad94d0b29358e6`。 | 迁移前复制到仓库外受控备份，记录哈希、文件数、消息数、旧 `chat_id` 与导入批次；不把原文或密钥提交到 Git。 |
| wkf 领域会话快照 | `app/domain-session/*.json`：3 文件、39 条内部消息（用户 5、助手 19、工具 15）、13 个 `candidate` 产物；schema version 均为 1，文件被 Git 忽略。 | 与主会话分别备份并按快照 scope、revision、artifact ID 建映射；仅可回读的候选进入候选区，内部消息不可直接伪装成用户聊天。 |
| wkf 其他本地会话 | 本地未发现其他 `session-*.jsonl` 或旧 `app/subagent-session/`；`tests/fixtures/` 是测试夹具，`out/` 是评测输出，`app/cron/action.jsonl` 是定时任务状态，均不计入真实聊天。 | 导入前对原始环境重新枚举主会话与域会话，按角色及来源分类；不可映射内容列差异清单。 |
| PostgreSQL 候选 | 已连接 wkf `.env` 指向的 Postgres.app 原生 `travel_memory` 库。`public.itinerary_results` 表存在，**0 行、0 个 chat_id**；无历史候选版本可从该表导入。 | 本机当前源表为空，无需为候选数据生成迁移批次。2A 导入前再只读核数；若新增数据，先做 `pg_dump` 并验证备份可恢复。 |
| Neo4j 记忆 | 已连接 wkf `.env` 指向的 Neo4j Desktop 原生 `neo4j` 库。**11 节点**：Episode 4、IngestJob 4、TripPlan 1、SessionRef 1、PreferenceProfile 1；**5 条 USES_PLAN 关系**；`group_id` 共 1 个。当前未见 Entity 或 RELATES_TO。 | 迁移前在受控位置导出并试恢复该库，保留原 group/UUID 与来源；区分记忆事实、计划/偏好投影和队列状态，不能把 11 个节点全当作可展示的记忆。2A 导入前逐类重核数量。 |

两个数据库均由本机原生应用运行，不依赖 wkf Docker 容器/数据卷。wkf 当前 `.env` 的 PostgreSQL 目标为 `127.0.0.1:5432`；启动文档中的 `55432` 是 Docker 示例映射，盘点以实际连接的本机库为准。上表是当前时间点快照，D02 正式导入前需重新核数。

## 授权和第三方边界

- D01：用户确认 wkf 作者授权通过副本合并。wkf 根目录无 `LICENSE`/`NOTICE`；代码复制时保留来源提交、文件与作者署名要求，需取得可归档的授权说明。此授权不覆盖第三方数据与素材。
- wkf 前端 lockfile 中核对的直接依赖：`@amap/amap-jsapi-loader`、React、React Query、React Markdown、remark-gfm、Zustand 标为 MIT，lucide-react 标为 ISC。依赖包许可不同于高德在线地图/地点数据许可；Python `requirements.txt` 使用范围版本，移植依赖前需按锁定版本复核许可证。
- 当前 wkf 前端没有仓库内图片/字体资产；`ItineraryPanel.tsx` 使用 4 个远程 Unsplash 兜底图片 URL。图片本身与 API 使用条款分别核对；阶段 0 样例不引用图片。[Unsplash 图片许可说明](https://help.unsplash.com/en/articles/2612337-do-i-have-to-give-credit-to-a-contributor-when-i-use-their-image)、[API 署名指引](https://help.unsplash.com/en/articles/2511315-guideline-attribution)。
- wkf 使用高德 JS 与 REST 地点/路线服务，且有本地路线候选缓存。按[高德开放平台服务协议](https://lbs.amap.com/pages/terms/)核对账户授权、展示和缓存/存储边界；在阶段 4 接 provider 之前，须确认适用许可允许目标用法，尤其是跨底图展示或长期保存服务数据。当前不能把 wkf 的缓存逻辑直接当作可复用契约。

## 可重现的规划样例

[合成样例](phase-0-planning-sample.json)只包含虚构“示例城”和虚构地点，不含坐标、用户数据、密钥或真实 provider 结果。它对应 wkf 的 `ItinerarySnapshot` 与 `Constraint` 契约，供阶段 1/3 对照适配。三个确定性硬约束预期均为 `pass`；把晚餐结束时间改为 `20:30` 时，`day_end_before` 应为 `fail`。样例的 `example.invalid` 仅是占位来源，**不得**作为真实来源证据或进入正式确认流程。

在 wkf 根目录执行以下只读校验，可重现样例结果：

```bash
.venv/bin/python -c 'import json; from pathlib import Path; from app.core.type.itinerary_snapshot import ItinerarySnapshot; from app.core.type.violation import Constraint; from app.agents.orchestration.checks import check_constraints; p=json.loads(Path("../Vago/docs/project-merge/phase-0-planning-sample.json").read_text()); s=ItinerarySnapshot.model_validate(p["snapshot"]); c=[Constraint.model_validate(x) for x in p["constraints"]]; actual={x.rule:x.status for x in check_constraints(s,c)}; print(actual); assert actual==p["expected"]'
```

## 阶段 0 剩余核验

1. Neo4j 当前有数据；在阶段 2A 实际复制前完成受控备份与恢复验证，并重新核数。确认本机以外是否还有会话或领域快照。
2. 在阶段 4 复用高德数据/缓存前确认实际账号许可和署名/展示要求；复制任何具体第三方素材前逐项核对来源。
3. 保留本文件的 HEAD、命令、结果及源文件哈希，后续数据源变化须追加新盘点记录，不覆盖本次事实。
