# iOS Travel Map 实施计划

基线日期：2026-09-05。本文基于当前仓库代码、[iOS README](../apps/vago-ios/README.md) 和 [Travel Footprint 设计](design/ios-travel-footprint.md) 编写，参考 project-remould-skill 的渐进迁移原则。本轮仅编写计划，不实施代码变更；以下 Phase 编号是 Travel Map 的局部实施阶段，不替代项目整体 remould Phase 1–9。

## 1. 结论与实施边界

当前已经具备前台定位、本地队列、100 条分批上传、服务端幂等去重、全屏地图初版、轨迹折线以及打卡创建和读取。下一步应修正数据交接与地图交互，再增加分段渲染、打卡详情和实验性 Fog。无需重建定位器、认证协议或同步接口。

建议顺序：**Phase 1 布局与页面状态 → Phase 2 定位生命周期与 camera → Phase 3 本地/远端合并与同步调度 → Phase 4 过滤、分段及折线 → Phase 5 打卡详情与创建体验 → Phase 6 有限历史浏览 → Phase 7 Fog 实验**。Phase 5 可在 Phase 2 后独立推进；Fog 不阻塞前六阶段验收。

当前目标设备是 iPhone，项目最低 iOS 17、`TARGETED_DEVICE_FAMILY = 1`。先覆盖不同 iPhone 尺寸、横竖屏与大字体；原生 iPad 布局不因“动态适配”自动纳入本轮。

本文将代码事实、尚待实机复现的风险和建议实现分开说明。曾经编译通过不等于全屏、键盘、定位权限及弱网场景已经真机验收通过。

## 2. 当前实现清单

下表 iOS 路径均相对于 `apps/vago-ios/VagoIOS/`，后端路径相对于 `services/vago-ai/`。

| 能力      | 现有文件 / 类型                                                                             | 实际行为与边界                                                                                                                |
| ------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| 应用与页面装配 | `App/VagoIOSApp.swift` / `VagoIOSApp`；`App/RootView.swift` / `RootView`、`MainTabView` | WindowGroup 注入会话，登录后显示行程、记录、我的；根和 Tab 已有最大宽高约束                                                                         |
| 网络与认证   | `Core/APIClient.swift` / `APIClient`、`SessionStore`；`Core/KeychainStore.swift`        | 统一 envelope、Bearer、401 后刷新一次并重放请求；Keychain 保存 token；业务页面不需另写认证                                                         |
| API 地址  | `Core/APIConfiguration.swift`；工程外层 `VagoIOS-Info.plist`                               | 读取 plist，真机使用开发 Mac 地址；当前 plist 为开发者本机配置，不在计划中固化 IP                                                                    |
| 当前行程    | `Features/Trips/CurrentTripView.swift`；`TrackingView.load()`                          | 请求 `travel/trips` 并选择 `status == 2`；记录页尚不能选择历史行程                                                                       |
| 定位与权限   | `Core/LocationTrackingStore.swift` / `LocationTrackingStore`                          | 单个 CLLocationManager；When In Use；期望约 10 米精度、20 米 distanceFilter；delegate 桥接回 MainActor                                 |
| 样本校验    | 同上 / `handleLocationUpdate`                                                           | 仅拒绝负水平精度和早于约 120 秒的样本；delegate 只消费回调数组最后一条；无完整异常点处理                                                                    |
| 本地足迹队列  | 同上 / `pendingSamples`、`append`、`save`                                                 | JSON 存储于 `vago.location.pending.{userUuid}`，按账号隔离；每次修改重新编解码整个数组                                                        |
| 批量上传    | 同上 / `syncPendingSamples`、`LocationSyncPayload`                                       | 按 Trip 分组、每批最多 100 条；成功删除该批 UUID，失败保留；每个新样本立即启动同步任务                                                                    |
| 网络模型    | `Core/Models.swift`                                                                   | `PendingLocationSample` 的 UUID 编码为 `clientUuid`；另有 `FootprintLocation`、`LocationSyncResult`、`CheckinRequest`、`Checkin` |
| 地图页面    | `Features/Footprints/TrackingView.swift` / `TrackingView`                             | 已是 ZStack 全屏地图加浮层，没有常驻导航栏；底部仍用固定 74pt padding                                                                          |
| 地图渲染    | 同文件 / 私有 `TrackingMap`                                                                | 服务端点全量连成一条 4pt 折线，同时每点显示 Marker；打卡为橙色 Annotation，最后本地样本为红色 Marker                                                      |
| Camera  | `TrackingMap.initialRegion`                                                           | 仅初始 1km 区域；依次取本地最新样本、远端末点、末次打卡，最后默认新加坡；没有回到当前位置和跟随模式                                                                   |
| 手动打卡    | 同文件 / `CheckinSheet`、`createCheckin`                                                  | 按钮打开 medium sheet，FocusState 管理键盘；提交后关闭键盘，成功追加标记并关闭 sheet；无选中详情                                                        |
| 足迹 API  | `app/footprints/router.py`、`service.py`                                               | 上传、查询 GPS、创建和查询打卡均已存在；复用认证依赖和行程归属校验                                                                                    |
| 数据模型    | `app/footprints/models.py`、`schemas.py`                                               | MySQL `location_samples` 与 `checkins` 分表，GPS 和主动记录语义独立；没有 segment、Fog、照片表                                              |
| 数据迁移    | `migrations/versions/20260904_03_create_footprint_tables.py`                          | 创建两张事实表与索引；现有 migration 不应为新功能改写                                                                                       |
| 已有测试    | `tests/test_footprints_api.py`、`test_footprints_service.py`                           | 覆盖基本上传/重复重试、轨迹归属、打卡状态约束、读取和 Z 时间格式；尚无 iOS 自动化测试目标                                                                      |

