# Vago 与 travel-assistance-wkf 合并评估及分阶段落地建议

> 更新于 2026-10-16。基于本地 Vago `8f71665`、travel-assistance-wkf（下称 wkf）`35c4584` 及当前工作区代码；未执行两项目端到端运行。本文区分代码已有能力、评测结果与合并目标。本文始终是合并实施的直接指导文件；[决策填写表](merge-decisions.md)仅收集需要用户选择的信息，填写后将确定的结论回写本文。

## 1. 总体决策

以 **Vago 产品、仓库、认证、领域服务、MySQL 正式旅行记录和 Web/iOS 客户端**为主干，按模块吸收 wkf 的规划计算、外部地点与路线查询、会话交互和 Agent 编排经验。先完成“**生成候选方案 → 展示依据与校验结果 → 用户确认 → 写入 Vago 正式 Plan/Itinerary**”的闭环；运行中 Trip 重规划、图记忆和领域 Agent 再分别验证。

不直接拼接两个对外 FastAPI、两套前端和多套业务真相源。wkf 的 `chat_id`、`user_id`、`group_id` 不能作为 Vago 授权依据；wkf `itinerary_results` 是会话候选版本的设计参照，不能直接当作 Vago 正式行程。**D01 已确认 wkf 作者完全授权通过副本合并**；具体署名要求、第三方资产和地图服务条款仍在阶段 0 核对。wkf 仓库根目录未见 `LICENSE`，不要据此推断第三方依赖也获得授权。

首期产品形态按用户意见确定：**Vago 的聊天输入和消息流保持主界面；Agent 答复引用可展开的地点、路线、地图和行程候选预览组件**。不照搬 wkf 三栏页面，也不让预览长期挤占输入区。Web 先完成规划与确认闭环，iOS 按旅行中使用场景接入。

## 2. 最新代码和证据对照

