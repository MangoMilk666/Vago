import SwiftUI

struct LoginView: View {
    // @State 是页面私有的可变状态；输入变化时 SwiftUI 自动更新对应控件。
    @EnvironmentObject private var session: SessionStore
    @State private var phone = ""
    @State private var code = ""
    @State private var isSubmitting = false
    @State private var isSendingCode = false
    @State private var message = ""
    @State private var messageIsError = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 28) {
                Spacer()
                Image(systemName: "location.circle.fill")
                    .font(.system(size: 58))
                    .foregroundStyle(.indigo)
                Text("Vago")
                    .font(.largeTitle.bold())
                Text("把每一段旅程，留在自己的坐标里。")
                    .font(.title3)
                    .foregroundStyle(.secondary)
                VStack(spacing: 14) {
                    TextField("手机号", text: $phone)
                        .keyboardType(.phonePad)
                        .textContentType(.telephoneNumber)
                        .textFieldStyle(.roundedBorder)
                    HStack {
                        TextField("验证码", text: $code)
                            .keyboardType(.numberPad)
                            .textContentType(.oneTimeCode)
                            .textFieldStyle(.roundedBorder)
                        Button(isSendingCode ? "发送中" : "获取验证码") {
                            // Task 将 async 函数桥接到按钮点击事件，不需要手动创建线程。
                            Task { await sendCode() }
                        }
                        .buttonStyle(.bordered)
                        .disabled(phone.isEmpty || isSendingCode)
                    }
                    if !message.isEmpty {
                        Text(message).font(.footnote).foregroundStyle(messageIsError ? .red : .secondary)
                    }
                    Button {
                        Task { await signIn() }
                    } label: {
                        if isSubmitting { ProgressView().frame(maxWidth: .infinity) }
                        else { Text("登录").frame(maxWidth: .infinity) }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(phone.isEmpty || code.isEmpty || isSubmitting)
                }
                Text("登录即表示你同意 Vago 的服务条款与隐私政策。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                Spacer()
            }
            .padding(28)
        }
    }

    private func signIn() async {
        isSubmitting = true
        message = ""
        messageIsError = false
        // defer 与 Python 的 finally 相似，保证请求成功或失败都会恢复按钮状态。
        defer { isSubmitting = false }
        do {
            try await session.login(phone: phone, code: code)
        } catch {
            message = error.localizedDescription
            messageIsError = true
        }
    }

    private func sendCode() async {
        isSendingCode = true
        message = ""
        messageIsError = false
        defer { isSendingCode = false }
        do {
            try await session.sendSMSCode(to: phone)
            message = "验证码已发送，请注意查收"
        } catch {
            message = error.localizedDescription
            messageIsError = true
        }
    }
}
