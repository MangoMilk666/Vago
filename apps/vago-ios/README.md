# Vago iOS

Vago 的原生 iOS 基础客户端。它使用 **Swift + SwiftUI**，直接调用 FastAPI `/api/v1` API，不经过 React、Vite Proxy 或旧 Spring Boot 服务。

这份文档面向熟悉 Python FastAPI / Java Spring Boot、但刚开始接触 iOS 的开发者。当前项目刻意保持小而完整：已跑通登录、会话、当前行程、日程、个人资料与基础足迹采集；照片、迷雾地图与旅行回忆属于后续能力。

## 当前能力

- 从 `Info.plist` 读取 API 地址；
- 手机号验证码发送与登录；
- Keychain 安全保存 access / refresh token；
- access token 返回 401 时自动刷新一次并重试原请求；
- 展示唯一的“进行中”正式行程及其每日安排；
- 展示基础个人资料和退出登录；
- iOS 与 Web 使用 FastAPI 同一套领域 API 和 JWT 协议。

## 开始前准备

需要 macOS 和 Xcode 26（项目最低部署版本为 iOS 17）。不需要 CocoaPods、Swift Package Manager 或额外的第三方依赖。

1. 启动 FastAPI：进入 `services/vago-ai` 后，使用项目现有虚拟环境启动服务。
2. 确认 `GET http://127.0.0.1:8000/health` 可访问。
3. 在 Finder 双击 [VagoIOS.xcodeproj](/Users/henrysang/Documents/Vago/apps/vago-ios/VagoIOS.xcodeproj)，或在 Xcode 中选择 **File > Open**。
4. 顶部 Scheme 选择 `VagoIOS`，目标设备选择一个 iOS Simulator，按 `Cmd + R` 构建并运行。

首次真机运行前，需在 Xcode 的 **Signing & Capabilities** 选择自己的 Team，并将 `com.vago.ios` 改为唯一的 Bundle Identifier。

## 目录与职责

```text
apps/vago-ios/
├── VagoIOS.xcodeproj/       # Xcode 工程配置、Build Settings、运行目标
├── VagoIOS-Info.plist       # App 元数据与 API 地址配置
├── VagoIOS/
│   ├── App/                 # App 入口、全局会话注入、根导航
│   ├── Core/                # API、认证、Keychain、网络模型等跨页面基础能力
│   ├── Features/            # 业务页面，按 Auth / Trips / Profile 分组
│   └── Resources/           # 图片、字符串、本地资源；当前暂无业务资源
└── README.md
```

与后端分层的大致对照：

| iOS 目录 | 类比 FastAPI / Spring Boot | 当前代码 |
|---|---|---|
| `App/` | 应用启动、依赖装配 | `VagoIOSApp`、`RootView` |
| `Core/Models.swift` | Pydantic schema / DTO | API 响应与行程模型 |
| `Core/APIClient.swift` | HTTP client + auth middleware | `APIClient`、`SessionStore` |
| `Core/KeychainStore.swift` | 安全凭证存储适配器 | Keychain 的 token 读写 |
| `Features/` | Controller 之后的页面层 | SwiftUI 页面与展示状态 |

SwiftUI 项目不像 Spring Boot 有固定的 controller/service/repository 三层。建议将可复用的网络、持久化和领域模型留在 `Core`，将特定业务 UI 放在 `Features/<Feature>`，避免所有代码堆进一个 View。

## 请求与认证链路

```text
LoginView
  -> SessionStore.login()
  -> APIClient POST /api/v1/auth/login/phone
  -> FastAPI 返回 accessToken / refreshToken / sessionId
  -> KeychainStore 写入 iOS Keychain

后续业务请求
  -> APIClient 自动添加 Authorization: Bearer <accessToken>
  -> 401 时 POST /api/v1/auth/token/refresh
  -> Keychain 替换新 token，并仅重试一次原请求
```

服务端的 refresh token 已按 `user_uuid + session_id` 存储。这意味着同一个账号的 iOS 与 Web 登录不会互相覆盖 refresh token。`session_id` 不等同于数据库设备表：当前是足够支撑双端并行登录的 Redis 会话标识，设备列表和全设备注销将后续按产品需求建设。

## Swift / SwiftUI 快速入门

### 类型、结构体与协议

Swift 强类型且偏向使用 `struct` 表示数据。`Codable` 是 `Encodable` 和 `Decodable` 的组合，角色接近“可序列化 + 可反序列化的 Pydantic DTO”。

```swift
struct Trip: Decodable, Identifiable {
    let uuid: String
    let title: String
    let status: Int

    var id: String { uuid }
}
```

- `let`：不可重新赋值，类似 Python 中约定不可变的变量，但由编译器强制。
- `var`：可变属性。
- `String?`：可空值，类似 `str | None`。
- `Identifiable`：为 SwiftUI 列表提供稳定 `id`，对应 React `key` 的需求。

### 声明式 UI

SwiftUI 的 `View` 类似 React 函数组件：`body` 声明“状态在当前值下应展示什么”，而不是命令式创建和销毁控件。

```swift
@State private var isLoading = true

var body: some View {
    if isLoading {
        ProgressView()
    } else {
        Text("加载完成")
    }
}
```

- `@State`：当前 View 自己拥有的可变状态，类似 React `useState`。
- `@StateObject`：当前 View 创建并长期拥有的引用对象；本项目根节点用它创建唯一 `SessionStore`。
- `@EnvironmentObject`：从上层视图树注入的共享对象，类似 React Context / 依赖注入。
- `@Published`：`ObservableObject` 的可观察属性，值改变时依赖它的页面会重绘。