### 2.1 现有 HTTP contract

统一前缀为 `/api/v1`，返回 `{code, message, data}`。

| 接口                                            | 实际约束                                                                                                      |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `POST /footprints/location-samples/sync`      | 必填 `tripUuid`，1–100 个 samples；每点有 `clientUuid`、坐标、可选精度/速度和 `recordedAt`；返回 acceptedCount / duplicateCount |
| `GET /footprints/trips/{trip_uuid}/locations` | 校验当前用户拥有未删除 Trip；按 recorded_at 升序返回该行程全部点，无分页；响应 **未包含 clientUuid**                                       |
| `POST /footprints/checkins`                   | 当前用户的进行中 Trip 才能创建；地点名最长 256、备注最长 2000；返回完整 Checkin                                                       |
| `GET /footprints/trips/{trip_uuid}/checkins`  | 已存在，不需要重新新增；按 checked_at 升序返回完整打卡，足够驱动详情页                                                                 |

`location_samples` 保存服务端 32 位 uuid、client_uuid、user_uuid、trip_uuid、坐标、accuracy_m、speed_mps、recorded_at、created_at；数据库唯一约束是 `(user_uuid, client_uuid)`。`checkins` 保存独立 uuid、归属、地点名称、坐标、备注与时间。服务端归属由认证用户决定，不能信任客户端传入 userUuid。

GPS 同步目前只检查 Trip 归属和未删除状态，不检查其状态或采样时间是否早于结束时间。因此“允许已结束行程补传离线数据”是当前行为，但还不能声称服务端已严格区分补传与结束后的新采样。本轮优先保留兼容行为，客户端在发现行程结束后停止采集；严格的服务端时间边界需后续独立定义，不能直接用计划 endDate 充当实际结束时间。

### 2.2 必须纳入计划的实际缺口

1. **本地与远端缺少共同标识。** 数据库已有 client_uuid，但 GET DTO 未暴露；仅凭坐标和时间无法可靠去重，MySQL 浮点精度和时间精度也可能改变表示。
2. **已采样不等于已显示。** 地图只有远端快照和最后一个本地点；pending 数组私有，上传成功后从队列删除，却没有同步更新远端快照。`load()` 先 GET 再同步，也不会读回补传结果。
3. **断网首次进入记录页无法独立初始化。** `prepare()` 在远端读取成功之后才执行，无法先恢复本地队列。`restoreSession()` 把包括临时网络失败在内的所有异常都视为退出并清 Keychain，冷启动离线使用尚未成立。
4. **生命周期依赖页面。** `.onDisappear` 停止记录；授权回调只要已有 Trip 就可能启动采样，没有明确“用户仍希望记录”的条件；停止后的迟到回调也没有 isTracking 检查。
5. **单个点立即触发上传，缺少同步互斥。** MainActor 在 await 时允许任务交错，不代表网络任务串行；服务端唯一索引可防重复行，但并发先查后插仍可能报唯一约束错误，不能等同于所有并发重试都会返回成功。
6. **“当前位置”是旧记录样本。** 停止或移动后可能过时；打卡无法脱离持续记录获得一次新鲜位置，也没有冻结用户确认的坐标。
7. **折线没有断点。** 全部 GPS 点连接，跨天、乘机、停止再开始可能出现虚假长线；大量 Marker 掩盖实际路线和打卡。
8. **布局仍待验证。** 固定底部偏移、medium-only 且不可滚动的 sheet、小屏及键盘状态均存在风险；刷新会替换整个地图，容易重置 camera。现有 plist 没有 UILaunchScreen 或 Launch Storyboard，且工程关闭自动生成 plist；屏幕有效区域偏小应先检查安装产物与窗口尺寸，不能只归因于 SwiftUI frame。
9. **错误状态有遮挡。** 打卡错误写入父地图 message，sheet 中未显示；初次加载失败可能落入“无进行中行程”，混淆网络失败和真实空数据。
10. **时间与存储需回归。** 响应可带微秒 Z 时间，解码器没有显式 fractional-seconds ISO 分支，需实测补齐兼容用例；队列解码失败目前直接删除，不能作为长期可靠恢复方案。代码把 GPS 描述成“非敏感”不准确，应在后续文档/注释同步纠正。

以上是源代码检查结果或明确标注的风险，本轮未运行真机、构建或测试，不将历史验证结果当作本次验收。

## 3. 对照设计文档

