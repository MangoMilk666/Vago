import SwiftUI

struct RootView: View {
    // @EnvironmentObject 从根视图注入的共享状态中读取当前认证状态。
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var tracking: LocationTrackingStore

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
        .onChange(of: session.profile?.uuid) { _, userUuid in
            // 分支条件：退出登录后清理旧账号的内存定位状态，UserDefaults 待传队列仍按账号保留。
            if userUuid == nil {
                tracking.reset()
            }
        }
    }
}

private struct MainTabView: View {
    // 内部枚举避免用容易写错的字符串表示 Tab；Hashable 是 TabView(selection:) 的绑定值要求。
    private enum Tab: Hashable {
        case trip
        case footprint
        case profile
    }

    // 显式保存选中标签，避免子视图加载状态变化时 TabView 恢复到默认页。
    @State private var selectedTab: Tab = .trip

    var body: some View {
        // $selectedTab 是 @State 的 Binding 投影值，TabView 可通过它读写当前选中项。
        TabView(selection: $selectedTab) {
            // TabView 是 iOS 原生底部标签导航，移动端只保留旅行中的高频入口。
            CurrentTripView()
                .tabItem { Label("行程", systemImage: "map") }
                .tag(Tab.trip)
            TrackingView()
                .tabItem { Label("记录", systemImage: "location") }
                .tag(Tab.footprint)
            ProfileView()
                .tabItem { Label("我的", systemImage: "person.crop.circle") }
                .tag(Tab.profile)
        }
        // TabView 显式扩展到安全区域内的最大尺寸，适配不同 iPhone 的屏幕高度。
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
