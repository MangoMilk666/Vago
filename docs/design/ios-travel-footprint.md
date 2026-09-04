

# Vago iOS Travel Footprint & World Map

## 1. Overview

`Travel Map` 是 Vago iOS 客户端面向个人旅行记录的核心空间界面。

它以 **MapKit 全屏地图**为基础，将用户当前定位、旅行足迹、手动打卡、历史轨迹和未来的世界迷雾能力统一组织在同一个地图体验中。

该模块不是一个独立的“地图工具页”，而是 Vago Personal Travel Intelligence 的空间入口，用于回答：

- 我现在在哪里；

- 我曾经去过哪里；

- 我在旅行过程中具体走过哪些路线；

- 我在哪些地点留下过主动记录；

- 世界上哪些区域已经被我探索；

- 这些地点与我的 Trip、照片、备注和旅行回忆之间有什么关系。

Travel Map 不负责重新实现地图本身已有的能力。道路、地标、地图缩放、地图样式、POI 等基础地图体验优先复用 Apple MapKit；Vago 主要负责叠加属于用户自己的旅行数据和交互。

---

## 2. Current State

当前 iOS 客户端已经完成第一版 Travel Tracking 基础链路。

现有能力包括：

- 使用 Core Location 获取前台位置；

- 用户主动点击开始后启动足迹采集；

- 当前约以 20 米距离变化作为位置采样条件；

- GPS 样本先进入客户端本地队列；

- 本地数据按当前用户 UUID 隔离；

- 网络可用时以最多 100 条为一批同步到 FastAPI；

- 服务端通过 `userUuid + clientUuid` 实现幂等去重；

- 请求超时或重复重试不会重复创建轨迹数据；

- MapKit 可以读取服务端已同步的轨迹数据；

- 地图可以显示当前位置；

- 用户可以进行手动打卡；

- 手动打卡必须绑定到当前进行中的正式 Trip；

- 已结束 Trip 不允许新增打卡；

- 已结束 Trip 仍允许补传此前离线缓存的 GPS 样本。

当前版本暂未包含：

- 后台持续定位；

- 世界迷雾；

- 高级轨迹渲染；

- 反向地理编码；

- 打卡照片关联；

- 基于地图的 Travel Memory；

- 复杂 GIS 运算；

- 长期本地数据库持久化。

本设计文档建立在现有采集与同步机制之上，后续实现应尽量复用已经验证过的链路，而不是重写当前基础能力。

---

## 3. Product Goal

Travel Map 的目标不是简单显示 GPS 点，而是把用户的旅行经历转化为具有连续性、个人归属感和可回顾性的空间记录。

目标体验可以概括为：

```text
Current Location
        +
Travel Footprint
        +
Manual Check-ins
        +
Explored World
        +
Trip Context
        ↓
Personal Travel Map
```

用户打开该页面时，应首先感受到“这是我的旅行世界”，而不是“这是一个带地图组件的功能页面”。

地图应该始终是整个界面的主要视觉载体，其余控件、状态面板和操作入口均围绕地图进行叠加。

---

## 4. Core UX Principles

### 4.1 Map is the Canvas

Travel Map 使用接近 Apple Maps 的沉浸式全屏布局。

地图应尽可能铺满 iPhone 可视区域：

```text
┌──────────────────────────────┐
│                              │
│                              │
│            MapKit            │
│                              │
│                    [ Locate ] │
│                              │
│                              │
│                     [Checkin] │
│                              │
│ ┌──────────────────────────┐ │
│ │   Current tracking state │ │
│ └──────────────────────────┘ │
└──────────────────────────────┘
```

主要 UI 应通过：

- floating button；

- floating card；

- overlay；

- bottom sheet；

- compact status panel；

等形式覆盖在地图上，而不是通过传统 `VStack` 将地图挤压成页面中的一个矩形区域。

SwiftUI 层面优先采用：

```text
ZStack
├── Map
├── Map overlays
├── Floating controls
├── Status cards
└── Sheets
```

---

### 4.2 Progressive Disclosure

地图上的主要按钮只负责唤醒功能，不长期展开复杂面板。

例如：

```text
Check-in Button
      ↓ tap
Check-in Sheet
```

```text
Tracking Status Button
      ↓ tap
Tracking Control Panel
```

用户没有主动操作时，应保持地图本身尽可能干净。

---

### 4.3 Separate Spatial Meanings