| 设计能力             | 已有能力                         | 需要修改                       | 需要新增                           | 当前阶段不做                     |
| ---------------- | ---------------------------- | -------------------------- | ------------------------------ | -------------------------- |
| 全屏地图             | ZStack、Map、浮层、Tab 内入口        | 安全区域、固定偏移、错误/刷新状态、sheet 滚动 | 状态 sheet、图层入口                  | 自建底图或地图手势                  |
| 当前定位/camera      | CLLocationManager、初始区域       | 当前定位与轨迹样本分离                | Locate、跟随/自由浏览、范围适配            | 后台持续跟随、导航                  |
| 生命周期             | 开始/停止、When In Use            | 授权回调、迟到回调、Tab/账号生命周期       | 明确记录意图和前台策略                    | Always、24h 采集、复杂 Pause 状态机 |
| pending + synced | 本地队列、远端 GET                  | 同步后的展示交接                   | 共同 key、合并视图模型                  | 全历史永久本地副本                  |
| GPS 过滤           | 负精度/120 秒旧点过滤                | 完整回调数组、有序处理                | 基础质量过滤和异常连接判断                  | Map Matching、高级平滑/活动识别     |
| segment          | 无                            | 一条全局折线                     | 时间/空间断点、显式记录段标识                | 专门的 segment 服务或表           |
| 足迹样式             | 单层 polyline + 每点 Marker      | 删除常驻每点 Marker、增量更新         | 主线/柔和外描边、图层开关                  | 大规模 zoom/tile 系统           |
| Check-in         | POST、GET、Annotation、输入 sheet | 新鲜坐标、错误提示、字段长度与重复提交        | 点击详情、Trip/时间确认                 | 离线打卡队列、照片、拖 pin、POI 搜索     |
| 历史行程             | 后端可按任意自有未删除 Trip 查询          | 不再把浏览地图绑定为必须有 active Trip  | 有限历史选择、只读状态                    | 自动下载全用户历史                  |
| Fog              | 无                            | 不把路线或当前位置直接当探索事实           | 固定半径派生区域和实验图层                  | PostGIS、矢量瓦片、面积百分比         |
| 分层               | 定位/同步已在 Store，认证已统一          | View 中请求逐步外移               | 一个页面 ViewModel、一个足迹 Repository | 一次性复制四套 service/repository |

设计中的 `tripUuid?`、altitude、syncStatus 是概念模型，不能机械替换现有 DTO。本轮 Trip 仍必填；userUuid 取自会话/缓存命名空间；syncStatus 是客户端派生状态；无明确用途不增加 altitude 列。设计 §22 将 notes 列为未来能力，但当前备注已经可写可读，应直接复用。

## 4. 推荐的最小结构

继续保留 `Core/LocationTrackingStore.swift` 作为现有采样、缓存和批量同步的实现入口。先增加小接口和状态修正，不一次性拆成 LocationService、FootprintSyncService、CheckinRepository 三套新实现。

UI 在 `Features/Footprints/` 就地拆分即可，设计里的 `Features/TravelMap/` 是示意名称。避免为统一名字先搬动所有文件；稳定后有需要再单独重命名。

```text
RootView / 登录会话范围
  ├── LocationTrackingStore（继续复用；唯一采样和同步执行者）
  └── TrackingView
        └── TravelMapViewModel（页面加载、所选行程、camera、sheet 状态）
              ├── FootprintRepository（pending/已确认/remote 合并）
              ├── APIClient（现有认证与 HTTP）
              └── FootprintGeometry（过滤/分段/渲染数据纯计算）
```

Check-in 的两个简单请求初期放在 ViewModel 即可；只有形成独立缓存/离线需求再抽 CheckinRepository。页面内存数据与持久化队列都按 user + Trip 隔离；异步请求结束时校验账号与所选 Trip 的请求版本，防止切换后旧结果回填。

## Phase 1：布局、地图常驻与可验证的页面状态

实施状态：已完成

**目标：** 验证并修正真实全屏适配；地图刷新、空状态和表单不破坏地图视口。

**涉及现有文件：** `App/RootView.swift`、`Features/Footprints/TrackingView.swift`、必要时 `Features/Auth/LoginView.swift`；检查外层 `VagoIOS-Info.plist` 与 `VagoIOS.xcodeproj/project.pbxproj`。

**建议新增文件/类型：** 在 `Features/Footprints/` 拆出 `TravelMapCanvas.swift`（承接 TrackingMap）、`CheckinSheet.swift`；增加 `TravelMapViewModel.swift` 接收页面请求与 loading/error 状态。仅搬移已有职责，不复制实现。

**实施内容与数据流：**

- 先比较真机截图、window bounds、safeAreaInsets 与构建后的 plist。排查 Launch Screen 缺失造成的兼容显示风险；确认后在自定义 plist 配置原生 Launch Screen，不能仅在关闭自动生成 plist 时添加无效的生成开关。
- 地图底图可延伸至安全区下方，交互控件保持在系统提供的安全区内；移除硬编码的 74pt 底部占位。保持原生 TabBar，不复制一套自绘栏。
- Map 实例常驻；刷新只更新数据和小型状态提示。初始加载失败、空行程和已有缓存三者分别呈现，错误保留重试入口。
- 拆出状态控制 sheet；创建打卡 sheet 支持 medium/large、自适应滚动、显式关闭及键盘完成。取消只关闭表单，不隐式开始/停止记录。
- 浮层透明空白不拦截地图手势。原生 POI 的点击和地点信息按最低 iOS 17 的可用能力验收，不能把“看见 POI 名字”等同于已接入地点详情。

**后端/API/数据库：** 纯 iOS，无变更。

**主要风险：** 缺少 Launch Screen 只是待验证原因；不能把根视图 `.frame(maxHeight: .infinity)` 当作已解决全屏的证据。sheet 键盘遮挡、地图与按钮手势竞争需要实机检查。

