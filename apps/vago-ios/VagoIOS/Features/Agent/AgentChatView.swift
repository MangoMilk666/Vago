import Foundation
import SwiftUI

/// iOS Agent 入口：复用 Web 已使用的持久化会话与 SSE，不在客户端实现 Agent Runtime。
struct AgentChatView: View {
    @EnvironmentObject private var session: SessionStore
    @StateObject private var viewModel = AgentChatViewModel()
    @State private var input = ""
    @State private var isConversationListPresented = false
    @FocusState private var isInputFocused: Bool

    var body: some View {
        ZStack(alignment: .leading) {
            NavigationStack {
                VStack(spacing: 0) {
                    conversationHeader
                    Divider()
                    messageList
                }
                .navigationTitle("Vago Agent")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button { withAnimation { isConversationListPresented = true } } label: {
                            Image(systemName: "sidebar.left")
                        }
                        .accessibilityLabel("打开对话侧栏")
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button { viewModel.startNewConversation() } label: {
                            Image(systemName: "square.and.pencil")
                        }
                        .disabled(viewModel.isStreaming)
                        .accessibilityLabel("新对话")
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Menu {
                            Toggle("使用旅行上下文", isOn: $viewModel.usePersonalContext)
                            Toggle("使用个人资料", isOn: $viewModel.useRag)
                        } label: {
                            Image(systemName: "slider.horizontal.3")
                        }
                        .accessibilityLabel("Agent 上下文设置")
                    }
                }
                .safeAreaInset(edge: .bottom) { composer }
                .task(id: session.profile?.uuid) {
                    await viewModel.loadConversations(session: session)
                }
                .alert("Agent 对话提示", isPresented: Binding(
                    get: { !viewModel.errorMessage.isEmpty },
                    set: { if !$0 { viewModel.errorMessage = "" } }
                )) {
                    Button("好的", role: .cancel) {}
                } message: {
                    Text(viewModel.errorMessage)
                }
            }

            if isConversationListPresented {
                Color.black.opacity(0.24)
                    .ignoresSafeArea()
                    .onTapGesture { withAnimation { isConversationListPresented = false } }
                ConversationSidebar(
                    conversations: viewModel.conversations,
                    activeConversationUuid: viewModel.activeConversation?.uuid,
                    isStreaming: viewModel.isStreaming,
                    onClose: { withAnimation { isConversationListPresented = false } },
                    onNewConversation: {
                        viewModel.startNewConversation()
                        withAnimation { isConversationListPresented = false }
                    },
                    onSelect: { conversation in
                        Task {
                            await viewModel.selectConversation(conversation, session: session)
                            withAnimation { isConversationListPresented = false }
                        }
                    },
                    onRename: { conversation, title in
                        Task { await viewModel.renameConversation(conversation, title: title, session: session) }
                    },
                    onDelete: { conversation in
                        Task { await viewModel.deleteConversation(conversation, session: session) }
                    }
                )
                .frame(width: min(UIScreen.main.bounds.width * 0.84, 340))
                .frame(maxHeight: .infinity, alignment: .leading)
                .transition(.move(edge: .leading).combined(with: .opacity))
            }
        }
        .animation(.easeInOut(duration: 0.2), value: isConversationListPresented)
    }

    private var conversationHeader: some View {
        HStack(spacing: 10) {
            Image(systemName: "sparkles")
                .foregroundStyle(.indigo)
            VStack(alignment: .leading, spacing: 2) {
                Text(viewModel.activeConversation?.title ?? "新对话")
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                Text("经授权后参考你的旅行事实与个人资料")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(.thinMaterial)
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    if let nextBeforeUuid = viewModel.nextBeforeUuid {
                        Button(viewModel.isLoadingMessages ? "正在读取历史记录" : "加载更早消息") {
                            Task { await viewModel.loadOlderMessages(beforeUuid: nextBeforeUuid, session: session) }
                        }
                        .font(.caption)
                        .frame(maxWidth: .infinity)
                        .disabled(viewModel.isLoadingMessages || viewModel.isStreaming)
                    }

                    if viewModel.messages.isEmpty && !viewModel.isLoadingMessages {
                        AgentEmptyState { suggestion in
                            input = suggestion
                            isInputFocused = true
                        }
                        .frame(maxWidth: .infinity, minHeight: 360)
                    }

                    ForEach(viewModel.messages) { message in
                        AgentMessageBubble(message: message)
                            .id(message.id)
                    }
                    Color.clear.frame(height: 2).id("agent-bottom")
                }
                .padding()
            }
            // 用户向下拖动消息区域时按原生交互渐进收起键盘，地图/聊天等长页面都可复用这项行为。
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: viewModel.messages.count) { _, _ in
                withAnimation { proxy.scrollTo("agent-bottom", anchor: .bottom) }
            }
            .onChange(of: viewModel.streamingTextRevision) { _, _ in
                proxy.scrollTo("agent-bottom", anchor: .bottom)
            }
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("问问当前行程、旅行记录或下一步安排", text: $input, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...5)
                .focused($isInputFocused)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color(uiColor: .secondarySystemBackground), in: RoundedRectangle(cornerRadius: 18))
                .submitLabel(.send)
                .onSubmit { send() }
            Button(action: send) {
                Image(systemName: viewModel.isStreaming ? "hourglass" : "arrow.up")
                    .font(.headline)
                    .frame(width: 36, height: 36)
                    .foregroundStyle(.white)
                    .background(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isStreaming ? Color.gray : Color.indigo, in: Circle())
            }
            .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isStreaming)
            .accessibilityLabel("发送消息")
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(.bar)
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        input = ""
        // 发送后立即让输入框失焦，避免用户在等待长回答时仍被键盘遮挡内容。
        isInputFocused = false
        Task {
            await viewModel.send(message: text, session: session)
        }
    }
}

