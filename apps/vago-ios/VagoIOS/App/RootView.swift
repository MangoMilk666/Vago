import SwiftUI

struct RootView: View {
    // @EnvironmentObject 从根视图注入的共享状态中读取当前认证状态。
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        Group {
            // SwiftUI 根据状态声明 UI；state 变化后 body 会自动重新计算，无需手动刷新页面。
            switch session.state {
            case .launching:
                ProgressView()
                    .controlSize(.large)
            case .signedOut:
                LoginView()
            case .signedIn:
                MainTabView()
            }
        }
        .tint(.indigo)
        // 根容器始终占用 WindowGroup 提供的完整可用区域，避免首屏内容的固有尺寸压缩 TabView。
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct MainTabView: View {
    var body: some View {
        TabView {
            // TabView 是 iOS 原生底部标签导航，移动端只保留旅行中的高频入口。
            CurrentTripView()
                .tabItem { Label("行程", systemImage: "map") }
            TrackingView()
                .tabItem { Label("记录", systemImage: "location") }
            ProfileView()
                .tabItem { Label("我的", systemImage: "person.crop.circle") }
        }
        // TabView 显式扩展到安全区域内的最大尺寸，适配不同 iPhone 的屏幕高度。
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
