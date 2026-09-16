import SwiftUI

/// 行程 Tab 展示用户自己的正式行程，并把唯一“当前行程”同步给记录页。
struct CurrentTripView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var tripContext: TripContextStore
    @State private var isLoading = true
    @State private var errorMessage = ""
    @State private var createError = ""
    @State private var isCreatorPresented = false
    @State private var isCreating = false
    @State private var loadedUserUuid: String?
    private let client = APIClient()

    private var inProgressTrips: [Trip] { tripContext.trips.filter { $0.status == TripStatus.inProgress.rawValue } }
    private var notStartedTrips: [Trip] { tripContext.trips.filter { $0.status == TripStatus.notStarted.rawValue } }
    private var endedTrips: [Trip] { tripContext.trips.filter { $0.status == TripStatus.ended.rawValue } }

    var body: some View {
        NavigationStack {
            Group {
                if isLoading && tripContext.trips.isEmpty {
                    ProgressView("正在读取行程")
                } else if tripContext.trips.isEmpty {
                    ContentUnavailableView("暂无正式行程", systemImage: "suitcase", description: Text("创建或转换一份计划后，行程会在这里出现。"))
                } else {
                    List {
                        tripSection("进行中", trips: inProgressTrips)
                        tripSection("未开始", trips: notStartedTrips)
                        tripSection("已结束", trips: endedTrips)
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("行程")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { isCreatorPresented = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel("新增行程")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { await refresh() } } label: { Image(systemName: "arrow.clockwise") }
                        .accessibilityLabel("刷新行程列表")
                }
            }
            // task(id:) 仅在账号变化时触发，避免每次 Tab 重绘都重复请求 travel/trips。
            .task(id: session.profile?.uuid) { await loadInitially() }
            .sheet(isPresented: $isCreatorPresented) {
                TripCreatorSheet(isSaving: isCreating, errorMessage: $createError) { request in
                    Task { await createTrip(request) }
                }
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
            }
            .alert("暂时无法读取行程", isPresented: Binding(get: { !errorMessage.isEmpty }, set: { if !$0 { errorMessage = "" } })) {
                Button("好的", role: .cancel) {}
            } message: {
                Text(errorMessage)
            }
        }
    }

    @ViewBuilder
    private func tripSection(_ title: String, trips: [Trip]) -> some View {
        // 分支条件：空状态分类不渲染空 Section，避免列表出现没有内容的分组标题。
        if !trips.isEmpty {
            Section(title) {
                ForEach(trips) { trip in
                    NavigationLink {
                        TripDetailView(trip: trip)
                    } label: {
                        TripRow(trip: trip)
                    }
                }
            }
        }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let trips: [Trip] = try await client.request(path: "travel/trips", tokenProvider: session)
            guard let userUuid = session.profile?.uuid else { return }
            tripContext.replaceTrips(trips, for: userUuid)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func loadInitially() async {
        guard let userUuid = session.profile?.uuid, loadedUserUuid != userUuid else { return }
        loadedUserUuid = userUuid
        await load()
    }

    private func refresh() async {
        errorMessage = ""
        await load()
    }

    private func createTrip(_ request: TripCreateRequest) async {
        isCreating = true
        createError = ""
        defer { isCreating = false }
        do {
            let created: Trip = try await client.request(
                path: "travel/trips",
                method: "POST",
                body: request,
                tokenProvider: session
            )
            guard let userUuid = session.profile?.uuid else { return }
            // 新增行程只更新列表，不会自动开始定位或覆盖当前正在进行的行程。
            tripContext.upsert(created, for: userUuid)
            isCreatorPresented = false
        } catch {
            // 创建失败时保留表单和输入内容，由 Sheet 在原位置展示具体错误。
            createError = error.localizedDescription
        }
    }
}

/// 单个行程在列表中的摘要，不把状态只交给颜色表达，方便无障碍与快速扫描。
private struct TripRow: View {
    let trip: Trip

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(trip.title).font(.headline)
                Spacer()
                Text(TripStatus(rawValue: trip.status)?.title ?? "未知")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(statusColor)
            }
            if let destination = trip.destination, !destination.isEmpty {
                Label(destination, systemImage: "mappin.and.ellipse")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Text("\(trip.startDate.formatted(date: .abbreviated, time: .omitted)) - \(trip.endDate.formatted(date: .abbreviated, time: .omitted))")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 3)
    }

    private var statusColor: Color {
        switch TripStatus(rawValue: trip.status) {
        case .notStarted: return .orange
        case .inProgress: return .green
        case .ended: return .secondary
        case nil: return .red
        }
    }
}

/// 行程详情保留服务端的可编辑/只读边界，并提供这份行程对应的只读地图入口。
private struct TripDetailView: View {
    let initialTrip: Trip
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var tracking: LocationTrackingStore
    @EnvironmentObject private var tripContext: TripContextStore
    @State private var trip: Trip
    @State private var days: [ItineraryDay] = []
    @State private var isLoadingDays = true
    @State private var isSaving = false
    @State private var dayError = ""
    @State private var actionError = ""
    @State private var isEditorPresented = false
    @State private var isSwitchConfirmationPresented = false
    private let client = APIClient()