不同地图元素必须具有明确不同的视觉语义。

至少区分：

```text
当前位置
≠
GPS 足迹
≠
手动打卡
≠
世界迷雾
≠
Apple MapKit POI
```

特别是：

- GPS Footprint 表示“用户实际经过的移动轨迹”；

- Check-in 表示“用户主动留下的旅行记录”；

- Fog / Explored Area 表示“用户曾经探索过的空间区域”。

这三者不应使用相似的点状标记混在一起。

---

## 5. Map Screen Layout

Travel Map 应作为一个独立 Feature 页面存在，例如：

```text
Features/
└── TravelMap/
```

页面主体由 MapKit 提供。

基础结构建议：

```text
TravelMapView
│
├── Map
│   ├── current location
│   ├── footprint overlays
│   ├── check-in annotations
│   └── fog overlays
│
├── FloatingControls
│   ├── locate button
│   ├── tracking button
│   ├── check-in button
│   └── map options button
│
└── Sheets
    ├── tracking panel
    ├── check-in panel
    ├── check-in detail
    └── map layer options
```

地图应该能够延伸到主要安全区域之下，使视觉上接近系统原生地图 App。

顶部和底部元素必须考虑：

- Dynamic Island；

- Home Indicator；

- Safe Area；

- Tab Bar；

- future navigation chrome。

如果 Travel Map 仍位于 App 主 Tab 中，应尽量避免额外的顶部 Navigation Bar 长期占用地图空间。

---

## 6. Native Map Interaction

Travel Map 应尽可能保留 MapKit 原生地图体验。

用户至少需要能够：

- 单指拖动地图；

- 双指缩放；

- 旋转地图；

- 改变视角；

- 查看 Apple MapKit 已有地标；

- 点击已有 POI；

- 查看地点名称；

- 回到当前位置；

- 切换是否跟随当前位置；

- 在地图缩放后浏览历史足迹；

- 查看自己的 Check-in。

Vago 不应该自行实现：

- 道路数据；

- 普通地标数据库；

- 地图瓦片；

- 基础地图手势；

- Apple 已提供的地点展示能力。

Vago 的地图层应该主要负责：

```text
MapKit Base Map
        +
Vago Personal Spatial Data
```

---

## 7. Location Tracking

### 7.1 Tracking Lifecycle

足迹记录必须由明确的用户操作控制。

基础状态建议定义为：

```text
IDLE
  ↓
TRACKING
  ↓
PAUSED
  ↓
TRACKING
  ↓
STOPPED
```

MVP 可以暂时简化为：

```text
IDLE
  ↓
TRACKING
  ↓
STOPPED
```

未来再增加 Pause。

UI 应明确告诉用户当前是否正在记录位置。

例如：

```text
Recording
01:24:35
52 GPS points
Last synced 2 min ago
```

用户不应该依赖地图上的轨迹颜色去猜测 App 是否正在采集位置。

---

### 7.2 Location Permission

当前版本使用：

```text
When In Use
```

定位权限。

第一阶段继续保持前台定位即可。

未来若增加后台旅行轨迹记录，应单独设计：

- `Always` permission；

- Background Modes；

- 用户解释页面；

- 电池消耗控制；

- 后台策略；

- App 被系统挂起后的恢复逻辑。

后台定位不属于当前 Travel Map 重构的必要前置条件。

---

### 7.3 Footprint Sample

每一个原始 GPS 采样点至少应具有：

```text
FootprintPoint
├── clientUuid
├── userUuid
├── tripUuid?
├── latitude
├── longitude
├── horizontalAccuracy
├── altitude?
├── recordedAt
└── syncStatus
```

其中建议保留：

```text
horizontalAccuracy
recordedAt
```

即使第一阶段地图没有直接使用这些数据。

原因是 GPS 数据天然存在漂移。

例如：

```text
actual movement
───────→

GPS sample
• • •          •
              ↑
        temporary drift
```

后续进行：

- 异常点过滤；

- 轨迹平滑；

- 速度分析；

- 地图简化；

时都需要这些信息。

---

### 7.4 Sampling Strategy

当前约 20 米的距离变化阈值可以继续作为第一版默认策略。

采样不应简单追求越多越好。

目标应是在：

```text
轨迹精度
+
电池消耗
+
本地存储
+
同步流量
+
地图渲染性能
```

之间取得平衡。

未来可以根据状态动态调整采样，例如：