| 主题 | 当前事实 | 对合并顺序的影响 |
| --- | --- | --- |
| Vago 正式领域 | `services/vago-ai/app/travel/models.py` 已有 `Plan`、`Trip`、`ItineraryDay`、`ItinerarySpot`；`travel/service.py` 管理创建及日程修改。Agent 当前主要是有界、只读的领域工具与 SSE 事件，并未实现完整写操作审批。 | 候选方案须独立于正式 Plan/Trip，确认后才调用领域服务；不能把目标审批流程写成现状。 |
| Vago 对话 | MySQL `AgentConversation`/`AgentMessage` 按用户保存消息、来源、结构化计划和可回放的公开事件；Web `AiPlanPage.jsx` 已消费流式事件。 | 扩展现有会话和事件契约；候选卡片必须可在刷新后回读。 |
| Vago 足迹 | 2026-10-15 的迁移已统一为 `TravelFootprint` / `travel_footprints`，用 `footprint_type` 区分 `AUTO_GPS` 与 `MANUAL_CHECKIN`；新接口 `/trips/{trip_uuid}/footprints`，旧 `/observations` 为兼容别名。坐标事实按 WGS-84 保存。 | 规划路线不能写入足迹或作为已到访证据；足迹可通过只读领域工具提供旅行进度。 |
| wkf 对外 API | `app/api/routes/chat.py` 的 `user_id` 可由客户端提交且明确不是认证；缺省用户会进入共享记忆组。其他聊天/表单/结果入口也不具备 Vago 的账号归属边界。 | 不能原样暴露 wkf API；会话、候选、地图缓存和记忆访问都由 Vago JWT 派生 `user_uuid` 并校验对象归属。 |
| wkf 行程结果 | PostgreSQL `itinerary_results` 以 `(chat_id, version)` 保存不可变版本；`SubmitItineraryPlanTool` 的 `dryRun=true` 只计算，非 dry-run 会保存结果并发布事件。 | 借用“候选版本 + 先写后通知 + 可回读”；在 Vago 改为 MySQL 用户归属候选，Agent 提交不得直接写正式 Plan。 |
| wkf 校验 | `app/service/itinerary_timeline.py` 可计算路线、缓冲和时间冲突；`app/agents/orchestration/checks.py` 的常识/硬约束检查主要经 `evaluation.py` 的快照适配器用于评测。缺价格、标签或来源时可能返回 `unverifiable`。 | 先做数据适配和确定性校验服务，再接 Agent；不能把评测函数视作已有的生产保存关口。 |
| wkf Agent | `AgentLoop` 处理工具调用、澄清、取消与排队、域委派、白名单和会话压缩；`MessageBus` 负责进出站消息；`SubAgentManager` 管理子 Agent 的预算、超时与状态；`DomainAgent` 通过结构化输入输出执行域任务。`app/subagent/` 与 Agent Registry 支持用一个执行实现配合多个域配置扩展 Agent。 | 在阶段 5 确定 LangGraph Runtime 对应的控制能力、状态和 Agent 配置契约；阶段 11 再实现并评估域委派。复用能力与接口设计，不复制一套独立编排循环。 |
| Vago Agent 技术方向 | 当前 `requirements.txt` 固定 `langchain==0.2.5`、`langchain-openai==0.1.8`；`rag_chain.py` 使用 `AgentExecutor`，`llm.py` 使用 `ChatOpenAI`。 | 保留 LangChain 的模型、工具和消息集成；规划 Agent 编排迁移至 LangGraph。现有 `AgentExecutor` 作为迁移前实现，不作为目标编排基础。 |
| wkf Agent 评测 | `docs/travelplanner-eval/phase-t3-run1.md` 的同批 18 例里，single 最终通过 10/18、multi 4/18；multi 成本约为 single 两倍。报告也指出小样本和沙盒任务限制。 | 该结果不足以否定 Vago 的多 Agent 架构目标；它说明默认委派策略须在 Vago 任务上验证。阶段 5 建立单 Agent 基线，阶段 11 对照后按任务启用委派。 |
| wkf 长期记忆 | Neo4j 图记忆有实体、关系、时间、冲突与检索实现；`docs/mem/v0.2/README.md` 报告测试完成，但真 LLM 质量回归只跑一次，Q1/Q6 仍 MISS。没有与 Vago 当前上下文或 Qdrant 的同任务对照。 | 允许保留 Neo4j 作隔离试验，不宣称已优于 Vago；生产化由质量、隔离、删除、时延和成本决定。 |
| JSONL 与 MCP | wkf `SessionManager.save()` 使用 `open("w")` 重写整段 JSONL，并非追加日志；CLI `build_mcp_servers()` 在 `CLI_ENABLE_MCP` 未显式关闭时会配置 Playwright 与 Exa，并非默认空配置。 | MySQL 对话仍为生产真相源；可借鉴压缩/摘要。MCP 连接只可在显式开关、工具白名单、凭据和隐私审查后适配。 |

证据入口：Vago 的 [产品需求](../prd/PRD.md)、[架构](../architecture.md)、`services/vago-ai/app/agent_runtime/`、`services/vago-ai/app/agent_conversations/`、`services/vago-ai/app/footprints/`、`apps/vago-web/src/pages/AiPlanPage.jsx`；wkf 的 `app/api/`、`app/agents/`、`app/service/itinerary_timeline.py`、`app/tools/itinerary.py`、`app/store/itinerary_store.py`、`app/mem/`、`docs/travelplanner-eval/phase-t3-run1.md`、`docs/mem/v0.2/README.md`。代码路径均相对于各自仓库。

## 3. 对已提出个人意见的处理

