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
    }
}

private struct MainTabView: View {
    var body: some View {
        TabView {
            // TabView 是 iOS 原生底部标签导航，移动端只保留旅行中的高频入口。
            CurrentTripView()
                .tabItem { Label("行程", systemImage: "map") }
            ProfileView()
                .tabItem { Label("我的", systemImage: "person.crop.circle") }
        }
    }
}
