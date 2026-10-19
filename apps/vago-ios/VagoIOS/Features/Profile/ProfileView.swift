import SwiftUI

struct ProfileView: View {
    // 个人页不保存用户副本，始终从共享 SessionStore 读取最新 profile。
    @EnvironmentObject private var session: SessionStore
    @Environment(\.appTheme) private var theme
    @Environment(\.colorScheme) private var colorScheme
    @AppStorage("vago.appearance.theme") private var selectedTheme: AppTheme = .indigo
    @AppStorage("vago.appearance.mode") private var selectedAppearance: AppAppearance = .system
    @State private var isLoggingOut = false
    @State private var isLogoutConfirmationPresented = false

    var body: some View {
        // List 采用系统分组列表样式，Section 用于形成账号信息与危险操作的视觉边界。
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 14) {
                        Image(systemName: "person.crop.circle.fill").font(.system(size: 52)).foregroundStyle(theme.accent)
                        VStack(alignment: .leading) {
                            // ?? 是 nil 合并运算符：服务端资料尚未到达时使用本地兜底文案。
                            Text(session.profile?.nickname ?? "旅行者").font(.headline)
                            Text(session.profile?.phone ?? session.profile?.email ?? "Vago 用户").foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 6)
                }
                Section("外观") {
                    Picker("外观模式", selection: $selectedAppearance) {
                        ForEach(AppAppearance.allCases) { option in
                            Text(option.title).tag(option)
                        }
                    }
                    .accessibilityHint("选择跟随系统、日间模式或夜间模式")
                    NavigationLink {
                        ThemeSelectionView(selection: $selectedTheme)
                    } label: {
                        HStack {
                            Text("主题配色")
                            Spacer()
                            Text(selectedTheme.title).foregroundStyle(.secondary)
                        }
                    }
                    .accessibilityHint("切换应用背景、按钮和地图轨迹颜色")
                }
                Section("账户") {
                    Button("退出登录", role: .destructive) { isLogoutConfirmationPresented = true }
                        .disabled(isLoggingOut)
                }
            }
            .scrollContentBackground(.hidden)
            .background(theme.background(for: colorScheme))
            .navigationTitle("我的")
        }
        .alert("确认退出登录？", isPresented: $isLogoutConfirmationPresented) {
            Button("取消", role: .cancel) {}
            Button("退出登录", role: .destructive) { Task { await logout() } }
        } message: {
            Text("你的数据将会被保留，退出后需重新登录 Vago。")
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

private struct ThemeSelectionView: View {
    @Binding var selection: AppTheme
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        List {
            ForEach(AppTheme.allCases) { option in
                Button {
                    selection = option
                } label: {
                    HStack(spacing: 14) {
                        // 自行绘制预览，避免系统菜单将所有图标统一染成当前主题色。
                        ZStack {
                            RoundedRectangle(cornerRadius: 10)
                                .fill(option.background(for: colorScheme))
                            Capsule()
                                .fill(option.route)
                                .frame(width: 38, height: 5)
                                .offset(y: 6)
                            Circle()
                                .fill(option.checkin)
                                .frame(width: 11, height: 11)
                                .offset(x: 15, y: -8)
                        }
                        .frame(width: 64, height: 42)
                        .overlay {
                            RoundedRectangle(cornerRadius: 10)
                                .strokeBorder(.secondary.opacity(0.18), lineWidth: 1)
                        }
                        Text(option.title)
                        Spacer()
                        if selection == option {
                            Image(systemName: "checkmark")
                                .fontWeight(.semibold)
                                .foregroundStyle(option.accent)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(option.title)
                .accessibilityValue(selection == option ? "已选择" : "未选择")
            }
        }
        .themedScrollBackground()
        .navigationTitle("主题配色")
        .navigationBarTitleDisplayMode(.inline)
    }
}