```text
walking
→ relatively dense

vehicle
→ larger distance interval

stationary
→ significantly reduced sampling
```

该能力不属于当前 MVP。

---

## 8. Footprint Rendering

### 8.1 Rendering Goal

地图最终不应该直接显示大量 GPS 离散点：

```text
• • • • • • • •
```

而应该将这些位置转换为连续轨迹：

```text
───────────────
```

足迹的视觉重点应该是：

> 用户实际经过世界的路径。

基础处理过程：

```text
Raw GPS Points
      ↓
Invalid Point Filtering
      ↓
Chronological Ordering
      ↓
Optional Simplification
      ↓
Polyline / Path
      ↓
Map Rendering
```

---

### 8.2 Trail Appearance

轨迹应比普通导航线更加具有个人旅行记录的感觉。

避免只使用默认：

```text
thin blue polyline
```

建议形成至少两层视觉：

```text
soft halo
══════════════

main trail
──────────────
```

例如：

```text
Outer translucent stroke
        +
Inner stronger stroke
```

这样可以实现：

- 在复杂地图背景上仍然可见；

- 视觉更柔和；

- 不像导航路线；

- 与 MapKit 默认路线形成差异；

- 更符合 Personal Travel Memory 的产品定位。

具体颜色和视觉参数由后续 Design System 决定，本设计文档不固定最终品牌色。

---

### 8.3 Segment Boundaries

并非所有时间连续的 GPS 点都应该自动连接。

例如：

```text
Singapore
•
•
•

8 hours later

Tokyo
•
•
•
```

如果直接按时间连接：

```text
Singapore ───────── Tokyo
```

会产生不存在的巨大直线。

因此轨迹生成应考虑 segment。

可以根据以下条件切断：

- 时间间隔过大；

- 两点距离异常；

- 速度不合理；

- tracking session 不同；

- Trip 不同；

- 用户明确停止并重新开始记录。

概念模型：

```text
Footprint
├── Segment A
│   ├── p1
│   ├── p2
│   └── p3
│
└── Segment B
    ├── p4
    └── p5
```

第一阶段可以优先按照 tracking session 或明显时间间隔切分。

---

### 8.4 Zoom-aware Rendering

随着历史数据增长，不应在世界级缩放时仍然绘制几十万条原始 GPS 点。

未来应按地图 zoom level 使用不同精度的数据。

例如：

```text
World View
→ highly simplified footprint

Country View
→ medium detail

City View
→ detailed path

Street View
→ near-original path
```

实现方式未来可以考虑：

- polyline simplification；

- server-side aggregation；

- map region query；

- tile / grid based retrieval。

MVP 暂时可以加载当前 Trip 或有限历史范围的数据。

---

## 9. Manual Check-in

### 9.1 Domain Meaning

Check-in 是用户主动创建的 Personal Travel Annotation。

它不是 GPS sample。

因此：

```text
FootprintPoint
≠
Checkin
```

FootprintPoint 表示：

> 系统记录用户经过这里。

Checkin 表示：

> 用户主动选择在这里留下记录。

---

### 9.2 Creating a Check-in

用户点击地图上的 Check-in 按钮时，应打开专门面板。

默认使用：

```text
current location
```

并允许用户确认：

- 当前地点；

- 地点名称；

- 时间；

- 备注；

- 所属 Trip。

当前规则继续保持：

```text
只有进行中的正式 Trip
可以创建新的 Check-in
```

如果当前没有正式进行中的 Trip，应明确告诉用户无法绑定，而不是静默失败。

---

### 9.3 Check-in Location

第一阶段可以继续以当前定位作为 Check-in 坐标。

后续可以扩展：

- 在地图长按某处打卡；

- 从附近 POI 中选择；

- 调整 pin 位置；

- 反向地理编码；

- 搜索地点。

这些属于后续增强能力。

---

### 9.4 Check-in Rendering

Check-in 应使用独立于足迹轨迹的 Annotation。

例如：

```text
        ◉
Marina Bay Sands
```

或者使用自定义 Symbol / Marker。

它应该在视觉上表达：

> 这是用户主动留下的旅行节点。

而不是普通 GPS 点。

点击 Check-in 后应展示详情：

```text
┌─────────────────────────────┐
│ Marina Bay Sands            │
│                             │
│ Singapore                   │
│ Sep 4 · 19:42               │
│                             │
│ “晚上散步的时候顺路来到这里” │
│                             │
│ View Memory                 │
└─────────────────────────────┘
```