@MainActor
private final class AgentChatViewModel: ObservableObject {
    @Published private(set) var conversations: [AgentConversation] = []
    @Published private(set) var activeConversation: AgentConversation?
    @Published private(set) var messages: [AgentDisplayMessage] = []
    @Published private(set) var nextBeforeUuid: String?
    @Published private(set) var isLoadingMessages = false
    @Published private(set) var isStreaming = false
    @Published var useRag = true
    @Published var usePersonalContext = true
    @Published var errorMessage = ""
    @Published private(set) var streamingTextRevision = 0

    private let client = APIClient()
    private var loadedUserUuid: String?

    func loadConversations(session: SessionStore) async {
        guard let userUuid = session.profile?.uuid, loadedUserUuid != userUuid else { return }
        loadedUserUuid = userUuid
        // 分支条件：切换账号后先清空旧账号的会话内存，网络请求返回前也不能短暂展示他人的聊天记录。
        conversations = []
        activeConversation = nil
        messages = []
        nextBeforeUuid = nil
        do {
            let conversations: [AgentConversation] = try await client.request(path: "agent/conversations", tokenProvider: session)
            self.conversations = conversations
            // 分支条件：首次进入 Agent 时自动恢复最近活跃会话；没有历史则保留空白新对话。
            if let first = conversations.first {
                await selectConversation(first, session: session)
            }
        } catch {
            errorMessage = "暂时无法读取对话列表：\(error.localizedDescription)"
        }
    }

    func startNewConversation() {
        guard !isStreaming else { return }
        activeConversation = nil
        messages = []
        nextBeforeUuid = nil
        useRag = true
        usePersonalContext = true
    }

    func selectConversation(_ conversation: AgentConversation, session: SessionStore) async {
        guard !isStreaming, activeConversation?.uuid != conversation.uuid else { return }
        activeConversation = conversation
        useRag = conversation.useRag
        usePersonalContext = conversation.usePersonalContext
        messages = []
        nextBeforeUuid = nil
        await loadMessages(conversationUuid: conversation.uuid, beforeUuid: nil, session: session)
    }

    func loadOlderMessages(beforeUuid: String, session: SessionStore) async {
        guard let conversationUuid = activeConversation?.uuid, !isStreaming else { return }
        await loadMessages(conversationUuid: conversationUuid, beforeUuid: beforeUuid, session: session)
    }