| 意见 | 处理结论 |
| --- | --- |
| 两边后端类似，冲突以 Vago 优先 | 同意。Vago 的身份、领域模型、正式写入和客户端兼容性优先；wkf 的算法和控制流按接口改造，避免长期双后端。 |
| PostgreSQL 数据可并入 MySQL | D02 已选择将 wkf 历史聊天、候选和记忆全量迁给一个 Vago 测试账号。先盘点、备份和试导入，再按目标契约迁移；原 wkf 身份与来源 ID 保留为溯源字段，不作为 Vago 授权依据。PostgreSQL 不作为第二套正式业务库长期保留。 |
| Neo4j 先保留，未来讨论它与 Qdrant | 同意保留作实验性、可重建的个人记忆投影。Neo4j 侧重关系和时态事实；Qdrant 用于非结构化知识语义检索，两者不是等价替代。待同一任务对照后决定共存、收缩或弃用。 |
| wkf 多 Agent 设计可复用，Vago 保留 LangChain 并采用 LangGraph | 采纳为合并方向。Vago 建立支持子 Agent 和域 Agent 的 LangGraph Runtime；在阶段 5 固定控制能力、Agent 注册和通信契约，阶段 11 完成实际委派并根据 Vago 任务评测决定启用范围。LangChain 保留模型、工具和消息集成，现有 `AgentExecutor` 逐步迁出编排职责。 |
| 中国大陆与境外可用不同地图依赖 | 同意，规划数据通过 provider 适配层输出统一契约。高德可用于大陆候选；境外 provider 尚未选定，应按覆盖、授权、成本和质量决定。地图底图仍由 Web/iOS 现有组件承载。 |
| 可复用 wkf 的 MCP 连接代码思路 | 可作为未来受控外部工具适配方案。先用直接 provider API 完成路线闭环；MCP 需要时再接，且默认关闭不需要的连接。 |
| 不沿用三栏；聊天答复引用资源预览 | 采纳为目标交互。答复内引用有稳定 ID 的资源卡片，展开后可看详情/地图/候选版本；保持输入区宽度和消息可读性。 |
| JSONL 聊天存储是否更省 | 现有 wkf 实现每次保存全量重写，不能据此判断更高效。Vago MySQL 支持归属、索引、分页和事务，继续作为生产存储；若担心长会话成本，应实测读取、写入、压缩、备份和并发，再选摘要或归档。 |
| Vago 的 tooling 事件流可视化 | 延续已有公开 SSE 事件，增加阶段、工具名、状态、关联的 proposal/version/resource ID；进度是展示，持久化状态由可回读 API 保证，不暴露模型内部推理、密钥或原始 GPS。 |

## 4. 合并时固定的契约

1. **身份与隔离**：所有 `conversation_uuid`、候选版本、正式 Plan/Trip、地图缓存、图记忆均绑定服务端认证得到的 `user_uuid`；请求体不接收可决定归属的 wkf `user_id`。列表、详情、澄清、取消、事件重连、版本读取和确认写入分别校验归属。
2. **候选与正式记录**：`PlanningBrief` 表达当次目标、日期、人数、预算、硬约束和已确认偏好，不覆盖正式 Plan。`PlanProposal` 为不可变候选版本，含 `conversation_uuid`、可选目标 `plan_uuid`/`trip_uuid`、版本、状态、每日项目、路线选择、来源/查询时间、价格/币种/估算标识、警告、校验结果和创建时间。D03 首版支持新建 Plan 和修改尚未转换为 Trip 的草稿 Plan；进行中 Trip 修改仍属阶段 9。仅用户确认后的专用命令可调用 Vago Travel Service 持久化正式记录；更新草稿须比较提交时的目标版本/状态并展示差异，重复确认需幂等，源候选版本需可追溯。
3. **来源与坐标**：外部地点和路线保存 provider、外部 ID、查询时间、坐标系、时区及失效/估算标识。高德候选和 Vago WGS-84 足迹、MapKit/Leaflet 展示之间需明确转换与误差验证；任何计划路线不得进入 `travel_footprints`。地图源与路线源可以不同。
4. **约束与决策**：对日期/时区、停留与换乘时间、地点顺序、显式禁忌和可计算预算进行确定性检查。结果分 `pass`、`fail`、`unverifiable`：D04 已决定明确硬约束的 `fail` 或 `unverifiable` 一律阻止正式写入，先补证据或修正候选并重新校验；软性未知以醒目警告展示。用户确认不能替代硬约束通过，Agent 文本也不能覆盖校验结果。
5. **对话与事件**：沿用 Vago `AgentConversation`/`AgentMessage` 和公开 SSE 事件。事件携带会话/turn、trace、序号、阶段与关联资源 ID；工具执行、澄清、候选就绪、失败/取消、确认结果有明确状态。断线重连读取持久化会话、候选和确认状态，不依赖历史 SSE 重放。
6. **工具与记忆**：Agent 使用有 schema、超时、权限和成本预算的内部 Domain Tools 或受控外部适配器，不直接访问通用 SQL。Vago 结构化事实/明确偏好优先；Neo4j 若接入，仅作为按 `user_uuid` 隔离的可选投影，保留来源、确认状态、纠错和删除路径，推断内容不能改写 GPS/打卡或用户确认偏好。
7. **Agent 编排与多 Agent**：保留 LangChain 的模型、工具和消息集成，Agent 工作流使用 LangGraph；现有 `AgentExecutor` 作为迁移前实现。LangGraph Runtime 应支持 wkf AgentLoop 的澄清、恢复、取消、预算和工具白名单能力，并定义子 Agent / DomainAgent 的注册、结构化输入输出、工具范围、预算、超时、状态和报告契约。采用“一个执行实现配合多个受约束的 Agent 配置”的扩展方式。Agent 间任务状态与公开进度接入 Vago 现有 `AgentConversation` / `AgentMessage` 和 SSE 事件；消息总线只保留必要的进出站通信语义，不另设第二套编排和会话真相源。阶段 5 建立 Runtime 与契约，阶段 11 通过 Vago 任务对照启用域委派。

