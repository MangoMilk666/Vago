# 阶段 1：身份与旅行领域映射契约

> 2026-10-16 核对。依据 wkf `app/core/type/{trip_plan,map,itinerary_result}.py`、`app/mem/models.py` 和 Vago `app/travel/{models,schemas,service}.py`。本文是阶段 2/7 的实现输入，**不是已上线的 API 或迁移结果**。

## 归属与对象边界

- Vago JWT 解析出的 `user_uuid` 是唯一授权主体。wkf `user_id`、`chat_id`、`group_id`、`TripPlan.uuid` 仅用于来源追溯；wkf 允许缺省用户进入共享组，不能映射为 Vago 账号权限。
- wkf 表单 `TripPlan` 是规划输入，不等于 Vago 正式草稿 `Plan`，更不等于 `Trip`。wkf `ItineraryRecord` 是会话下的不可变候选版本；阶段 2 才建立 Vago `PlanProposal`，阶段 7 由用户确认后写正式 Plan。
- `TravelMapPoint` 是拟去的地点，不是已到访足迹；路线、polyline 和预测时间绝不写入 `travel_footprints`。
- 字段处置：**直映**可经校验写正式模型；**转换**须记录规则和原值；**候选保留**不能在阶段 1/7 静默丢弃；**缺口**需在正式写入前提供明确处理或提示用户。

## 表单和计划

| wkf 字段 | Vago 对应与处置 | 条件 / 缺口 |
| --- | --- | --- |
| `chat_id`, `user_id`, graph `group_id`, `uuid` | 来源映射，候选保留 | 由 JWT 归属测试账号；旧值仅可追溯，不能作 owner 或目标 Plan UUID。 |
| `origin` | PlanningBrief / 候选保留 | Vago Plan 无出发地专列；不能假装是 `destination`。 |
| `cities[]`（有序） | `Plan.destination` 可用面向用户的摘要；原数组候选保留 | 单字符串无法无损保存城市顺序；确认时展示摘要与原数组，不能把摘要回解析成原数据。 |
| `companions[{name,type}]`, `companion_uuids` | 候选保留 | Vago 无同行人表；图节点 UUID 不可直接作为 Vago 账号或人 ID。隐私数据不进普通日志。 |
| `start_date`, `end_date` | 直映 `Plan.start_date/end_date`（含末日） | wkf 表单为当地日历日；wkf 图存 UTC 半开区间，读图须先按 `tz_name` 转当地日，再将独占末日减一天；严禁直接取 UTC `.date()`。确认时还需 `start <= end`。 |
| `budget_min`, `budget_max` | 候选保留；用户明确选择总预算后转换为 `Plan.budget` | wkf 两端为整趟 CNY 范围，Vago 只有单个 Decimal(10,2)。不可自动取均值或上限；下限大于上限为无效输入。 |
| `budget_tier`, `budget_description` | 候选保留 | 档位/描述不等于金额，也不写入用户明确偏好。 |
| 预算币种 | wkf 固定 CNY，候选标明 `CNY`；正式 `Plan.budget_currency` | 不因 Vago 默认 CNY 就忽略来源币种；其他 provider 的价格必须带币种，未知币种不得合计。 |
| `purpose` | PlanningBrief / 候选保留 | Vago Plan 无用途专列；不能覆盖用户确认偏好。 |
| wkf plan label | 可供新建 Plan 标题建议 | 用户确认标题；编辑时保留原 Plan 标题，除非用户明确同意改名。 |

## 日期、每日项目和地图资源