    func renameConversation(_ conversation: AgentConversation, title: String, session: SessionStore) async {
        let normalizedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedTitle.isEmpty else { return }
        do {
            let updated: AgentConversation = try await client.request(
                path: "agent/conversations/\(conversation.uuid)",
                method: "PATCH",
                body: AgentConversationUpdateRequest(title: normalizedTitle),
                tokenProvider: session
            )
            replaceConversation(updated)
        } catch {
            errorMessage = "更新对话标题失败：\(error.localizedDescription)"
        }
    }

    func deleteConversation(_ conversation: AgentConversation, session: SessionStore) async {
        guard !isStreaming else { return }
        do {
            try await client.requestWithoutResponse(
                path: "agent/conversations/\(conversation.uuid)",
                method: "DELETE",
                body: EmptyAgentRequest(),
                tokenProvider: session
            )
            conversations.removeAll { $0.uuid == conversation.uuid }
            // 分支条件：删除当前会话后回到空白状态，避免页面继续展示已被服务端删除的历史。
            if activeConversation?.uuid == conversation.uuid {
                startNewConversation()
            }
        } catch {
            errorMessage = "删除对话失败：\(error.localizedDescription)"
        }
    }

    func send(message: String, session: SessionStore) async {
        guard !isStreaming else { return }
        do {
            let conversation = try await ensureConversation(session: session)
            let history = messages
                .filter { !$0.isError && !$0.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
                .map { AgentChatMessage(role: $0.role, content: $0.content) }
            let request = AgentChatStreamRequest(
                messages: history + [AgentChatMessage(role: "user", content: message)],
                useRag: useRag,
                usePersonalContext: usePersonalContext,
                conversationUuid: conversation.uuid
            )
            let localAssistantId = "stream-\(UUID().uuidString)"
            messages.append(AgentDisplayMessage(id: "local-\(UUID().uuidString)", role: "user", content: message))
            messages.append(AgentDisplayMessage(id: localAssistantId, role: "assistant", content: "", isStreaming: true, isTraceRunning: true))
            isStreaming = true
            defer {
                isStreaming = false
                markLocalAssistantFinished(id: localAssistantId)
            }

            let bytes = try await client.openEventStream(
                path: "ai/chat/stream",
                body: request,
                tokenProvider: session
            )
            var streamContainsError = false
            for try await line in bytes.lines {
                guard line.hasPrefix("data:") else { continue }
                let rawEvent = String(line.dropFirst(5)).trimmingCharacters(in: .whitespaces)
                if rawEvent == "[DONE]" { break }
                guard let data = rawEvent.data(using: .utf8), let event = try? JSONDecoder().decode(AgentEvent.self, from: data) else { continue }
                if event.type == "error" { streamContainsError = true }
                consume(event, for: localAssistantId)
                // 分支条件：Runtime 读取非常快时，iOS 仍以短间隔播放公开事件，避免 UI 一次性刷出完整轨迹。
                if event.type.hasPrefix("agent.") || event.type.hasPrefix("tool.") {
                    try? await Task.sleep(for: .milliseconds(180))
                }
            }
            // SSE 完成时服务端已写入历史；重新读取可得到真实 UUID、自动标题与事件回放数据。
            // 分支条件：服务端已明确发送生成错误时不刷新覆盖本地提示；成功流才以持久化历史为准。
            if !streamContainsError {
                await refreshAfterStream(conversationUuid: conversation.uuid, session: session)
            }
        } catch {
            appendEvent(AgentEvent(type: "agent.failed", label: "本轮 Agent 请求未能完成"), to: lastStreamingMessageID)
            updateLastStreamingMessage { message in
                message.content = message.content.isEmpty ? "连接失败：\(error.localizedDescription)" : message.content
                message.isError = true
            }
        }
    }

    private var lastStreamingMessageID: String? {
        messages.last(where: { $0.isStreaming })?.id
    }

    private func loadMessages(conversationUuid: String, beforeUuid: String?, session: SessionStore) async {
        isLoadingMessages = true
        defer { isLoadingMessages = false }
        do {
            let suffix = beforeUuid.map { "?beforeUuid=\($0)" } ?? ""
            let page: AgentConversationMessagePage = try await client.request(
                path: "agent/conversations/\(conversationUuid)/messages\(suffix)",
                tokenProvider: session
            )
            let restored = page.messages.map(AgentDisplayMessage.init)
            // 分支条件：带游标的是更早历史，必须插在现有消息之前保持时间顺序。
            messages = beforeUuid == nil ? restored : restored + messages
            nextBeforeUuid = page.nextBeforeUuid
        } catch {
            errorMessage = "读取对话记录失败：\(error.localizedDescription)"
        }
    }

    private func ensureConversation(session: SessionStore) async throws -> AgentConversation {
        if let activeConversation { return activeConversation }
        let conversation: AgentConversation = try await client.request(
            path: "agent/conversations",
            method: "POST",
            body: AgentConversationCreateRequest(useRag: useRag, usePersonalContext: usePersonalContext),
            tokenProvider: session
        )
        activeConversation = conversation
        conversations.insert(conversation, at: 0)
        return conversation
    }

    private func consume(_ event: AgentEvent, for messageID: String) {
        if event.type.hasPrefix("agent.") || event.type.hasPrefix("tool.") {
            appendEvent(event, to: messageID)
        } else if event.type == "text", let content = event.content {
            updateMessage(id: messageID) { message in
                message.content += content
            }
            streamingTextRevision += 1
        } else if event.type == "sources", let sources = event.sources {
            updateMessage(id: messageID) { message in message.sources = sources }
        } else if event.type == "context", let labels = event.labels {
            updateMessage(id: messageID) { message in message.contextLabels = labels }
        } else if event.type == "error" {
            updateMessage(id: messageID) { message in
                message.content = event.message ?? "AI 生成失败"
                message.isError = true
            }
        }
    }

    private func appendEvent(_ event: AgentEvent, to messageID: String?) {
        guard let messageID else { return }
        updateMessage(id: messageID) { message in
            message.events.append(event)
            if event.type == "agent.completed" || event.type == "agent.failed" {
                message.isTraceRunning = false
            }
        }
    }

    private func updateLastStreamingMessage(_ update: (inout AgentDisplayMessage) -> Void) {
        guard let messageID = lastStreamingMessageID else { return }
        updateMessage(id: messageID, update)
    }

    private func updateMessage(id: String, _ update: (inout AgentDisplayMessage) -> Void) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
        update(&messages[index])
    }