**真机验证：** 至少小屏与大屏各一台 iPhone，横竖屏、浅/深色、大字体；截图核对状态栏、TabBar、Home Indicator；展开 sheet 并输入长备注，能滚动到提交键、收起键盘和取消；连续刷新不跳回初始地图区域。证据记录设备/系统版本和复现步骤。

## Phase 2：定位意图、当前坐标与 camera

实施状态：已完成（2026-09-05）

**本次落地说明：** `LocationTrackingStore` 已提升为 App 级共享对象，并新增 `CurrentLocationFix` 区分一次定位与已持久化足迹。连续采样只在用户明确开始记录、应用位于前台、登录会话和进行中行程均有效时写入队列；切换 Tab、展开 sheet 不会停止记录，注销时只清理内存状态。地图已改为可绑定 camera：初次有数据时自适应可视范围，点击定位恢复跟随，用户拖动后进入自由浏览。后台只停止前台连续定位，回到前台按原记录意图恢复；本阶段不请求后台定位权限，也不新增后端 API 或数据库迁移。

**目标：** 区分“看当前位置”和“保存足迹”，让地图跟随、自由浏览与记录状态独立。

**涉及现有文件：** `LocationTrackingStore.swift`、`RootView.swift`、`VagoIOSApp.swift`、`TrackingView.swift` 及 Phase 1 拆出的 Canvas/ViewModel。

**建议新增类型：** Store 内的记录意图状态、`CurrentLocationFix`（坐标、时间、水平精度）、页面 `CameraMode`。暂不新建另一套 CLLocationManager。

**实施内容与数据流：**

- 同一定位回调先更新有效的 currentLocation；仅在用户有记录意图、会话与 active Trip 有效时进入已有持久化路径。Locate/打卡可申请一次定位，单次定位不自动入足迹队列，也不驱散 Fog。
- 授权回调只恢复此前用户明确发起的动作；停止后清除记录意图，迟到回调不得继续保存。处理 denied/restricted、精确位置关闭、定位失败/超时，避免按钮无反馈。
- 将 Store 的所有权提升到登录会话范围，Tab 切换和弹 sheet 不再决定是否停止；注销清理内存并取消旧账号任务。进入后台停止持续定位，回前台仅在原记录意图仍有效且 Trip 仍进行中时恢复，并建立新段边界；不申请后台定位权限。
- Canvas 使用可绑定 camera position。Locate 回到新鲜位置；跟随只影响 camera；用户拖动进入自由浏览，后续 GPS 不抢回视角；恢复跟随由用户点击。初次远端加载可适配足迹范围，不再永久固定新加坡/1km。
- 统一当前坐标显示来源，避免自绘旧样本 Marker 与系统定位点同时争夺“当前位置”语义。地图获取定位不触发第二条持久化链路。

**后端/API/数据库：** 纯 iOS，无变更。

**主要风险：** 授权和停止事件交错、旧账号 Task 回调、camera 每次刷新强制归位；不能把系统的回调距离阈值理解为固定每 20 米必有一点。

**真机验证：** 首次拒绝后去设置授权，未点开始不能产生上传；Locate 后数据库样本数不增；开始步行、切 Tab、弹 sheet、停止、锁屏再回来，状态和采样符合上述策略；自由拖图不被 GPS 拉回；停止后移动再打卡应获得新坐标；账号 A 注销切 B 不显示 A 的点。

## Phase 3：本地与远端合并、同步交接和离线恢复

实施状态：未开始

**目标：** 新点本地保存后立即可见，上传/读回过程中不重复、不消失，保留现有批量同步算法和幂等键。

**涉及现有文件：** `LocationTrackingStore.swift`、`Core/Models.swift`、`Core/APIClient.swift` 的必要兼容分支、TravelMapViewModel；后端 `app/footprints/schemas.py`、必要的 `service.py`，两个 footprint 测试文件。

**建议新增文件/类型：** `Core/FootprintRepository.swift`、`Features/Footprints/FootprintDisplayPoint.swift`。Repository 调用现有 Store 同步，不另造上传器。网络恢复需要时增加一个小型 NWPathMonitor 包装，只作为重试信号。

**实施内容与数据流：**

1. 远端 `LocationSampleResponse` 增加现有 DB 字段 `clientUuid`，iOS DTO 先可选读取以兼容部署窗口；服务端支持任意字符串幂等键，不能把远端字段强制解码为 UUID。有效 UUID 字符串可规范化大小写，其他键按原文保留。后端先上线，新客户端随后上线；旧服务器不支持精确合并，必须明确最低服务端版本，不能以坐标近似去重假装支持。
2. Store 暴露按账号/Trip 的 pending 快照、同步状态和成功批次通知。先恢复本地数据再发 GET；显示模型统一由“远端快照 + pending + 已确认但未读回的短期内存点”组成。
3. 合并 key 为用户命名空间内的 clientUuid，渲染时再按 Trip 隔离；相同 key 由远端权威字段覆盖本地值，缺少 clientUuid 的旧远端点仅使用 server uuid。排序使用 recordedAt + 稳定 key，绝不按经纬度或时间单独去重。
4. 上传成功仍按原逻辑删除 pending；同时保留已确认点的内存副本，直到 GET 返回相同 clientUuid 再移交，避免网络读回失败时轨迹闪失。此副本不是第二个待上传队列；冷启动离线不承诺恢复已上传且未缓存的全部历史。
5. 上传调度增加单一在途任务。继续按 Trip 分组、每批 ≤100；建议初始触发为积累约 20 点或前台约 30 秒、手动刷新、停止记录、前台恢复及网络恢复。数字是待测参数，不改变 100 点接口上限；失败保留同一 clientUuid，有限退避且尊重取消。
6. 单个 Trip 的不可重试错误不无限阻塞其他 Trip 的批次；已删除 Trip 的待传数据隔离并向用户展示，不能静默删除。计数、同步中、最近成功时间、失败/重试入口独立显示，不沿用陈旧 syncError。
7. 保持 APIClient/Keychain/refresh 协议。仅修正会话恢复将“临时网络不可达”误判为 token 失效的分支：保留凭证；本机已有登录账号时用最小账号标识及最近 active Trip 元数据恢复离线页面，联网再校验，缓存不作为服务端授权证据。真正无效凭证仍走现有退出逻辑。明确离线可记录/查看本地数据，在线写打卡需网络。若无法确定缓存 Trip 是否仍进行中，离线状态标示未验证，联网后立即复核。
8. 用真实服务端微秒 Z 时间覆盖 decoder；出现并发 401 竞争时在现有 SessionStore 合并刷新任务，不在 Feature 再实现 refresh。