| wkf 字段 | Vago 对应与处置 | 条件 / 缺口 |
| --- | --- | --- |
| `TravelDayInput.day`, `TravelMapPoint.day`, `TravelRoute.day` | 转换为 `ItineraryDay.day_index` 和 `day_date` | 仅对明确起始日计算：`start_date + (day-1)`；检查 1-based、连续范围及同一天唯一性。wkf 结果仅有 `city` 时不能凭空推断日期。 |
| `TravelDayInput.startTime`, point `startTime/endTime` | 候选保留 | Vago Day/Spot 没有时钟字段；校验时按地点时区解释，跨午夜不能仅比较 HH:mm。不可塞入 `duration_minutes`。 |
| point `id`, `placeRef` | 候选内部 ID / provider 引用 | 正式 `ItinerarySpot.uuid` 由 Vago 生成；外部 ID 要连同 provider、查询时间、坐标系保留。 |
| point `name`, `address`, `durationMinutes`, `note` | 直映 `ItinerarySpot.name/address/duration_minutes/notes` | 校验 Vago 字段长度与非负时长；超长不得截断。 |
| point `type` | 转换 `ItinerarySpot.category` | hotel/airport/station 等只能按明确字典映射到 0–5，未知类型归“其他”前须仍保留原类型；酒店亦可在用户确认后进入 Day accommodation。 |
| point 列表顺序 | `ItinerarySpot.sort_order` | 按选中候选的每日顺序生成，不用旧 point ID 排序。 |
| point `lng/lat`, `source`, `confidence` | 候选资源保留 | Vago Spot 无坐标/质量/来源字段；高德来源通常涉及 GCJ-02，但 wkf payload 没有显式坐标系，需 provider 证据核实后转换；不能将候选坐标写成 WGS-84 事实。 |
| point `imageUrl(s)`, `guideSummary`, `guideTips` | 候选保留或后续资源引用 | Vago Spot 无同义字段；外部图片与摘要须保留来源、许可和失效信息，不默认永久存储。 |
| `PlaceInput.bufferMinutes`, `routeSelectionReason`, `transportFromPrevious`, `transportDurationMinutes`, `routeChoiceFromPrevious` | 候选时间线/路线选择保留 | `ItineraryDay.transportation` 是文字，不足以无损装载逐段交通及缓冲。 |
| route `id/mode/pointIds`, `durationMinutes/distanceMeters` | 候选路线保留 | 无正式路线实体；只在选中候选中引用对应地点，断链 ID 必须报错。 |
| route/segment `polyline`, segment `fromPointId/toPointId`, `startTime/endTime`, `routeDurationMinutes/bufferMinutes`, `selectionReason`, `queriedAt`, `routeChoiceId`, `routeSummary`, `durationMinutes/distanceMeters`, `steps[]` | 候选路线保留 | 确认前按时区、地点顺序、provider 来源、查询时效与币种校验；polyline 的坐标顺序/坐标系须核实，不能降格为足迹。 |
| `warnings`, 校验结果 | 候选版本保留 | 对明确硬约束 `fail` 或 `unverifiable` 按 D04 阻止正式写入；软性未知醒目展示。 |
| `ItineraryRecord.id/chat_id/version/city/plan_uuid/created_at` | 来源 ID、候选版本和创建时间 | PostgreSQL `(chat_id,version)` 唯一，Vago 需按 owner + conversation/目标隔离版本；旧 `plan_uuid` 是 wkf graph UUID，不直接指向 Vago Plan。当前源表 0 行，阶段 2A 再核数。 |

## 三种目标路径

1. **新建 Plan**：候选关联当前 Vago conversation，`target_plan_uuid = null`。经约束检查和用户确认，调用领域服务创建 status=0 的 Plan 与日期对应的 ItineraryDay/Spot。阶段 1 不实际写入。
2. **编辑未转换草稿 Plan**：候选绑定已归属当前用户且 `status=0`、`converted_trip_uuid=null` 的 Plan；记录读取时 `updated_at` 或后续显式版本。确认时再次核对归属、状态、版本和日程差异；当前 `update_plan`/`update_itinerary_day` 没有完整的草稿状态和并发保护，阶段 7 必须补齐，不能直接复用为无条件确认命令。
3. **已有 Trip**：只读其状态、日期、现有日程作为候选上下文；阶段 1–7 不写已有 Trip。运行中 Trip 的剩余日程重规划及确认属于阶段 9，已结束 Trip 不得被改写。

不确定的时间、货币、地点/路线来源或无法落库的关键语义均应留在候选与差异清单中。若被用户指定为硬约束而证据不足，正式写入必须停止，不能通过注释、模型文本或用户确认绕过。