不要在 `body` 内进行网络请求或写入状态；`body` 会因为状态变化多次执行。当前页面在 `.task { await load() }` 中发起异步加载。

### async / await 与 Actor

Swift 的 `async/await` 与 Python 类似：

```swift
Task {
    let trips: [Trip] = try await client.request(path: "travel/trips")
}
```

- `Task {}`：从按钮点击等同步回调启动异步任务。
- `try await`：请求可能抛出错误且会挂起等待网络结果。
- `do / catch`：类似 Python `try / except`。
- `@MainActor`：要求对象状态只在 UI 主执行上下文访问。它解决 Swift 6 的并发数据竞争检查；`URLSession` 等待网络时不会卡住界面。

## API 配置与网络调试

API 根地址位于 [VagoIOS-Info.plist](/Users/henrysang/Documents/Vago/apps/vago-ios/VagoIOS-Info.plist) 的 `VAGO_API_BASE_URL`：

| 运行位置 | 推荐地址 |
|---|---|
| iOS Simulator 与 FastAPI 同机 | `http://127.0.0.1:8000/api/v1` |
| 真机与 FastAPI 同一 Wi-Fi | `http://<Mac局域网IP>:8000/api/v1` |
| 测试 / 生产 | `https://api.example.com/api/v1` |

真机里的 `127.0.0.1` 指向手机自身，绝不是开发 Mac。用 `ipconfig getifaddr en0` 获取 Mac 的 Wi-Fi IP；还需要让 FastAPI 监听 `0.0.0.0`、确认防火墙放行端口 8000。

当前 plist 允许本地网络 HTTP，目的是便于开发联调。生产环境必须使用 HTTPS，并移除对任意 HTTP 的放行；不要把 token、数据库密码或 API 密钥写入 plist 或提交到 Git。

Xcode 常用操作：

| 操作 | 快捷键 / 位置 | 用途 |
|---|---|---|
| 运行 | `Cmd + R` | 编译、安装并启动 App |
| 停止 | `Cmd + .` | 停止当前运行进程 |
| 打断点 | 点击代码行号左侧 | 暂停观察变量和调用栈 |
| 单步执行 | `F6` / `F7` / `F8` | Step Over / Into / Out |
| 控制台 | `Cmd + Shift + Y` | 查看 `print`、运行日志和错误 |
| 清理构建缓存 | `Cmd + Shift + K` | 解决偶发旧产物问题 |

建议第一次调试时在 `APIClient.perform` 的 `URLSession.shared.data(for:)` 后设断点，检查：请求 URL、`Authorization` 头、HTTP 状态码、FastAPI 返回的 `{code,message,data}`。

若 Xcode 报出 `missing or invalid CFBundleExecutable`，表示自定义 `Info.plist` 缺少 `CFBundleExecutable`。本项目已配置为 `$(EXECUTABLE_NAME)`；清理构建目录后重新运行即可。

## 命令行构建

不打开 Xcode 时，可在仓库根目录执行：

```bash
xcodebuild \
  -project apps/vago-ios/VagoIOS.xcodeproj \
  -scheme VagoIOS \
  -sdk iphonesimulator \
  -configuration Debug \
  -derivedDataPath /private/tmp/VagoIOSDerived \
  build CODE_SIGNING_ALLOWED=NO
```

`-derivedDataPath` 将 Xcode 缓存放到临时目录，便于 CI 或受限环境构建。实际安装到真机仍必须启用代码签名。

## 常见问题

**登录后立刻回到登录页**：检查 FastAPI `JWT_SECRET_KEY` 已配置、Redis 可用，以及 iOS 的 API 地址是否指向同一套 FastAPI 服务。

**验证码发送失败**：当前后端验证码状态保存在 Redis，确认 Redis 运行且没有触发 60 秒发送间隔限制；开发环境验证码会记录在 FastAPI 日志中。

**真机无法访问服务**：检查 Mac 与手机在同一网络、FastAPI 不是只绑定 `127.0.0.1`、使用的是 Mac 局域网 IP、系统防火墙没有拦截端口。

**日期解码失败**：`Models.swift` 的 `Date` 依赖服务端 ISO 8601 时间格式；若后端 contract 改为自定义格式，应同步调整 `APIClient` 的 `JSONDecoder.dateDecodingStrategy`。

**不要怎么做**：不要把 refresh token 放进 `UserDefaults`（等价于明文偏好存储）；不要绕开 `APIClient` 各页各自手写 Authorization；不要把 iOS 当作 Web 的缩小版来同步迁移全部页面。

## 下一步

Phase 8 已完成第一版 Travel Tracking：在“记录”标签中，iOS 会在用户点击开始后申请“使用期间”定位权限，以约 20 米的距离变化采集前台 GPS 样本。样本先进入按用户 UUID 隔离的 `UserDefaults` 本地队列，网络可用时按每批最多 100 条调用 FastAPI 同步；服务端按 `userUuid + clientUuid` 去重，因此请求超时或重复重试不会重复生成轨迹。

MapKit 会读取服务端已同步轨迹并显示当前位置。手动打卡只能绑定进行中的正式 Trip；已结束行程仍允许补传此前离线缓存的 GPS 样本，但不允许再创建新打卡。当前版本刻意不启用后台定位、反向地理编码、照片关联、迷雾地图或复杂 GIS，避免在核心采集与同步机制尚未稳定前扩大范围。

首次在模拟器测试时，在 Simulator 的 **Features > Location** 选择一个预设位置或 GPX 路线，随后在 App 的“记录”页点击“开始记录”。真机需在系统弹窗中允许定位权限。API 数据库迁移请在 `services/vago-ai` 中执行：

```bash
.venv/bin/alembic upgrade head
```
