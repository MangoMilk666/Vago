import SwiftUI

@main
struct VagoIOSApp: App {
    // @main 指定 iOS 应用的进程入口；App 协议相当于 SwiftUI 版本的 AppDelegate 配置入口。
    // @StateObject 让根视图拥有唯一的会话对象；视图重绘不会重新创建登录状态。
    @StateObject private var session = SessionStore()
    // 定位服务提升到 App 生命周期；切换 Tab、弹出 sheet 都不会重新创建 CLLocationManager。
    @StateObject private var tracking = LocationTrackingStore()
    // 行程上下文独立于页面实例，跨 Tab 共享用户明确选择的唯一足迹记录目标。
    @StateObject private var tripContext = TripContextStore()
    // 与个人页共用同一持久化键，切换后整棵视图树立即收到新主题。
    @AppStorage("vago.appearance.theme") private var selectedTheme: AppTheme = .indigo
    // 外观模式独立于主题配色；默认保持原有的系统外观行为。
    @AppStorage("vago.appearance.mode") private var selectedAppearance: AppAppearance = .system
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        // Scene 表示一个系统窗口场景；当前 iPhone 应用只创建一个 WindowGroup。
        WindowGroup {
            RootView()
                .environment(\.appTheme, selectedTheme)
                .preferredColorScheme(selectedAppearance.colorScheme)
                // EnvironmentObject 类似在视图树中注入共享依赖，子页面可直接读取同一会话。
                .environmentObject(session)
                .environmentObject(tracking)
                .environmentObject(tripContext)
                // .task 会随根视图出现执行异步恢复逻辑，不阻塞首屏渲染。
                .task {
                    await session.restoreSession()
                }
                .onChange(of: scenePhase) { _, newPhase in
                    // SwiftUI 统一将前后台变化交给 Store，业务页面只关心是否展示记录控制。
                    tracking.handleScenePhase(newPhase)
                }
        }
    }
}