### 数据映射重点

| wkf 数据/能力 | Vago 目标 | 迁移规则 |
| --- | --- | --- |
| `chat_id`、JSONL session | `AgentConversation`/`AgentMessage` | D02 决定全量迁入一个专用 Vago 测试账号；保留旧 ID 与导入映射。内部工具调用等记录不得伪装成面向用户的消息，无法映射的记录列入迁移差异清单。新会话由 Vago 生成 ID。 |
| `TripPlan` 表单 | `PlanningBrief` 或 Plan 创建输入 | 用户需求与正式旅行记录分开；明确偏好不由表单抽取结果静默覆盖。 |
| `itinerary_results` 与 `submit_itinerary_plan` | MySQL `PlanProposal` 版本 | 历史结果全量迁入测试账号的候选区并保留原版本/来源；wkf “提交”改为候选提交，不直接创建 Vago Plan。 |
| `placeRef`、`routeChoiceId` | 外部地点/路线引用 | 与 provider、坐标系、查询时间和来源绑定；过期时重新查询，不以模型编造 ID 代替。 |
| Episode/Entity/Edge | 测试账号的隔离 Neo4j 记忆数据；生产仍为可选投影 | D02 的历史记忆须纳入全量迁移及数量核对，但只给测试账号使用；阶段 10 再验证是否接入产品上下文，不作为正式旅行事实的唯一来源。 |
| wkf Agent 配置与报告 | LangGraph Agent Registry / 受约束的 Agent 配置；结构化观察与资源引用 | 阶段 5 定义配置字段、可用工具和输入输出 schema；阶段 11 验证配置驱动的域 Agent。报告附完成状态、证据与未解决项，主 Agent 保留关键候选和约束。 |

## 5. 更细的分阶段落地顺序

每阶段单独可验收、可回退；编号表示依赖顺序，未通过门槛不把下一阶段标为完成。阶段 0–7 构成规划闭环，阶段 2A 专门处理 D02 的历史迁移；阶段 8–11 是扩展或独立试验。实现单元可再拆 PR，但一个 PR 不应同时改身份、全量编排、正式写入与双端 UI。

各阶段推进的进度和结果，需要及时记录在 [Merge Progress Record File](Project-Merge-Progress.md).