    private func markLocalAssistantFinished(id: String) {
        updateMessage(id: id) { message in
            message.isStreaming = false
            message.isTraceRunning = false
        }
    }

    private func refreshAfterStream(conversationUuid: String, session: SessionStore) async {
        do {
            let latest: [AgentConversation] = try await client.request(path: "agent/conversations", tokenProvider: session)
            conversations = latest
            if let updated = latest.first(where: { $0.uuid == conversationUuid }) {
                activeConversation = updated
            }
            await loadMessages(conversationUuid: conversationUuid, beforeUuid: nil, session: session)
        } catch {
            // 回答已在本地完整显示时，刷新失败不覆盖它，只提示历史可能尚未同步。
            errorMessage = "回答已生成，但刷新会话记录失败：\(error.localizedDescription)"
        }
    }

    private func replaceConversation(_ updated: AgentConversation) {
        if let index = conversations.firstIndex(where: { $0.uuid == updated.uuid }) {
            conversations[index] = updated
        }
        if activeConversation?.uuid == updated.uuid {
            activeConversation = updated
        }
    }
}

/// Agent 页面专用展示模型；流式中的临时状态不写入服务端消息 DTO。
private struct AgentDisplayMessage: Identifiable {
    let id: String
    let role: String
    var content: String
    var sources: [AgentSource] = []
    var contextLabels: [String] = []
    var events: [AgentEvent] = []
    var isStreaming = false
    var isTraceRunning = false
    var isError = false

    init(id: String, role: String, content: String, isStreaming: Bool = false, isTraceRunning: Bool = false) {
        self.id = id
        self.role = role
        self.content = content
        self.isStreaming = isStreaming
        self.isTraceRunning = isTraceRunning
    }

    init(_ message: AgentConversationMessage) {
        id = message.uuid
        role = message.role
        content = message.content
        sources = message.sources
        contextLabels = message.contextLabels
        events = message.agentEvents
    }
}