    init(trip: Trip) {
        initialTrip = trip
        _trip = State(initialValue: trip)
    }

    private var canEdit: Bool { trip.status != TripStatus.ended.rawValue }
    private var activeTrip: Trip? { tripContext.activeTrip }

    var body: some View {
        List {
            Section("行程信息") {
                LabeledContent("目的地", value: trip.destination?.isEmpty == false ? trip.destination! : "未设置")
                LabeledContent("日期") {
                    Text("\(trip.startDate.formatted(date: .abbreviated, time: .omitted)) - \(trip.endDate.formatted(date: .abbreviated, time: .omitted))")
                        .multilineTextAlignment(.trailing)
                }
                LabeledContent("状态", value: TripStatus(rawValue: trip.status)?.title ?? "未知")
            }

            Section("旅行记录") {
                NavigationLink {
                    TripMapDetailView(trip: trip)
                } label: {
                    Label("查看点位与轨迹", systemImage: "map")
                }
                Text("地图仅用于浏览这份行程的已同步观察数据，不会改变当前正在记录的行程。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            if canEdit {
                Section("行程操作") {
                    if trip.status == TripStatus.notStarted.rawValue {
                        Button(activeTrip == nil ? "开始并设为当前行程" : "切换为当前行程") {
                            // 分支条件：已有进行中行程时，切换会结束旧行程，必须先取得用户明确确认。
                            if activeTrip == nil {
                                Task { await startTrip() }
                            } else {
                                isSwitchConfirmationPresented = true
                            }
                        }
                        .disabled(isSaving)
                    } else if trip.status == TripStatus.inProgress.rawValue {
                        Button("结束行程", role: .destructive) {
                            Task { await finishTrip() }
                        }
                        .disabled(isSaving)
                    }
                }
            }

            Section("每日安排") {
                if isLoadingDays {
                    ProgressView()
                } else if !dayError.isEmpty {
                    ContentUnavailableView("暂时无法读取日程", systemImage: "exclamationmark.icloud", description: Text(dayError))
                } else if days.isEmpty {
                    Text("暂未安排日程").foregroundStyle(.secondary)
                } else {
                    ForEach(days) { day in
                        NavigationLink { ItineraryDayView(day: day) } label: {
                            VStack(alignment: .leading) {
                                Text("第 \(day.dayIndex) 天 · \(day.dayDate.formatted(date: .abbreviated, time: .omitted))")
                                Text(day.spots.map(\.name).joined(separator: " · ").isEmpty ? "暂未安排地点" : day.spots.map(\.name).joined(separator: " · "))
                                    .font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(trip.title)
        .toolbar {
            if canEdit {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { isEditorPresented = true } label: { Image(systemName: "pencil") }
                        .accessibilityLabel("编辑行程")
                }
            }
        }
        .task(id: initialTrip.uuid) { await loadDays() }
        .sheet(isPresented: $isEditorPresented) {
            TripEditorSheet(trip: trip, isSaving: isSaving) { request in
                Task { await updateTrip(request) }
            }
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
        }
        .alert("切换当前行程？", isPresented: $isSwitchConfirmationPresented) {
            Button("取消", role: .cancel) {}
            Button("结束并切换", role: .destructive) { Task { await switchActiveTrip() } }
        } message: {
            Text("“\(activeTrip?.title ?? "当前行程")”会立即结束并进入历史记录，之后不可再编辑。")
        }
        .alert("行程操作失败", isPresented: Binding(get: { !actionError.isEmpty }, set: { if !$0 { actionError = "" } })) {
            Button("好的", role: .cancel) {}
        } message: {
            Text(actionError)
        }
    }

    private func loadDays() async {
        isLoadingDays = true
        dayError = ""
        defer { isLoadingDays = false }
        do {
            days = try await client.request(path: "travel/trips/\(trip.uuid)/days", tokenProvider: session)
        } catch {
            dayError = error.localizedDescription
        }
    }

    private func updateTrip(_ request: TripUpdateRequest) async {
        await performTripWrite(path: "travel/trips/\(trip.uuid)", method: "PUT", body: request) { updated in
            trip = updated
            isEditorPresented = false
        }
    }

    private func startTrip() async {
        await performTripAction(path: "travel/trips/\(trip.uuid)/start") { started in
            trip = started
        }
    }

    private func finishTrip() async {
        await performTripAction(path: "travel/trips/\(trip.uuid)/finish") { finished in
            // 分支条件：唯一进行中行程结束前若正在采样，停止后续定位回调，待传旧点仍保留原 tripUuid。
            if tracking.isTracking {
                tracking.stopTracking()
            }
            trip = finished
        }
    }

    private func switchActiveTrip() async {
        let previousTripUuid = activeTrip?.uuid
        // 切换前停止旧行程采样；已在本地队列中的点仍按其原 tripUuid 分批上传。
        if tracking.isTracking {
            tracking.stopTracking()
        }
        await performTripAction(path: "travel/trips/\(trip.uuid)/switch") { switched in
            trip = switched
            guard let userUuid = session.profile?.uuid else { return }
            tripContext.replaceAfterSwitch(previousTripUuid: previousTripUuid, newActiveTrip: switched, for: userUuid)
        }
    }

    private func performTripAction(path: String, onSuccess: @escaping (Trip) -> Void) async {
        await performTripWrite(path: path, method: "POST", body: EmptyRequest(), onSuccess: onSuccess)
    }

    private func performTripWrite<Body: Encodable>(path: String, method: String, body: Body, onSuccess: @escaping (Trip) -> Void) async {
        isSaving = true
        actionError = ""
        defer { isSaving = false }
        do {
            let updated: Trip = try await client.request(path: path, method: method, body: body, tokenProvider: session)
            onSuccess(updated)
            if let userUuid = session.profile?.uuid {
                tripContext.upsert(updated, for: userUuid)
            }
        } catch {
            actionError = error.localizedDescription
        }
    }
}

/// 输入表单只编辑后端允许的 Trip 元数据；DatePicker 可避免字符串日期解析歧义。
private struct TripEditorSheet: View {
    let trip: Trip
    let isSaving: Bool
    let save: (TripUpdateRequest) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var title: String
    @State private var destination: String
    @State private var startDate: Date
    @State private var endDate: Date

    init(trip: Trip, isSaving: Bool, save: @escaping (TripUpdateRequest) -> Void) {
        self.trip = trip
        self.isSaving = isSaving
        self.save = save
        _title = State(initialValue: trip.title)
        _destination = State(initialValue: trip.destination ?? "")
        _startDate = State(initialValue: trip.startDate)
        _endDate = State(initialValue: trip.endDate)
    }

    private var trimmedTitle: String { title.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var isDateRangeValid: Bool { startDate <= endDate }

    var body: some View {
        NavigationStack {
            Form {
                TextField("行程名称", text: $title)
                TextField("目的地（可选）", text: $destination)
                DatePicker("开始日期", selection: $startDate, displayedComponents: .date)
                DatePicker("结束日期", selection: $endDate, in: startDate..., displayedComponents: .date)
                if !isDateRangeValid {
                    Text("结束日期不能早于开始日期").foregroundStyle(.red)
                }
            }
            .navigationTitle("编辑行程")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }.disabled(isSaving)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "保存中" : "保存") {
                        let trimmedDestination = destination.trimmingCharacters(in: .whitespacesAndNewlines)
                        save(TripUpdateRequest(
                            title: trimmedTitle,
                            destination: trimmedDestination.isEmpty ? nil : trimmedDestination,
                            startDate: startDate,
                            endDate: endDate
                        ))
                    }
                    .disabled(isSaving || trimmedTitle.isEmpty || !isDateRangeValid)
                }
            }
        }
    }
}

private struct ItineraryDayView: View {
    let day: ItineraryDay
    var body: some View {
        List {
            if let transportation = day.transportation { Section("交通") { Text(transportation) } }
            if let accommodation = day.accommodation { Section("住宿") { Text(accommodation) } }
            Section("地点") {
                ForEach(day.spots) { spot in
                    VStack(alignment: .leading) {
                        Text(spot.name)
                        if let address = spot.address { Text(address).font(.subheadline).foregroundStyle(.secondary) }
                    }
                }
            }
            if let notes = day.notes, !notes.isEmpty { Section("备注") { Text(notes) } }
        }
        .navigationTitle("第 \(day.dayIndex) 天")
    }
}

/// POST 行程动作没有请求体时使用的空 JSON 对象，复用 APIClient 的统一认证和错误处理链路。
private struct EmptyRequest: Encodable {}

/// 手动创建行程表单；日期由 DatePicker 提供，避免用户输入格式错误的日期字符串。
private struct TripCreatorSheet: View {
    let isSaving: Bool
    @Binding var errorMessage: String
    let create: (TripCreateRequest) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var destination = ""
    @State private var startDate = Date()
    @State private var endDate = Calendar.current.date(byAdding: .day, value: 1, to: Date()) ?? Date()

    private var trimmedTitle: String { title.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        NavigationStack {
            Form {
                Section("基本信息") {
                    TextField("行程名称", text: $title)
                    TextField("目的地（可选）", text: $destination)
                }
                Section("日期") {
                    DatePicker("开始日期", selection: $startDate, displayedComponents: .date)
                    DatePicker("结束日期", selection: $endDate, in: startDate..., displayedComponents: .date)
                }
                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
            }
            .navigationTitle("新增行程")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }.disabled(isSaving)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "创建中" : "创建") {
                        let trimmedDestination = destination.trimmingCharacters(in: .whitespacesAndNewlines)
                        create(TripCreateRequest(
                            title: trimmedTitle,
                            destination: trimmedDestination.isEmpty ? nil : trimmedDestination,
                            startDate: startDate,
                            endDate: endDate
                        ))
                    }
                    .disabled(isSaving || trimmedTitle.isEmpty)
                }
            }
        }
    }
}