未来可附加：

- photos；

- notes；

- rating；

- emoji；

- Trip；

- AI-generated travel memory。

---

## 10. World Fog / Explored World

### 10.1 Concept

World Fog 表示用户“探索过哪些空间”，而不是用户的具体移动路线。

因此：

```text
Footprint Trail
=
Where exactly did I travel?

Fog / Explored Area
=
Which parts of the world have I explored?
```

两者必须保持独立。

---

### 10.2 Rendering Layers

最终 Travel Map 可以形成：

```text
MapKit Base Map
      │
      ├── Fog Overlay
      │
      ├── Footprint Trail
      │
      ├── Check-in Annotation
      │
      └── Current Location
```

地图层顺序需要确保：

- Footprint/Check-in经过的固定半径覆盖位置不再有Fog层覆盖（类似雾气驱散的效果）

- Fog 不遮挡重要 Vago 元素；

- Footprint 在 Fog 上仍清晰；

- Check-in marker 始终容易点击；

- Current Location 保持最高交互优先级。

---

### 10.3 Fog Behavior

基础概念为：

```text
unexplored
→ visually covered / muted

explored
→ revealed
```

但 Vago 不一定必须实现传统游戏式的黑色迷雾。

视觉目标应该更偏：

> elegant explored-world visualization

例如可以使用：

- semi-transparent overlay；

- softened map regions；

- subtle mask；

- blurred / desaturated unexplored area；

- light visual contrast；

- explored glow。

最终效果应保持地图可读性，不应让用户感觉整个地图被黑色遮罩压住。

---

### 10.4 Explored Area Model

不要直接把原始 GPS 点本身当作 Fog 数据。

概念流程建议：

```text
GPS Points
    ↓
Exploration Radius
    ↓
Explored Cells / Regions
    ↓
Fog Overlay
```

例如每个 GPS point 可以解除周围一定半径的区域。

未来数据结构可以采用：

- grid；

- geohash；

- spatial cell；

- polygon。

MVP 不应立即引入复杂 GIS。

第一版可以先完成：

```text
GPS location
      ↓
fixed exploration radius
      ↓
simple map overlay
```

验证体验之后再优化算法。

---

## 11. Offline-first Tracking

旅行环境天然存在：

- 飞机；

- 地铁；

- 漫游；

- 弱网；

- 无网络；

- 网络频繁切换。

因此足迹记录不能依赖实时 API 请求。

当前架构：

```text
Core Location
      ↓
Local Queue
      ↓
Batch
      ↓
FastAPI
```

应该继续保留。

GPS 采样成功本身不能依赖：

```text
POST /footprints
```

是否成功。

---

## 12. Batch Synchronization

当前每批最多：

```text
100 points
```

的机制可以作为第一阶段默认值继续使用。

客户端概念状态：

```text
PENDING
   ↓
SYNCING
   ↓
SYNCED
```

失败：

```text
SYNCING
   ↓
FAILED / PENDING
   ↓
retry
```

如果当前实现没有独立持久化这些枚举状态，也至少需要维持等价逻辑。

---

### 12.1 Idempotency

服务端当前通过：

```text
userUuid + clientUuid
```

去重。

这一设计应继续保留。

这样客户端可以安全执行：

```text
send
 ↓
timeout
 ↓
unknown whether server received
 ↓
retry same batch
```

而不会生成重复轨迹点。

---

### 12.2 Sync Trigger

同步可以由以下事件触发：

- 累积到一定 batch size；

- App 前台活跃；

- 网络恢复；

- 用户停止记录；

- 用户主动刷新；

- 周期性 lightweight sync。

不建议每获得一个 GPS sample 就立即请求服务器。

---

## 13. Local Storage

当前使用：

```text
UserDefaults
```

保存按用户隔离的少量待同步队列。

对于当前 MVP 和小批量数据来说可以继续使用。

但如果未来实现：

- 长时间后台记录；

- 数千或数万 GPS point；

- 多 Trip 离线记录；

- 丰富 Check-in；

- 离线地图数据；

- 长期历史缓存；

则不应继续把大量 GPS 数据长期放入 UserDefaults。

届时应评估：

- SwiftData；

- Core Data；

- SQLite；

- lightweight local database abstraction。

迁移应在真实数据量和需求出现后进行，而不是当前提前增加复杂度。

---

## 14. Data Ownership

所有个人空间数据都必须属于当前登录用户。