| 阶段 | 范围和交付 | 明确不纳入 | 合并/验收要求 | 指导信息文件(若需要) |
| --- | --- | --- | --- | --- |
| **0. 基线与复用边界** | 锁定双方提交与测试命令；核对已获 wkf 作者授权的范围、第三方许可与署名要求；盘点 D02 全量迁移所涉 JSONL 会话、PostgreSQL 候选和 Neo4j 记忆的实际数量、来源及备份方式；建立无密钥/真实位置的规划样例。 | 部署 wkf API、此时直接导入数据。 | 作者授权已由 D01 确认；第三方条款核对完成；迁移清单可复核，样例可重现；Vago Web/iOS/领域测试有基线。 | [已确认 D01、D02](merge-decisions.md) |
| **1. 身份和领域映射** | 列清 wkf 表单、地点、路线、时间线、版本到 Vago Plan/Trip/Itinerary 的逐字段映射与缺失语义；为 D02 指定一个空的 Vago 测试账号，并建立旧 `chat_id`/`group_id`/版本到新 ID 的溯源映射；按 D03 同时设计新建和编辑草稿 Plan，确认时区、币种、坐标契约。 | AgentLoop、Neo4j 生产接入、前端大改。 | 用新 Plan、未转换的草稿 Plan 和既有 Trip 各一例检验映射；导入数据只能由指定测试账号读取；未定义字段不静默丢弃；所有入口有双用户测试。 | [已确认 D02、D03](merge-decisions.md) |
| **2. 候选持久化与查询 API** | 在 Vago MySQL 建候选版本及必要的 Brief/资源引用；提供创建、列举、按版本读取与状态读取的领域/API 路径；服务端生成版本和关联 ID。先以固定样例写入。 | 正式 Plan 写入、PostgreSQL、JSONL 替换对话库。 | Alembic 升降级/回滚路径明确；并发版本不重号、重复提交幂等；另一个用户无法读/改/确认候选；刷新后可回读。 |  |
| **2A. 测试账号历史数据导入** | 在阶段 2 契约上试导入并正式导入 wkf 全部历史 JSONL 会话和 PostgreSQL 行程候选；Neo4j 的历史图记忆复制到隔离测试图并绑定同一测试账号。保留原始 ID、版本、来源、导入批次及备份；不兼容字段列差异清单。 | 把旧数据当作真实生产用户事实、导入 `.env`/密钥、让图记忆默认参与规划。 | 各来源导出数、成功数、未映射数和目标数可核对；重复运行幂等；抽样回读会话/候选/记忆及来源正确；生产账号不可读取，失败可回滚。阶段 10 再评价图记忆是否进入生产上下文。 | [已确认 D02](merge-decisions.md) |
| **3. 时间线与约束校验** | 把 wkf `build_itinerary`/`dryRun` 的可复用逻辑及 `ItinerarySnapshot` 检查适配到 Vago 候选；定义适用规则、`fail`/`unverifiable`/警告及来源缺失处理；校验结果随版本保存。 | LLM 自行裁决硬约束、直接“提交即正式保存”。 | 多日、跨日时区、路线缺失、冲突、禁忌和预算缺证据反例通过；保存关口重新校验选中版本；D04 已确定硬约束 `fail` 或 `unverifiable` 阻止正式写入。 | [已确认 D04](merge-decisions.md) |
| **4. 外部地点与路线 provider** | 按 Vago 认证和配额边界适配 wkf 高德搜索/路线候选/选路缓存；统一地点与路线输出，记录坐标系、来源、时间和失效策略；境外 provider 先保留接口与降级策略。 | 替换 MapKit/Leaflet、把路线写入足迹、同时接所有国家 provider。 | 大陆至少一条真实路线能查询、选定、经时间线计算并预览；WGS-84 与 provider 坐标转换在地图上核对；密钥只在服务端，失败/限额有可理解的结果。 | [填写 D05](merge-decisions.md) |
| **5. LangGraph Runtime 与单 Agent 规划** | 在 Vago 中建立 LangGraph 编排基础，保留 LangChain 模型、工具和消息集成；接入 AgentLoop 的澄清、恢复、取消、预算与工具白名单能力。定义 Agent Registry / AgentSpec、子 Agent 与 DomainAgent 的结构化输入输出、工具范围、预算、超时、状态和报告契约；公开进度进入现有 `AgentConversation` / `AgentMessage` 与 SSE。规划主流程先以单 Agent 建立质量基线。 | 复制 wkf 的独立 OpenAI SDK 编排循环或完整 `MessageBus` / `SubAgentManager` 类；所有规划默认调用子 Agent；MCP、wkf 未认证路由或文件会话库。 | LangGraph 单 Agent 可多轮澄清并生成候选；运行可取消且有预算和终态；Agent 配置经过 schema 与工具白名单校验；公开事件按用户隔离并可回读；该 Runtime 能按既定契约挂接子图或子 Agent。 |  |
| **6. Web 聊天内资源预览** | 在现有 Vago AI 页面展示引用式地点/路线/地图/候选卡片、版本切换、校验警告和来源；答复文字引用稳定资源 ID，展开预览不覆盖聊天输入。 | wkf 三栏前端、整站升级 React/Vite、正式确认写入。 | 流式与历史消息均能恢复同一卡片；用户看得清来源、估算、硬约束状态和版本；窄屏输入体验可用。 |  |
| **7. 用户确认与正式 Plan 写入** | D03 已确定首版同时支持新建 Plan 和更新未转换的草稿 Plan/Itinerary。专用确认命令按认证用户、候选版本、目标 Plan 状态与版本重新校验，经 Vago Travel Service 原子写入；编辑时展示差异，保存候选到正式记录的关联并回读结果。进行中 Trip 修改仍属阶段 9。 | Agent 自动确认、修改进行中的 Trip。 | 用户拒绝/超时/目标已转换或被并发修改时正式数据不变；重复确认幂等；部分失败不留半成品；Web 可回读新建或更新的正式 Plan 和日程。此阶段才称首个端到端闭环。 | [已确认 D03、D04](merge-decisions.md) |
| **8. iOS 适配** | 基于阶段 7 的同一 API，展示候选/已确认计划、警告和来源；按移动端需要决定是否加入确认按钮和澄清回复。 | 复制 Web 编辑器、在 iOS 执行 Agent Runtime。 | 同一用户跨端版本一致；若提供确认，遵循同一幂等/审批规则；旧 iOS 足迹、打卡和行程展示可用。 | [填写 D06](merge-decisions.md) |
| **9. 进行中 Trip 重规划** | 生成“只改未来剩余日程”的候选差异，引用当前 Trip 与版本；校验时间/预算/已发生事实后展示变更，再经领域服务批准应用。 | 改写过去日程或 `TravelFootprint`、从建议直接静默写库。 | 拒绝后无变化；批准后差异可追溯并回读；并发修改触发冲突重算；足迹及已完成日程不受影响。 |  |
| **10. Neo4j 记忆对照试验** | Neo4j 先保留在隔离环境；以可重建投影连接 Vago 已授权事实/对话，比较“Vago 结构化上下文 + 可选 Qdrant”与“再加图记忆”的同题表现。 | 全量 MySQL 迁移、将推断事实写回原始旅行数据。 | 预先固定跨旅程偏好、时态矛盾和纠错样例；记录质量、来源正确率、双用户隔离、删除传播、时延与成本。未达门槛维持实验状态；共存或替换 Qdrant 另做决策。 | [填写 D07](merge-decisions.md) |
| **11. Sub-Agent 域委派 / MCP 按证据启用** | 基于阶段 5 的 LangGraph Runtime 和 AgentSpec 契约，实现 wkf SubAgentManager / DomainAgent 的任务委派能力；按领域配置注册 Agent，通过 LangGraph supervisor、subgraph 或合适的 Domain Tool 边界执行。对确需浏览器、长上下文或并行检索的任务开展委派；有明确 provider 需求时适配 wkf MCP 连接模式。 | 另建一套 Agent 循环、会话存储或消息总线；未经任务验证就让所有规划默认多 Agent；默认连接 Playwright/Exa。 | 使用 Vago 代表性规划任务与阶段 5 单 Agent 基线对照，记录任务完成质量、来源与约束保留、用户隔离、延迟、token/费用及失败恢复；通过门槛的任务才启用委派。MCP 连接具有明确授权、凭据管理、超时和关闭开关。 |  |

