import SwiftUI

@main
struct VagoIOSApp: App {
    // @main 指定 iOS 应用的进程入口；App 协议相当于 SwiftUI 版本的 AppDelegate 配置入口。
    // @StateObject 让根视图拥有唯一的会话对象；视图重绘不会重新创建登录状态。
    @StateObject private var session = SessionStore()

    var body: some Scene {
        // Scene 表示一个系统窗口场景；当前 iPhone 应用只创建一个 WindowGroup。
        WindowGroup {
            RootView()
                // EnvironmentObject 类似在视图树中注入共享依赖，子页面可直接读取同一会话。
                .environmentObject(session)
                // .task 会随根视图出现执行异步恢复逻辑，不阻塞首屏渲染。
                .task {
                    await session.restoreSession()
                }
        }
    }
}