```text
采样 → 原有本地队列 → 合并显示
                  ↓ 调度现有 sync
                 FastAPI → 成功批次 → 短期已确认显示
                    ↓ GET clientUuid
                  远端快照 → 按稳定 key 替换 → 合并显示
```

**后端/API/数据库：** 本阶段必须 FastAPI 配合增加响应 clientUuid，**不改表**。保留原 URL、字段、batch 上限及唯一约束。若并发重复上传测试暴露 IntegrityError，只在现有写入事务上补冲突回滚/重查，保证结果计数，不替换幂等机制。

**主要风险：** 账号切换后的在途响应、重复刷新 token、时间精度和 key 变化；UserDefaults 的整数组写入及冷启动离线边界。网络可达信号不能保证 API 可达；旧已上传点没有本地长期缓存时仍需联网查询。

**真机验证：** 已登录后断网行走，地图立即出现多个本地点；恢复网络点数稳定，pending 归零但轨迹不消失；模拟 POST 已落库但响应丢失，再传相同 batch，DB 不增重复行；上传后 GET 失败仍可见点；杀进程后离线恢复未上传队列；跨账号无回填；200+ 点分批 ≤100；无移动时网络恢复也能重试。后端补 clientUuid 回传、并发重试与归属测试，iOS 增加有意义的合并/交接测试。

## Phase 4：GPS 过滤、segment 与足迹渲染

实施状态：部分完成（2026-09-05，已完成 Phase 4A 的时间排序、15 米渲染降采样、断段与平滑路线展示；采集端完整质量过滤与显式段标识仍未实施）

**目标：** 可靠数据源转为可信的多段路径，消除虚假长连接和逐点 Marker 噪声。

**涉及现有文件：** `LocationTrackingStore.swift`、`Core/Models.swift`、FootprintRepository、Canvas；Phase 4B 涉及后端 footprint models/schemas/service、新 migration 与 `docs/database/db_schema.sql`。

**建议新增文件/类型：** `Features/Footprints/FootprintGeometry.swift`，包含 `GPSPointFilter`、`FootprintSegmentBuilder`、`FootprintSegment` 等小型纯计算类型；不为每个类型机械拆文件。

### Phase 4A：无需改表的质量过滤与推断分段

- 采集端保持原有精度配置和 distanceFilter，按时间消费 delegate 数组所有有效点。检查有限数值、经纬度范围、负/过大 accuracy、过旧/明显未来时间和重复回调；同时间不同坐标不随意认定为同一点。
- 初始校准值可取新采样最大水平误差 100m、历史时间间隔 5 分钟、相邻间距 5km 作为保守断线阈值。它们是人工待验证配置，不是所有交通方式的真值；不将步行阈值硬套到高铁/飞机。
- 持久化前只删除确定无效的采样；历史数据的可疑点只在显示层过滤。对突变坐标优先隔断连线并等待后续点确认，不让一个漂移点成为拒绝此后正常点的基准。
- 速度采用距离/正时间差辅助判断，结合精度误差；未知 speedMps 不当作静止。距离异常可能是真实交通位移，断线并保留端点比抹去访问事实更稳妥。
- 顺序为同 Trip 合并/去重 → 时间排序 → 点质量判断 → 连接有效性判断 → segment → polyline。跨 Trip 永不连接，非正时间差、长间隔和不可信跳跃断段。
- 默认取消所有 GPS Marker，只对单点段提供轻量点符号；每个 segment 两层 stroke（柔和外描边 + 主线）。轨迹、打卡、当前位置使用不同形状与语义，pending 状态不只靠颜色表达。
- 不为每个 camera 变化重新处理全部原始数据。数据或阈值变化才更新几何；只追加活动段，完成段缓存；真正出现性能瓶颈再引入简化算法，不修改原始点。

**后端/API/数据库：** Phase 4A 纯 iOS，依赖 Phase 3 的共同 key，无表修改。

### Phase 4B：显式停止/恢复的可持久化段边界

仅凭时间和距离无法辨别短暂“停止→重新开始”，更无法跨设备恢复该边界。为了完整满足设计，建议本阶段增加一个可选 **trackingSegmentUuid**，而不是创建 tracking_sessions 或 segments 表。

