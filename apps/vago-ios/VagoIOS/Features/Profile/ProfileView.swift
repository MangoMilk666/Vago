import SwiftUI

struct ProfileView: View {
    // 个人页不保存用户副本，始终从共享 SessionStore 读取最新 profile。
    @EnvironmentObject private var session: SessionStore
    @State private var isLoggingOut = false

    var body: some View {
        // List 采用系统分组列表样式，Section 用于形成账号信息与危险操作的视觉边界。
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 14) {
                        Image(systemName: "person.crop.circle.fill").font(.system(size: 52)).foregroundStyle(.indigo)
                        VStack(alignment: .leading) {
                            // ?? 是 nil 合并运算符：服务端资料尚未到达时使用本地兜底文案。
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
        // UI 只等待会话层完成清理；SessionStore 无论服务端注销结果如何都会移除本机 token。
        // 服务端注销失败也清理本机 Keychain，避免用户误以为仍处于退出状态。
        isLoggingOut = true
        await session.logout()
        isLoggingOut = false
    }
}