**建议的首个实现 PR**：只覆盖阶段 1 的可执行契约和阶段 2 的最小候选版本持久化/读取，使用固定样例与双用户隔离测试。时间线/约束校验作为下一 PR，随后才接地图、Agent 和界面。这样先固定“候选 ≠ 正式记录”的关键边界。

## 6. 贯穿各阶段的发布门槛

- **数据与权限**：每个新增 API/工具用两个账号验证列表、详情、版本、澄清、取消、确认和缓存；客户端提供的 `user_id/group_id` 不能决定归属。
- **兼容与迁移**：采用 Vago Alembic 管理 MySQL schema；逐调用方切换并回归 Web/iOS。D02 的 wkf 历史会话、候选和记忆全部映射到一个指定的 Vago 测试账号；保留原始来源与身份映射、去重、备份及撤回路径，不能直接混入生产用户上下文。
- **事实边界**：规划路线与实际 `TravelFootprint` 分开；来源、估算和不确定性在 UI 可见。地图 provider 切换不改变用户足迹坐标事实。
- **可观测与恢复**：公开事件可以显示过程，但候选、校验和正式写入结果须可独立回读；不记录原始 GPS、Prompt、模型内部推理或密钥到普通日志。
- **验收口径**：wkf 评测与单元测试证明相应代码路径可运行，不等于 Vago 真实场景已验收。每阶段用适配后的契约测试和一条完整用户路径验证，未通过不扩大默认流量。