包括：

```text
FootprintPoint
Checkin
Explored Area
Travel Memory
```

iOS 客户端必须确保：

- 本地缓存按 user UUID 隔离；

- logout 后不向新账号暴露旧账号位置数据；

- sync request 不依赖客户端传入 user UUID 来决定最终 ownership；

- 服务端根据 authenticated user 校验资源归属；

- Check-in 对应 Trip 必须属于当前用户。

---

## 15. Travel Map Architecture

Travel Map 不应该把：

- Core Location；

- URLSession；

- MapKit；

- local persistence；

- sync；

- UI state；

全部写进一个 SwiftUI View。

建议逐步形成以下职责：

```text
TravelMapView
       │
       ▼
TravelMapViewModel
       │
       ├── LocationService
       │
       ├── FootprintRepository
       │
       ├── CheckinRepository
       │
       └── FootprintSyncService
```

具体类名可以根据现有工程调整，不要求一次性创建全部抽象。

---

### 15.1 TravelMapView

负责：

- SwiftUI 布局；

- MapKit 展示；

- floating controls；

- sheet；

- 用户交互；

- loading/error UI。

不负责：

- 构造复杂 HTTP request；

- Keychain；

- GPS persistence；

- batch sync algorithm。

---

### 15.2 LocationService

负责：

```text
Core Location
```

包括：

- permission；

- current location；

- tracking lifecycle；

- location update；

- accuracy filtering；

- future background configuration。

它不应该依赖具体地图 UI。

---

### 15.3 FootprintRepository

负责统一访问：

```text
local footprint
+
remote footprint
```

View 不应关心一条轨迹来自：

- 本地 pending queue；

- FastAPI；

- cache。

---

### 15.4 FootprintSyncService

负责：

- batch；

- retry；

- idempotent upload；

- pending state；

- network recovery。

LocationService 不应该每获得一个 location 就直接调用 API。

---

### 15.5 CheckinRepository

负责：

- create check-in；

- fetch check-ins；

- Trip ownership；

- API interaction。

Check-in 和 Footprint 应继续保持两个独立 domain concept。

---

## 16. Data Flow

### 16.1 GPS Recording

```text
Core Location
      ↓
LocationService
      ↓
FootprintPoint
      ↓
Local Queue
      ↓
TravelMap renders local point
      ↓
FootprintSyncService
      ↓
FastAPI
      ↓
MySQL
```

地图不应该必须等数据同步成功后才显示用户刚走过的轨迹。

---

### 16.2 Historical Rendering

```text
TravelMap opens
      ↓
FootprintRepository
      ↓
FastAPI historical points
      +
local pending points
      ↓
merge
      ↓
deduplicate
      ↓
sort
      ↓
segment
      ↓
render
```

这样用户在断网状态下仍然可以看到刚刚记录的本地足迹。

---

### 16.3 Check-in

```text
User taps Check-in
      ↓
Current Location
      ↓
Check-in Sheet
      ↓
User confirms
      ↓
CheckinRepository
      ↓
FastAPI
      ↓
Map annotation
```

如果未来 Check-in 支持离线创建，可再增加 local pending queue。

当前无需与 Footprint 同时强行实现。

---

## 17. Backend Contract

iOS 继续直接调用：

```text
FastAPI /api/v1
```

不经过：

- React；

- Vite Proxy；

- Spring Boot。

所有新 Travel Map API 应继续符合现有统一响应结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

客户端继续通过统一 `APIClient` 完成：

- bearer token；

- access token；

- 401 refresh；

- retry；

- JSON decode。

Travel Map Feature 不应自己实现第二套认证逻辑。

---

## 18. Performance Considerations

Footprint 数据属于天然持续增长的数据。

因此设计时必须避免：

```text
每次打开地图
→ 下载用户全部历史 GPS points
→ 一次性全部渲染
```

第一阶段允许数据规模较小时采用简单实现，但架构上应该允许未来增加：

- Trip filtering；

- date range；

- map region query；

- simplified geometry；

- pagination；

- aggregated path；

- zoom-aware resolution。

MapKit 渲染层也应避免频繁因为单个 GPS point 更新而重建全部历史 polyline。

---

## 19. Privacy and Sensitive Location Data

GPS 足迹属于高度敏感的个人数据。

Vago 应遵循以下原则：

- 只在用户明确开始记录后采集；

- UI 明确显示当前 tracking 状态；