- 开始一次新的连续记录、后台中断后的恢复产生新标识；同段每个样本携带相同标识。它与 JWT sessionId、clientUuid 完全不同。
- `PendingLocationSample` 新字段可选解码，旧 UserDefaults JSON 继续可读；不得重生成已有点 clientUuid。iOS 请求与远端 DTO 增加字段。
- MySQL `location_samples` 增加 nullable `tracking_segment_uuid`，同步 service 原样保存、GET 返回；旧数据保持 NULL，不伪造历史边界。
- 显式段标识变化优先断段；缺失/过渡样本保守断开或采用 Phase 4A 推断。即使段相同，时间/空间断点仍生效。
- 新增 Alembic revision，不修改已执行的 20260904_03；先升级 DB 和服务端再发客户端。旧客户端可继续省略新字段。

**数据流变化：** 新采样增加连续记录段标识；合并后的点生成多个稳定 segment，渲染消费 segment 而不是整行程的一条折线。

**后端/API/数据库：** Phase 4B 必须 FastAPI 配合，新增一个可空列，无新表。若本次不接受 migration，可以只交付 4A，但必须标记“短间隔停止/恢复跨设备边界未实现”，不能宣称完整分段完成。

**主要风险：** 过滤过强丢掉真实旅行、旧数据无段标识、对异常点处理后重新连接两侧造成假路线。阈值先在真实行走/车行数据上校准；现有 MySQL Float 坐标也不适合承诺厘米级重合，不因此立即迁移整个坐标 schema。

**真机验证：** 室外步行、室内弱信号、短暂关闭定位、停止后立即恢复、跨天记录；不出现跨城市直线。把远距离和异常速度样本作为可控测试夹具，不以模拟路线替代真实精度验收；同账号第二台设备/重装后的联网读取仍保留新段边界。过滤、排序和 segment 使用纯函数测试覆盖边界。

## Phase 5：Check-in 创建确认与详情

实施状态：部分完成（2026-09-05，已实现打卡前单次定位、冻结坐标与 30 米重复打卡限制；Check-in Annotation 详情仍未实施）

**目标：** 用户可以独立打卡、清楚确认位置，并点击已保存标记查看真实记录。

**涉及现有文件：** `TrackingView.swift`、Phase 1 的 CheckinSheet、Canvas/ViewModel、`Core/Models.swift`、Phase 2 的 currentLocation 接口。

**建议新增文件/类型：** `CheckinDetailSheet.swift`、轻量 `CheckinDraft`；无需新增 CheckinRepository 或数据库实体。

**实施内容与数据流：**

- 点击打卡取得新鲜有效定位，冻结坐标、定位时间、确认时间和 active Trip 到 draft；建议坐标新鲜度先以 30 秒为校准值，过期可重新定位，不能静默用数小时前的 latestSample。
- sheet 展示地点名、备注、坐标/定位状态、时间和所属 Trip；不能反向地理编码时不伪造地址。提交时检查 Trip 仍有效，FastAPI 409/403/网络错误在 sheet 内可见且保留输入。
- 没有 active Trip、定位拒绝或尚未定位要给明确原因。浏览历史行程时创建入口默认只读；回到当前行程后再打卡，不误绑所选历史 Trip。
- 校验 256/2000 字符限制并阻止双击并发提交；成功后用响应 uuid 去重更新 Annotation，清焦点并关闭 sheet。现有 POST 没有业务幂等键，超时后不能盲目自动重试创建；提示结果待确认并刷新列表。
- Annotation 以稳定 uuid 选择，打开详情展示名称、时间、备注、坐标和 Trip 信息。现有 GET 列表已经返回完整详情，无需新详情接口。已结束 Trip 只读，不出现编辑按钮或尚不存在的 Memory 跳转。

**后端/API/数据库：** 纯 iOS，复用已存在的 GET/POST；离线创建、创建幂等键作为后续独立增强，不在本阶段暗加队列。

**主要风险：** 用户编辑期间坐标不断变化、错误被 sheet 遮住、超时重试造成重复打卡、详情点击与地图手势冲突。

**真机验证：** 未开始连续记录也可单次定位打卡，但不生成 GPS 轨迹；移动后打卡坐标新鲜；取消/键盘完成/拖拽收起/长备注滚动均可用；关闭网络提交显示表单错误且内容保留；保存后点击标记看到同一备注和时间；重开/第二台设备读取一致。

## Phase 6：有限历史行程地图

实施状态：未开始

**目标：** 没有进行中行程也可查看自己的旅行地图，限制数据规模。

**涉及现有文件：** TrackingView、TravelMapViewModel、FootprintRepository、`Core/Models.swift`；使用现有 `travel/trips` 和按 Trip 的 footprint/checkin GET。

**建议新增文件/类型：** `TripMapPickerSheet.swift`；ViewModel 增加 selectedTrip 与 activeRecordingTrip 的独立状态。

**实施内容与数据流：** 读取行程元数据，区分未开始/进行中/已结束；一次仅加载用户明确选择的一份 Trip。切换先清理上一份派生状态，取消或忽略旧请求；camera 的“显示全部”适配该 Trip 的 segment/打卡范围。正在记录的 Trip 不随历史浏览切换绑定；状态面板明确告诉用户仍在记录哪份行程。

**后端/API/数据库：** 有限、较小单 Trip 浏览可纯 iOS 完成。现有 GET 无分页；若真实单 Trip 点量达到性能预算，需单独增加可选 cursor/limit 或时间范围及稳定排序，保持旧数组 contract 默认行为，不能截断后仍宣称显示完整行程。分页不是本阶段无条件前置。