/// DELETE 接口不关心请求 body；保留空结构体即可沿用当前 APIClient 的通用认证请求方法。
private struct EmptyAgentRequest: Encodable {}

private struct AgentMessageBubble: View {
    let message: AgentDisplayMessage

    var body: some View {
        VStack(alignment: message.role == "user" ? .trailing : .leading, spacing: 8) {
            if message.role == "assistant", !message.events.isEmpty {
                AgentActivityTrace(events: message.events, isRunning: message.isTraceRunning)
            }
            HStack {
                if message.role == "user" { Spacer(minLength: 46) }
                VStack(alignment: .leading, spacing: 8) {
                    if !message.content.isEmpty {
                        MarkdownMessageText(content: message.content)
                    } else if message.isStreaming {
                        ProgressView().controlSize(.small)
                    }
                    if !message.contextLabels.isEmpty {
                        Text(message.contextLabels.joined(separator: " · "))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    if !message.sources.isEmpty {
                        Divider()
                        ForEach(message.sources) { source in
                            Label(source.title, systemImage: "doc.text")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(12)
                .foregroundStyle(message.role == "user" ? Color.white : Color.primary)
                .background(message.role == "user" ? Color.indigo : Color(uiColor: .secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16))
                if message.role != "user" { Spacer(minLength: 24) }
            }
        }
    }
}

/// 将常用 Markdown 行结构转成 SwiftUI 视图，行内强调、链接等由 AttributedString 的 Markdown 解析完成。
private struct MarkdownMessageText: View {
    let content: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(content.components(separatedBy: "\n").enumerated()), id: \.offset) { _, line in
                markdownLine(line)
            }
        }
        .textSelection(.enabled)
    }

    @ViewBuilder
    private func markdownLine(_ line: String) -> some View {
        if line.hasPrefix("### ") {
            markdownText(String(line.dropFirst(4))).font(.headline)
        } else if line.hasPrefix("## ") {
            markdownText(String(line.dropFirst(3))).font(.title3.weight(.semibold))
        } else if line.hasPrefix("# ") {
            markdownText(String(line.dropFirst(2))).font(.title2.weight(.bold))
        } else if line.hasPrefix("- ") || line.hasPrefix("* ") {
            HStack(alignment: .top, spacing: 6) {
                Text("•")
                markdownText(String(line.dropFirst(2)))
            }
        } else if line.hasPrefix("> ") {
            markdownText(String(line.dropFirst(2)))
                .italic()
                .padding(.leading, 8)
                .overlay(alignment: .leading) { Rectangle().fill(.indigo.opacity(0.45)).frame(width: 3) }
        } else if !line.isEmpty {
            markdownText(line)
        } else {
            Spacer().frame(height: 3)
        }
    }

    private func markdownText(_ text: String) -> Text {
        let attributed = (try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(text)
        return Text(attributed)
    }
}

private struct AgentActivityTrace: View {
    let events: [AgentEvent]
    let isRunning: Bool
    @State private var isExpanded = true

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 7) {
                ForEach(Array(events.enumerated()), id: \.offset) { _, event in
                    HStack(alignment: .top, spacing: 7) {
                        Image(systemName: event.type.hasSuffix("failed") ? "exclamationmark.circle" : event.type.hasSuffix("completed") ? "checkmark.circle.fill" : "circle.dotted")
                            .foregroundStyle(event.type.hasSuffix("failed") ? .orange : .indigo)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(event.label ?? "正在处理旅行上下文")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.leading)
                            // 分支条件：服务端事件属于领域工具调用时显示稳定工具名，方便联调核对真实调用边界。
                            if let tool = event.tool {
                                Text(tool)
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(.tertiary)
                            }
                        }
                        Spacer(minLength: 0)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(.top, 6)
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "sparkles")
                Text(isRunning ? "正在整理旅行上下文" : "本轮 Agent 执行记录")
                Spacer()
                Text("\(events.count)").font(.caption2.monospacedDigit())
            }
            .font(.caption.weight(.medium))
            .foregroundStyle(.indigo)
        }
        .padding(10)
        .background(.indigo.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
        .frame(maxWidth: .infinity, alignment: .leading)
        .onChange(of: isRunning) { _, running in
            // 分支条件：生成中自动展开便于观察；完成后默认收起，用户仍可自行展开回看。
            if running { isExpanded = true } else { isExpanded = false }
        }
    }
}