- 不偷偷启用后台定位；

- 不把位置数据写入普通日志；

- 不把位置权限描述写成模糊用途；

- 本地缓存必须与账号隔离；

- 服务端 API 必须基于认证用户控制访问；

- Production 必须使用 HTTPS；

- 不将位置数据暴露给其他用户作为默认行为。

未来如果加入：

- public trip；

- social sharing；

- shared travel map；

必须额外设计位置隐私边界。

个人足迹与打卡默认均应视为私人数据。

---

## 20. MVP Scope

下一阶段 MVP 建议集中实现：

### Map Experience

- 全屏 MapKit；

- 原生地图手势；

- 当前定位；

- floating controls；

- bottom sheet；

- Apple MapKit POI 基础能力。

### Footprint

- 保留现有采集逻辑；

- 展示本地 pending + server synced 足迹；

- GPS point 转连续 polyline；

- 基础异常连接过滤；

- 多 segment；

- 优雅的 footprint stroke。

### Check-in

- 当前坐标手动打卡；

- 绑定 active Trip；

- Map annotation；

- 点击查看详情；

- 明显区别于 Footprint。

### Sync

- 保留现有 100 point batch；

- 保留 `userUuid + clientUuid` 去重；

- 网络恢复后重试；

- UI 可以显示基础 sync 状态。

### Fog

第一阶段可以实现一个实验性质版本：

```text
GPS Point
→ fixed radius
→ explored region
→ basic overlay
```

Fog 不应该阻塞 Footprint 和 Check-in 主功能上线。

---

## 21. Out of Scope for Current MVP

以下能力暂不作为当前阶段必要目标：

- 24 小时后台持续定位；

- Always Location 权限；

- 高复杂度轨迹预测；

- Map Matching；

- GIS Server；

- PostGIS；

- vector tile；

- 完整空间数据库；

- 实时多人位置；

- 社交足迹；

- public heatmap；

- Apple Maps 的自定义替代地图；

- POI 数据库自建；

- 自动识别所有停留地点；

- 大规模历史数据优化；

- 照片地图完整能力；

- AI Travel Memory 自动生成。

---

## 22. Phase 2 Extensions

核心体验稳定后可以逐步增加：

### Tracking

- background location；

- adaptive sampling；

- stationary detection；

- activity-aware sampling；

- battery optimization。

### Check-in

- reverse geocoding；

- POI selection；

- long-press map check-in；

- photos；

- notes；

- emoji / tags；

- memory attachment。

### Footprint

- advanced smoothing；

- speed-aware filtering；

- map matching；

- historical timeline；

- Trip-specific color / style；

- trip playback animation。

### World Fog

- grid / geohash；

- region aggregation；

- city / country exploration progress；

- percentage explored；

- world overview；

- beautiful reveal animation。

### Travel Memory

```text
Check-in
+
Footprint
+
Photos
+
Trip
+
Notes
        ↓
Travel Memory
```

地图最终可以成为进入 Personal Travel Memory 的空间索引。

---

## 23. Long-term Product Direction

Travel Map 最终应成为 Vago 三个核心体验之一：

```text
Travel Map
    +
Travel Memory
    +
AI Companion
```

三者关系可以理解为：

```text
Travel Map
Where did I go?

Travel Memory
What happened there?

AI Companion
What does Vago know about my travel life,
and how can it help me next?
```

随着项目发展，Travel Map 不应该退化成单纯的“GPS 轨迹页面”。

它应该逐渐形成用户自己的：

> Personal Travel World.

用户每进行一次真实旅行，地图上都会留下新的轨迹、地点和记忆，最终形成长期积累且只属于用户自己的旅行空间档案。

---

## 24. Implementation Principle

后续开发遵循：

```text
collect reliably
      ↓
sync reliably
      ↓
render clearly
      ↓
improve visual experience
      ↓
add advanced spatial intelligence
```

不要反过来先构建复杂 GIS 或世界迷雾算法，再补基础采集可靠性。

当前已经完成的：

```text
location collection
+
local queue
+
batch sync
+
idempotency
+
basic MapKit
+
manual check-in
```

是后续 Travel Map 的基础。

下一阶段重点应放在：

```text
full-screen map experience
+
footprint rendering
+
check-in rendering
+
local + remote footprint merge
+
simple explored-world visualization
```

在这些体验稳定后，再逐步增加后台定位、复杂 Fog、照片和 Travel Memory。