**主要风险：** 无 active Trip 导致历史页被挡、旧请求污染新 Trip、误向历史 Trip 写入、长行程无界下载。

**真机验证：** 结束当前行程后仍可选择历史查看；历史模式无编辑/打卡；快速切换两份 Trip 不混点、不连线；记录期间浏览历史不会改上传 tripUuid；用代表性的大行程记录加载时长、内存和交互卡顿，再决定分页是否必要。

## Phase 7：简单 World Fog / Explored Area 实验

实施状态：未开始

**目标：** 使用现有个人旅行事实派生固定半径探索区域，验证“未探索淡化、探索处显露”的体验。

**涉及现有文件：** Canvas、ViewModel、Phase 4 的质量筛选结果、Phase 6 的所选 Trip 数据；不改 LocationTrackingStore 的采样或同步路径。

**建议新增文件/类型：** `ExploredAreaBuilder.swift`、`MapLayersSheet.swift`；真实遮罩阶段按需要新增 `TravelMapKitView.swift`（UIViewRepresentable）、`ExplorationFogOverlay` 与 `ExplorationFogRenderer`。

**数据范围与语义：**

- 第一版只针对当前或选定 Trip 已加载的数据，可缩放浏览，但不能声称是账号的完整“已探索世界”。历史没加载不代表用户从未去过；界面标注数据范围。
- 由质量通过的真实采样点和已保存 Check-in 分别产生固定米制半径圆盘。建议第一版两类都从 100m 试验；配置版本进入派生缓存 key。currentLocation 的一次查询不驱散 Fog；被过滤的漂移点也不能开辟探索区域。
- 使用原始有效点而非简化后 polyline 顶点，保留访问事实。不要在断段之间插值“探索走廊”。仅为渲染去掉重复圆盘，不删除事实数据。
- 区域是可重建的客户端派生数据，不上传、不建表；已上传点从 pending 退出后依旧通过 Phase 3 交接保留探索效果。清理账号/切换 Trip 同时清理派生缓存。

**分两步交付：**

1. **7A 探索区域验证：** 沿用 SwiftUI Map，固定半径圆形 overlay 验证真实米制范围、层级和性能，显示为“探索区域预览”。这一步尚非真正的反向 Fog，不以着色圆圈冒充已驱散遮罩。
2. **7B 可关闭的真实 Fog：** 先做小型 renderer 技术验证。若 SwiftUI Map 不能可靠表达反向区域遮罩，在单一 Canvas 内用 MKMapView 包装替代地图承载层，外层 SwiftUI 页面、数据源、定位与同步保持复用。不能叠放两套 Map。MKMapView 仍是 MapKit，复用原生手势、POI、camera 和 Annotation。

**7B 的最小绘制方案：**

- 自定义覆盖可见世界范围的 MKOverlay，renderer 仅处理请求的 mapRect；在隔离的绘图层/alpha mask 中先填半透明浅色 Fog，再将有效圆盘范围清成透明，最后与地图合成。重叠圆盘按并集显露，不能直接把多个洞以 even-odd 叠加而让重叠区重新变暗。
- 半径从米转换为当地纬度的 map points，再由 renderer 转换为绘图坐标；按当前 mapRect 加半径裕量筛选圆盘。必要时仅使用内存网格索引加速候选查询，网格不是新事实表或 GIS 基础设施。
- 渲染层顺序为底图 → Fog → segment 描边 → 打卡 → 当前定位；遮罩不接管触摸。保持浅色半透明，不把地图变成不可读黑幕。
- 只失效新增圆盘影响范围；renderer 使用不可变数据快照，避免渲染回调与 MainActor 的可变数组竞争。不每次定位都创建整世界 bitmap。
- 首版 Fog 在平面、有限行程范围验证；倾斜/3D、极高纬度或跨日期变更线未验证时关闭该实验层或明确限制，普通地图交互继续保留。世界缩放时若半径已小于像素，不夸大探索面积。

**后端/API/数据库：** 纯 iOS。没有 Fog API、PostGIS、空间索引表、vector tile、自建地图服务或面积百分比。

**主要风险：** 圆盘重叠漏绘、纬度导致半径失真、重建造成掉帧、MKMapView 适配后 camera/POI 行为回退、遮罩吞手势。7B 不通过则保留普通地图和可关闭的 7A，Fog 不阻塞核心记录交付。

**真机验证：** 同一路线 Fog 开/关截图对比；两个相交圆盘的交叠区仍透明；真实步行产生新区域，刷新和同步不恢复 Fog；单次 Locate 不驱散；平移/缩放/旋转后区域与地图对齐；打卡详情始终能点中；低端设备观察内存、CPU、帧率。用断段测试夹具确认跨城市不存在显露走廊。

## 5. UserDefaults 是否继续使用

**结论：前台、短期、少量 pending 队列可以继续使用；不把它扩展为全历史数据库。** 先修正访问接口和可靠性，不提前迁移 SwiftData/Core Data。

当前问题是每次 append/remove 都编解码全量数组、存储失败无明确状态、解码失败直接删数据，以及队列不对显示层开放。这些问题可在现有 Store 内改进：缓存内存快照、串行更新、按账号恢复、可选新字段向后兼容、损坏数据隔离并提示恢复失败，避免静默清空。GPS 是敏感个人数据，不能因为存储在 UserDefaults 就称其非敏感；日志只记录计数和错误类型，不记录坐标或凭证。