## 7. 已确认决策与后续待填写事项

用户已在[决策填写表](merge-decisions.md)确认 D01–D04，并明确了 LangChain / LangGraph 与多 Agent 架构方向；下表是当前执行口径。D05–D07 尚未填写，可先推进不依赖其选择的工作，到对应阶段的决策门槛再确认。本文仍是直接指导文件。

| 编号 | 状态 / 决策时点 | 当前执行口径 |
| --- | --- | --- |
| D01 代码/素材复用权利 | 已确认 B | wkf 作者完全授权通过副本合并；阶段 0 仍核对第三方素材、依赖和署名要求。 |
| D02 历史 wkf 数据迁移 | 已确认 C | 全量迁移历史会话、候选和记忆，统一归属一个指定的 Vago 测试账号；分阶段盘点、导入、核数与回滚，不转成生产用户事实。 |
| D03 首个正式写入范围 | 已确认 B | 首版既能新建 Plan，也能编辑尚未转换为 Trip 的草稿 Plan；进行中 Trip 重规划仍在阶段 9。 |
| D04 硬约束无法验证 | 已确认 A | 明确硬约束为 `fail` 或 `unverifiable` 时阻止确认写入，先补证据或修正；不设置警告放行。 |
| Agent 技术与架构方向 | 用户已明确 | 保留 LangChain 模型、工具和消息集成，使用 LangGraph 编排；建立支持 Sub-Agent / DomainAgent 的架构与配置契约，阶段 11 按 Vago 任务评测启用委派。 |
| D05 境外规划首期范围 | 阶段 4 接 provider 前 | 先完成大陆高德闭环；境外路线 provider 单独评估，暂不承诺首期路线可用。 |
| D06 iOS 首轮操作范围 | 阶段 8 前 | 先展示候选与已确认方案；确认和澄清入口依实际移动场景决定。 |
| D07 Neo4j/Qdrant 长期组合 | 阶段 10 对照后 | Neo4j 保持隔离试验，Qdrant 维持现用途；不预先决定双库生产部署或替换。 |