private struct AgentEmptyState: View {
    let onSuggestion: (String) -> Void

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "sparkles")
                .font(.system(size: 30))
                .foregroundStyle(.indigo)
            Text("和 Vago Agent 一起协调旅行")
                .font(.headline)
            Text("它会在你的授权范围内读取旅行事实与个人资料，不会自行修改行程。")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            ForEach([
                "总结我当前行程已完成和待安排的内容",
                "我有点累了，接下来四小时可以怎样安排？"
            ], id: \.self) { suggestion in
                Button(suggestion) { onSuggestion(suggestion) }
                    .font(.subheadline)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color(uiColor: .secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
            }
        }
        .padding(28)
    }
}

/// iPhone 上模仿 ChatGPT 的左侧会话抽屉；它覆盖主页面但不取代 iPad 的系统 sidebar 架构。
private struct ConversationSidebar: View {
    let conversations: [AgentConversation]
    let activeConversationUuid: String?
    let isStreaming: Bool
    let onClose: () -> Void
    let onNewConversation: () -> Void
    let onSelect: (AgentConversation) -> Void
    let onRename: (AgentConversation, String) -> Void
    let onDelete: (AgentConversation) -> Void
    @State private var editingConversation: AgentConversation?
    @State private var titleDraft = ""
    @State private var deletingConversation: AgentConversation?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Agent 对话", systemImage: "brain.head.profile")
                    .font(.headline)
                Spacer()
                Button(action: onClose) { Image(systemName: "xmark") }
                    .accessibilityLabel("关闭对话侧栏")
            }
            Button(action: onNewConversation) {
                Label("新对话", systemImage: "square.and.pencil")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(isStreaming)

            Text("近期对话")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            ScrollView {
                LazyVStack(spacing: 4) {
                    ForEach(conversations) { conversation in
                        HStack(spacing: 8) {
                            Button { onSelect(conversation) } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(conversation.title).lineLimit(1)
                                    Text(conversation.updatedAt.formatted(date: .abbreviated, time: .shortened))
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                            }
                            if conversation.uuid == activeConversationUuid {
                                Image(systemName: "checkmark").foregroundStyle(.indigo)
                            }
                            Menu {
                                Button { beginRename(conversation) } label: { Label("重命名", systemImage: "pencil") }
                                Button(role: .destructive) { deletingConversation = conversation } label: { Label("删除", systemImage: "trash") }
                            } label: {
                                Image(systemName: "ellipsis")
                                    .frame(width: 28, height: 28)
                            }
                            .accessibilityLabel("管理对话")
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 8)
                        .background(conversation.uuid == activeConversationUuid ? Color.indigo.opacity(0.12) : Color.clear, in: RoundedRectangle(cornerRadius: 10))
                    }
                }
            }
        }
        .padding(.top, 18)
        .padding(.horizontal, 16)
        .padding(.bottom, 12)
        .background(.regularMaterial)
        .ignoresSafeArea(edges: .vertical)
        .alert("重命名对话", isPresented: Binding(get: { editingConversation != nil }, set: { if !$0 { editingConversation = nil } })) {
            TextField("对话标题", text: $titleDraft)
            Button("保存") {
                if let editingConversation { onRename(editingConversation, titleDraft) }
                editingConversation = nil
            }
            Button("取消", role: .cancel) { editingConversation = nil }
        }
        .confirmationDialog("删除这段对话？", isPresented: Binding(get: { deletingConversation != nil }, set: { if !$0 { deletingConversation = nil } })) {
            Button("删除", role: .destructive) {
                if let deletingConversation { onDelete(deletingConversation) }
                deletingConversation = nil
            }
            Button("取消", role: .cancel) { deletingConversation = nil }
        } message: {
            Text("删除后无法恢复这段对话及其消息记录。")
        }
    }

    private func beginRename(_ conversation: AgentConversation) {
        titleDraft = conversation.title
        editingConversation = conversation
    }
}
