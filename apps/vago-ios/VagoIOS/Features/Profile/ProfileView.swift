import SwiftUI

struct ProfileView: View {
    @EnvironmentObject private var session: SessionStore
    @State private var isLoggingOut = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 14) {
                        Image(systemName: "person.crop.circle.fill").font(.system(size: 52)).foregroundStyle(.indigo)
                        VStack(alignment: .leading) {
                            Text(session.profile?.nickname ?? "旅行者").font(.headline)
                            Text(session.profile?.phone ?? session.profile?.email ?? "Vago 用户").foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 6)
                }
                Section("账户") {
                    Button("退出登录", role: .destructive) { Task { await logout() } }
                        .disabled(isLoggingOut)
                }
            }
            .navigationTitle("我的")
        }
    }

    private func logout() async {
        // 服务端注销失败也清理本机 Keychain，避免用户误以为仍处于退出状态。
        isLoggingOut = true
        await session.logout()
        isLoggingOut = false
    }
}