Phase 3 真机测量 100/1000/5000 点的 JSON 字节量、编解码耗时、主线程卡顿与杀进程恢复情况。数字仅是测试梯度，不是系统容量保证。若实际离线队列持续达数千点、写入明显影响交互、产品要求更强断电持久性或多日后台记录，则触发存储迁移；不可直接丢弃旧点以维持所谓上限。

迁移时优先给现有队列增加薄的存储适配接口，评估 Application Support 中原子写文件能否满足短期队列，再按长期查询需求选 SQLite/SwiftData/Core Data。不在 MVP 同时维护两套写入源；旧 UserDefaults 读取成功、数量/key 校验完成之后才切换。Fog 几何和已同步历史不常驻 UserDefaults；已确认但未读回点只作本次会话短期展示缓冲。

## 6. 后端配合与发布顺序

| 阶段       | 纯 iOS 部分         | 必须 FastAPI 配合                     | 数据库                 |
| -------- | ---------------- | --------------------------------- | ------------------- |
| Phase 1  | 全屏与状态、sheet      | 无                                 | 无                   |
| Phase 2  | 定位意图、camera、生命周期 | 无                                 | 无                   |
| Phase 3  | 合并、调度、离线恢复       | GPS GET 回传 clientUuid；并发冲突问题按测试修正 | 无                   |
| Phase 4A | 过滤、推断分段、折线样式     | 无                                 | 无                   |
| Phase 4B | 连续记录段标识          | 可选 trackingSegmentUuid 的输入、保存、输出  | 新增一个可空列和新 migration |
| Phase 5  | 打卡确认与详情          | 无，GET checkins 已存在                | 无                   |
| Phase 6  | 有限历史选择           | 仅真实数据量超预算时新增分页/范围能力               | 无强制修改；按查询评估索引       |
| Phase 7  | 派生探索区、Fog 渲染     | 无                                 | 无                   |

Phase 3 先发布兼容的响应增量，再发合并客户端；Phase 4B 先升级数据库和后端，再发携带段标识的客户端。旧客户端继续工作，旧样本保持可读；每次只验收一个 Phase，4A/4B 分别可交付。

既有后端测试应保留，新增测试集中于共同 key、归属、旧请求兼容、并发幂等和段字段往返。不得为了客户端渲染更改认证用户来源、唯一键或把 Check-in 合并进 GPS 表。

## 7. 推荐执行方式与验收门槛

先做 Phase 1 是为了建立可信的真机显示基线；Phase 2 解决“是否正在采集、当前位置是否新鲜”；Phase 3 解决“已采样的数据是否一直可见”；Phase 4 再解决“连接是否代表实际经过”。Phase 5 使用新鲜位置和已有完整 Checkin DTO，改动相对独立；Phase 6 扩展回顾能力但限制加载规模；Phase 7 最后验证探索区域，避免在不可靠点集上累积错误 Fog。

每阶段提交前记录一份真机验收结果，包括设备/系统、账号和 Trip 测试范围、网络状态、操作步骤、期望与实际结果、必要截图。测试使用专用旅行数据，正常用户不需要在 UI 中看到内部 batch/key 等实现细节。

纯 UI 阶段以小屏/大屏/键盘/手势实测为主；合并、分段和派生几何增加纯函数测试；API 增量运行对应 footprint contract/ownership 测试。只有编译通过不可标记地图体验验收完成。当前仓库没有 iOS 测试 target，可在 Phase 3 首次引入有明确价值的合并测试时建立最小单元测试目标，不为本轮文档搭建测试工程。

后续总体 remould 的 Travel Memory 仍需满足双端实际数据闭环；本计划只负责 iOS Travel Map，Web 足迹查询/渲染仍需单独验收，不因 iOS 计划完成自动标记整体 Phase 9 前置完成。

## 8. 依据与技术核对

仓库事实主要来源于第 2 节列出的代码与 [设计文档](design/ios-travel-footprint.md)。README 对功能的概述较早，实际代码已存在全屏初版、polyline、GET checkins 和 Annotation，应以代码为准；README 中“打开记录页前台采集”的范围也不能替代生命周期实测。

Launch Screen 的配置候选来自 Apple 的 [UILaunchScreen 文档](https://developer.apple.com/documentation/bundleresources/information-property-list/uilaunchscreen)；本仓库缺失配置是检查结果，其是否导致当前设备视口偏小仍需 Phase 1 实测确认。

Camera 跟随实现参考 Apple 的 [MapCameraPosition.userLocation](https://developer.apple.com/documentation/mapkit/mapcameraposition/userlocation(followsheading:fallback:))，作为复用原生 camera 能力的依据，具体与自有 currentLocation 的职责在 Phase 2 明确。

Fog 的 renderer 方案属于基于现有数据范围的实施建议；局部绘制、坐标转换和并发渲染约束参考 Apple 的 [Displaying overlays on a map](https://developer.apple.com/documentation/mapkit/displaying-overlays-on-a-map) 与 [MKOverlayRenderer.draw](https://developer.apple.com/documentation/mapkit/mkoverlayrenderer/draw(_:zoomscale:in:))。遮罩合成、圆盘并集和性能仍是 Phase 7 的验证任务，不是当前已实现能力。
