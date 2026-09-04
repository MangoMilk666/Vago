import SwiftUI

@main
struct VagoIOSApp: App {
    // @StateObject 让根视图拥有唯一的会话对象；视图重绘不会重新创建登录状态。
    @StateObject private var session = SessionStore()

    var body: some Scene {
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
