import SwiftUI

struct LoginView: View {
    // View 是值类型描述，body 每次重算都可能产生新值；持久可变数据必须放在 @State 等属性包装器中。
    private enum InputField {
        // 枚举比 Bool 更适合表达“当前具体聚焦哪个输入框”。
        case phone
        case verificationCode
    }

    // @State 是页面私有的可变状态；输入变化时 SwiftUI 自动更新对应控件。
    // @EnvironmentObject 读取 App 根节点注入的共享会话，不需要逐层作为参数传递。
    @EnvironmentObject private var session: SessionStore
    @State private var phone = ""
    @State private var code = ""
    @State private var isSubmitting = false
    @State private var isSendingCode = false
    @State private var message = ""
    @State private var messageIsError = false
    // FocusState 统一管理输入焦点，以便数字键盘也能被页面主动收起。
    @FocusState private var focusedField: InputField?

    var body: some View {
        // NavigationStack 负责 iOS 原生导航栏与后续 push 栈；登录页当前只使用其容器能力。
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
                    // $phone 把 @State 投影为 Binding<String>，TextField 修改内容会反向写入 phone。
                    TextField("手机号", text: $phone)
                        .keyboardType(.phonePad)
                        .textContentType(.telephoneNumber)
                        .textFieldStyle(.roundedBorder)
                        .focused($focusedField, equals: .phone)
                        .submitLabel(.done)
                    HStack {
                        TextField("验证码", text: $code)
                            .keyboardType(.numberPad)
                            .textContentType(.oneTimeCode)
                            .textFieldStyle(.roundedBorder)
                            .focused($focusedField, equals: .verificationCode)
                            .submitLabel(.done)
                        Button(isSendingCode ? "发送中" : "获取验证码") {
                            // Task 将 async 函数桥接到按钮点击事件，不需要手动创建线程。
                            Task { await sendCode() }
                        }
                        .buttonStyle(.bordered)
                        .disabled(phone.isEmpty || isSendingCode)
                    }
                    // 分支条件：仅在请求成功或失败后渲染状态文案，首屏不预留空白区域。
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
            // 点击不属于输入控件的页面区域时，结束编辑并收起键盘。
            .contentShape(Rectangle())
            .onTapGesture { focusedField = nil }
            .onSubmit { focusedField = nil }
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("完成") {
                        // 数字键盘没有系统 Return 键，使用工具栏提供明确的收起入口。
                        focusedField = nil
                    }
                }
            }
        }
    }

    private func signIn() async {
        // 页面层负责 loading 与错误提示，实际登录、存储 token、切换根状态由 SessionStore 负责。
        focusedField = nil
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
        // 验证码发送与登录分别维护 loading，避免一个按钮的状态错误禁用另一个操作。
        focusedField = nil
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
