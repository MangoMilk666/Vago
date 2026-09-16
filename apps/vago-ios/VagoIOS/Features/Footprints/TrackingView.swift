import CoreLocation
import MapKit
import SwiftUI

/// 旅行中记录页：以地图作为主画布，叠加定位控制与手动打卡入口。
struct TrackingView: View {
    // 此 View 组合现有定位 Store 与 FastAPI 数据，不在这里实现 Core Location 或持久化细节。
    @EnvironmentObject private var session: SessionStore
    // 行程上下文来自行程 Tab；它区分正在记录的唯一行程与用户仅用于浏览的历史行程。
    @EnvironmentObject private var tripContext: TripContextStore
    // App 注入的定位 Store 与登录会话同生命周期，离开记录 Tab 不会停止用户主动开启的记录。
    @EnvironmentObject private var tracking: LocationTrackingStore
    @State private var trip: Trip?
    // Repository 只负责合并显示数据，定位采集与上传仍复用既有 LocationTrackingStore。
    @StateObject private var footprintRepository = FootprintRepository()
    @State private var isLoading = true
    @State private var isRefreshing = false
    @State private var isCheckingIn = false
    @State private var isPreparingCheckin = false
    @State private var isTrackingSheetPresented = false
    @State private var isCheckinSheetPresented = false
    // 被点击的手动打卡会驱动详情 sheet；自动 GPS 点没有详情编辑入口。
    @State private var selectedCheckin: FootprintDisplayPoint?
    @State private var isUpdatingCheckin = false
    @State private var checkinDetailError = ""
    @State private var message = ""
    // 刷新错误与短暂操作反馈分开保存，成功读取远端数据后可以准确收起。
    @State private var refreshError: String?
    @State private var loadError = ""
    @State private var checkinError = ""
    // 用户点“打卡”时冻结这一次的新位置，填写表单期间不会因共享位置过期而禁用提交。
    @State private var checkinLocation: CurrentLocationFix?
    // 同一次表单提交失败后必须复用同一事件键，才能让网络重试保持幂等。
    @State private var checkinClientEventUuid: UUID?
    @State private var isNearbyCheckinAlertPresented = false
    @State private var loadedUserUuid: String?
    @State private var locatedTripUuid: String?
    // 离线冷启动使用的是上次已验证的行程摘要，联网成功前不能把它当作实时服务端状态。
    @State private var isTripStatusUnverified = false
    // 每次点击定位按钮递增，Canvas 据此恢复跟随模式；不是位置数据本身。
    @State private var locateRequestID = 0
    // 采样点过密时可仅查看平滑轨迹；该开关不影响打卡标记或服务端数据。
    @State private var areFootprintSamplesVisible = true
    // 保存提示的异步任务，以便连续打卡或离开页面时取消旧的三秒计时。
    @State private var messageDismissTask: Task<Void, Never>?
    private let client = APIClient()

    var body: some View {
        Group {
            //分支条件：初次读取数据时展示加载状态；完成后再依据是否有进行中行程选择内容。
            if isLoading {
                ProgressView("正在读取旅行记录")
            } else if let trip {
                mapContent(for: trip)
            } else if !loadError.isEmpty {
                ContentUnavailableView {
                    Label("暂时无法读取旅行记录", systemImage: "exclamationmark.icloud")
                } description: {
                    Text(loadError)
                } actions: {
                    Button("重新读取") { Task { await refreshMap() } }
                        .buttonStyle(.borderedProminent)
                }
            } else {
                ContentUnavailableView("暂无进行中的行程", systemImage: "location.slash", description: Text("行程开始后可以记录足迹。"))
            }
        }
        // 让 Tab 内的每一种状态都按屏幕可用空间布局，而不是跟随内容高度收缩。
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        // 用户切换后才重新初始读取；地图局部状态变化不应再次触发旅行接口请求。
        .task(id: session.profile?.uuid) { await loadInitially() }
        .onChange(of: tripContext.activeTrip?.uuid) { _, activeTripUuid in
            // 分支条件：行程页开始、结束或切换行程后，记录页只为新的进行中行程重建显示与采集上下文。
            Task { await applyActiveTripChange(activeTripUuid: activeTripUuid) }
        }
        .onChange(of: tracking.localQueueRevision) { _, _ in
            // 新采样落盘或成功批次移除后立即刷新合并视图，地图不必等待下一次 GET。
            footprintRepository.refreshLocalSamples(from: tracking)
        }
        .onChange(of: tracking.syncCompletionRevision) { _, _ in
            // 成功上传后先由内存确认副本接住显示，再等待远端快照回传同一 clientUuid。
            footprintRepository.recordConfirmedSamples(tracking.lastConfirmedSamples, tracking: tracking)
        }
        .onDisappear { messageDismissTask?.cancel() }
        .sheet(isPresented: $isCheckinSheetPresented) {
            CheckinSheet(
                isSubmitting: isCheckingIn,
                errorMessage: $checkinError,
                isNearbyCheckinAlertPresented: $isNearbyCheckinAlertPresented
            ) { locationName, note in
                guard let trip, let checkinLocation else { return }
                Task { await createCheckin(for: trip, location: checkinLocation, locationName: locationName, note: note) }
            }
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
        }
    }

    private func mapContent(for trip: Trip) -> some View {
        // 返回 some View 是不透明返回类型：调用者不需知道复杂的 ZStack 具体组合类型。
        ZStack {
            // 地图延伸至屏幕边缘并位于 TabBar 下方，保持 Apple Maps 式的连续地图画布。
            TravelMapCanvas(
                locations: footprintRepository.displayPoints,
                currentLocation: tracking.currentLocation,
                locateRequestID: locateRequestID,
                areFootprintSamplesVisible: areFootprintSamplesVisible,
                onSelectCheckin: { checkin in
                    checkinDetailError = ""
                    selectedCheckin = checkin
                }
            )
                .ignoresSafeArea()

            TravelMapControls(
                trip: trip,
                isTracking: tracking.isTracking,
                isRefreshing: isRefreshing,
                isPreparingCheckin: isPreparingCheckin,
                message: message,
                refreshError: refreshError,
                syncError: tracking.syncError,
                locationError: tracking.locationError,
                offlineStatusMessage: isTripStatusUnverified ? "离线状态，行程待联网验证" : nil,
                onShowTrackingControls: { isTrackingSheetPresented = true },
                onRefresh: { Task { await refreshMap() } },
                areFootprintSamplesVisible: areFootprintSamplesVisible,
                onToggleFootprintSamples: { areFootprintSamplesVisible.toggle() },
                onLocate: {
                    locateRequestID += 1
                    tracking.requestCurrentLocation()
                },
                onCheckIn: {
                    Task { await prepareCheckin() }
                }
            )
        }
        // Map 画布可延伸到 TabBar 下方，但浮层保持在系统计算的安全区内。
        .safeAreaPadding(.horizontal)
        .safeAreaPadding(.vertical, 12)
        .sheet(isPresented: $isTrackingSheetPresented) {
            TrackingControlSheet(
                trip: trip,
                tracking: tracking,
                userUuid: session.profile?.uuid,
                session: session,
                onSync: { Task { await syncAndReload() } }
            )
            .presentationDetents([.height(300), .medium])
            .presentationDragIndicator(.visible)
        }
        .sheet(item: $selectedCheckin) { checkin in
            CheckinDetailSheet(
                checkin: checkin,
                isSaving: isUpdatingCheckin,
                errorMessage: checkinDetailError
            ) { locationName, note in
                Task { await updateCheckin(checkin, locationName: locationName, note: note) }
            }
            .presentationDetents([.height(470), .large])
            .presentationDragIndicator(.visible)
        }
    }

    private func load(showLoading: Bool) async {
        // 参数区分首屏加载与手动刷新，后者应保留用户正在看的地图而不闪回 ProgressView。
        if showLoading {
            isLoading = true
            loadError = ""
        }
        defer {
            if showLoading {
                isLoading = false
            }
        }
        // 网络读取前先恢复最近一次已验证的进行中行程和本地队列，断网时仍可查看、继续记录足迹。
        if let userUuid = session.profile?.uuid, let cachedTrip = FootprintRepository.cachedActiveTrip(for: userUuid) {
            trip = cachedTrip
            isTripStatusUnverified = true
            tracking.prepare(tripUuid: cachedTrip.uuid, userUuid: userUuid, session: session)
            footprintRepository.prepare(userUuid: userUuid, tripUuid: cachedTrip.uuid, tracking: tracking)
        }
        do {
            let trips: [Trip] = try await client.request(path: "travel/trips", tokenProvider: session)
            // 分支条件：行程列表成功返回即说明网络已恢复，可清除上次保留的刷新失败状态。
            refreshError = nil
            guard let userUuid = session.profile?.uuid else { return }
            tripContext.replaceTrips(trips, for: userUuid)
            trip = tripContext.activeTrip
            isTripStatusUnverified = false
            // 分支条件：存在进行中行程时才读取其轨迹与打卡，并恢复该用户的待传队列。
            if let trip {
                FootprintRepository.cacheActiveTrip(trip, for: userUuid)
                tracking.prepare(tripUuid: trip.uuid, userUuid: userUuid, session: session)
                footprintRepository.prepare(userUuid: userUuid, tripUuid: trip.uuid, tracking: tracking)
                // 统一观察流按时间返回自动 GPS 与手动打卡，地图不再拼接两个独立远端集合。
                let remoteObservations: [TravelObservation] = try await client.request(
                    path: "footprints/trips/\(trip.uuid)/observations",
                    tokenProvider: session
                )
                // 分支条件：异步请求回来前若用户已切换行程，不让旧结果覆盖新地图。
                guard self.trip?.uuid == trip.uuid, session.profile?.uuid == userUuid else { return }
                footprintRepository.replaceRemoteObservations(remoteObservations)
                tracking.updateManualCheckinCoordinates(footprintRepository.manualCheckinCoordinates(), for: trip.uuid)
                // 分支条件：每个进行中行程首次进入记录页时请求一次当前位置，定位不会写入足迹队列。
                if locatedTripUuid != trip.uuid {
                    locatedTripUuid = trip.uuid
                    locateRequestID += 1
                    tracking.requestCurrentLocation()
                }
                let confirmed = await tracking.syncPendingSamples()
                footprintRepository.recordConfirmedSamples(confirmed, tracking: tracking)
            }
        } catch {
            // 分支条件：首次加载无可展示地图时展示独立错误页；已有数据刷新失败则保留原地图。
            if trip == nil {
                loadError = error.localizedDescription
            } else {
                refreshError = error.localizedDescription
            }
        }
    }

    private func refreshMap() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        // 用户主动刷新时保留已显示地图，避免刷新过程重新创建地图视图。
        await load(showLoading: false)
    }

    private func loadInitially() async {
        guard let userUuid = session.profile?.uuid, loadedUserUuid != userUuid else { return }
        // 请求开始前记录用户，阻止相同页面生命周期内的并发重复读取。
        loadedUserUuid = userUuid
        await load(showLoading: true)
    }

    private func applyActiveTripChange(activeTripUuid: String?) async {
        // 分支条件：结束当前行程后清空记录页的活动地图，不把旧旅行事实伪装成仍可继续写入的上下文。
        guard let activeTripUuid, let activeTrip = tripContext.activeTrip,
              let userUuid = session.profile?.uuid else {
            trip = nil
            return
        }
        // 当前视图已经展示同一活动行程时，不因列表刷新重复下载观察数据。
        guard trip?.uuid != activeTripUuid else { return }

        trip = activeTrip
        loadError = ""
        isTripStatusUnverified = false
        FootprintRepository.cacheActiveTrip(activeTrip, for: userUuid)
        tracking.prepare(tripUuid: activeTrip.uuid, userUuid: userUuid, session: session)
        footprintRepository.prepare(userUuid: userUuid, tripUuid: activeTrip.uuid, tracking: tracking)
        do {
            let observations: [TravelObservation] = try await client.request(
                path: "footprints/trips/\(activeTrip.uuid)/observations",
                tokenProvider: session
            )
            // 分支条件：网络返回期间再次切换行程时，不让旧请求回填新行程的地图。
            guard tripContext.activeTrip?.uuid == activeTrip.uuid, trip?.uuid == activeTrip.uuid else { return }
            footprintRepository.replaceRemoteObservations(observations)
            tracking.updateManualCheckinCoordinates(footprintRepository.manualCheckinCoordinates(), for: activeTrip.uuid)
            let confirmed = await tracking.syncPendingSamples()
            footprintRepository.recordConfirmedSamples(confirmed, tracking: tracking)
        } catch {
            refreshError = error.localizedDescription
        }
    }

    private func syncAndReload() async {
        // 同步本地队列后只重新拉轨迹点，避免为一个按钮重复读取行程与打卡数据。
        let confirmed = await tracking.syncPendingSamples()
        footprintRepository.recordConfirmedSamples(confirmed, tracking: tracking)
        guard let trip else { return }
        if let remoteObservations: [TravelObservation] = try? await client.request(
            path: "footprints/trips/\(trip.uuid)/observations",
            tokenProvider: session
        ) {
            footprintRepository.replaceRemoteObservations(remoteObservations)
            tracking.updateManualCheckinCoordinates(footprintRepository.manualCheckinCoordinates(), for: trip.uuid)
            // 分支条件：统一观察流读取成功后，地图已恢复最新事实，旧刷新错误不应继续遮挡视图。
            refreshError = nil
        }
    }

    private func prepareCheckin() async {
        guard !isPreparingCheckin else { return }
        isPreparingCheckin = true
        defer { isPreparingCheckin = false }
        do {
            // 打卡前主动获取并冻结新坐标，静止超过 30 秒也不会让入口悄悄失效。
            checkinLocation = try await tracking.requestFreshLocation()
            checkinClientEventUuid = UUID()
            checkinError = ""
            isNearbyCheckinAlertPresented = false
            isCheckinSheetPresented = true
        } catch {
            showTransientMessage(error.localizedDescription)
        }
    }

    private func createCheckin(for trip: Trip, location: CurrentLocationFix, locationName: String, note: String) async {
        // 分支条件：30 米内已有打卡时不禁用表单按钮，而是保留用户输入并弹出明确的换位置提示。
        if footprintRepository.displayPoints.contains(where: { point in
            point.kind == .manualCheckin
                && CLLocation(latitude: point.latitude, longitude: point.longitude)
                .distance(from: CLLocation(latitude: location.coordinate.latitude, longitude: location.coordinate.longitude))
                < 30
        }) {
            isNearbyCheckinAlertPresented = true
            return
        }
        isCheckingIn = true
        checkinError = ""
        defer { isCheckingIn = false }
        do {
            guard let clientEventUuid = checkinClientEventUuid else { return }
            let payload = CheckinRequest(
                tripUuid: trip.uuid,
                clientEventUuid: clientEventUuid,
                locationName: locationName,
                latitude: location.coordinate.latitude,
                longitude: location.coordinate.longitude,
                note: note.isEmpty ? nil : note,
                trackingSegmentUuid: tracking.activeTrackingSegmentUuid,
                checkedAt: Date()
            )
            let checkin: TravelObservation = try await client.request(
                path: "footprints/observations/checkins",
                method: "POST",
                body: payload,
                tokenProvider: session
            )
            footprintRepository.upsertManualCheckin(checkin)
            tracking.updateManualCheckinCoordinates(footprintRepository.manualCheckinCoordinates(), for: trip.uuid)
            showCheckinSuccessMessage()
            checkinClientEventUuid = nil
            // 仅在服务端写入成功后收起输入 sheet，保留失败时用户已填写的内容。
            isCheckinSheetPresented = false
        } catch {
            // 分支条件：其他设备刚写入附近打卡时由服务端兜底，客户端使用同一弹窗反馈。
            if error.localizedDescription.contains("打卡点太近") || error.localizedDescription.contains("已有打卡") {
                isNearbyCheckinAlertPresented = true
            } else {
                // 打卡失败应留在弹层内，用户可以保留已填写内容后再次提交。
                checkinError = error.localizedDescription
            }
        }
    }

    private func updateCheckin(_ checkin: FootprintDisplayPoint, locationName: String, note: String) async {
        // 分支条件：详情只会由远端手动打卡打开；缺少服务端 UUID 时拒绝发送不完整更新请求。
        guard let serverUuid = checkin.serverUuid else {
            checkinDetailError = "该打卡尚未同步完成，暂时无法编辑。"
            return
        }
        isUpdatingCheckin = true
        checkinDetailError = ""
        defer { isUpdatingCheckin = false }
        do {
            let payload = CheckinUpdateRequest(locationName: locationName, note: note)
            let updated: TravelObservation = try await client.request(
                path: "footprints/observations/checkins/\(serverUuid)",
                method: "PATCH",
                body: payload,
                tokenProvider: session
            )
            footprintRepository.upsertManualCheckin(updated)
            tracking.updateManualCheckinCoordinates(footprintRepository.manualCheckinCoordinates(), for: updated.tripUuid)
            selectedCheckin = nil
            showTransientMessage("打卡已更新")
        } catch {
            // 服务端会拒绝历史行程或跨账号更新，详情 sheet 保持打开以展示明确原因。
            checkinDetailError = error.localizedDescription
        }
    }

    private func showCheckinSuccessMessage() {
        showTransientMessage("已记录本次打卡")
    }

    private func showTransientMessage(_ text: String) {
        messageDismissTask?.cancel()
        message = text
        // 新提示会取消旧任务，且仅在文本未被后续状态替换时才自动收起。
        messageDismissTask = Task {
            try? await Task.sleep(for: .seconds(3))
            guard !Task.isCancelled, message == text else { return }
            message = ""
        }
    }
}

/// 手动打卡详情：用户可补充文本，但不会修改已经发生的坐标、时间与路线事实。
private struct CheckinDetailSheet: View {
    private enum InputField {
        case locationName
        case note
    }

    let checkin: FootprintDisplayPoint
    let isSaving: Bool
    let errorMessage: String
    let save: (String, String) -> Void

    @State private var isEditing = false
    @State private var locationName = ""
    @State private var note = ""
    @State private var isPhotoPreviewPresented = false
    @FocusState private var focusedField: InputField?

    private var trimmedLocationName: String {
        locationName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .top) {
                    if isEditing {
                        Text("编辑打卡")
                            .font(.title3.bold())
                    } else {
                        Text(checkin.locationName ?? "未命名地点")
                            .font(.title3.bold())
                            .lineLimit(2)
                    }
                    Spacer()
                    Button {
                        if isEditing {
                            resetEditableText()
                            focusedField = nil
                        }
                        isEditing.toggle()
                    } label: {
                        Image(systemName: isEditing ? "xmark" : "pencil")
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel(isEditing ? "取消编辑打卡" : "编辑打卡")
                }

                if isEditing {
                    TextField("地点名称", text: $locationName)
                        .textFieldStyle(.roundedBorder)
                        .focused($focusedField, equals: .locationName)
                        .submitLabel(.next)
                        .onSubmit { focusedField = .note }
                    TextField("记录备注（可选）", text: $note, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(3...6)
                        .focused($focusedField, equals: .note)
                        .submitLabel(.done)
                        .onSubmit { focusedField = nil }
                } else {
                    Text(checkin.note?.isEmpty == false ? checkin.note! : "暂未添加备注")
                        .font(.body)
                        .foregroundStyle(checkin.note?.isEmpty == false ? .primary : .secondary)
                }

                Button {
                    isPhotoPreviewPresented = true
                } label: {
                    VStack(spacing: 10) {
                        Image(systemName: "photo.on.rectangle.angled")
                            .font(.system(size: 34, weight: .medium))
                        Text("照片功能准备中")
                            .font(.subheadline.weight(.medium))
                    }
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .frame(height: 154)
                    .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("全屏查看打卡照片占位图")

                HStack(spacing: 8) {
                    Image(systemName: "clock")
                    Text(checkin.recordedAt, format: .dateTime.year().month().day().hour().minute())
                }
                .font(.footnote)
                .foregroundStyle(.secondary)

                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                }

                if isEditing {
                    Button(isSaving ? "保存中" : "保存修改") {
                        focusedField = nil
                        save(trimmedLocationName, note.trimmingCharacters(in: .whitespacesAndNewlines))
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .frame(maxWidth: .infinity)
                    .disabled(isSaving || trimmedLocationName.isEmpty)
                }
            }
            .padding(24)
        }
        .contentShape(Rectangle())
        .onTapGesture { focusedField = nil }
        .onAppear(perform: resetEditableText)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("完成") { focusedField = nil }
            }
        }
        .fullScreenCover(isPresented: $isPhotoPreviewPresented) {
            CheckinPhotoPlaceholderPreview(locationName: checkin.locationName)
        }
    }

    private func resetEditableText() {
        locationName = checkin.locationName ?? ""
        note = checkin.note ?? ""
    }
}

/// 真实照片上传尚未实施时，保留完整的全屏查看交互，不把占位卡伪装为用户照片。
private struct CheckinPhotoPlaceholderPreview: View {
    let locationName: String?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 18) {
                Image(systemName: "photo.on.rectangle.angled")
                    .font(.system(size: 76, weight: .light))
                Text(locationName ?? "打卡照片")
                    .font(.title3.weight(.semibold))
                Text("照片上传功能准备中")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .foregroundStyle(.white)
        }
        .overlay(alignment: .topTrailing) {
            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.title2)
                    .foregroundStyle(.white)
            }
            .padding()
            .accessibilityLabel("关闭全屏照片预览")
        }
    }
}

private struct CheckinSheet: View {
    // Sheet 将输入流程与地图主画布隔离，避免键盘或表单永久遮挡地图。
    private enum InputField {
        case locationName
        case note
    }

    let isSubmitting: Bool
    // Binding 指向父视图状态，子 Sheet 可以读取更新后的错误而不复制一份数据。
    @Binding var errorMessage: String
    // 接收父视图的附近打卡提示状态，Alert 显示时不会关闭用户正在填写的表单。
    @Binding var isNearbyCheckinAlertPresented: Bool
    let submit: (String, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var locationName = ""
    @State private var note = ""
    // 弹层单独维护焦点，使用户可通过键盘完成键或点击输入区外主动收起键盘。
    @FocusState private var focusedField: InputField?

    var body: some View {
        // ScrollView 使较小屏幕、横屏或键盘弹出时仍能滚动到确认按钮。
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    Text("在当前位置打卡")
                        .font(.title3.bold())
                    Spacer()
                    Button("取消") { dismiss() }
                }
                Text("保存这一刻的地点和感受，它会显示在本次旅行地图中。")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                TextField("地点名称", text: $locationName)
                    .textFieldStyle(.roundedBorder)
                    .focused($focusedField, equals: .locationName)
                    .submitLabel(.next)
                    .onSubmit { focusedField = .note }
                TextField("记录一点感受（可选）", text: $note, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(2...4)
                    .focused($focusedField, equals: .note)
                    .submitLabel(.done)
                    .onSubmit { focusedField = nil }
                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
                Button(isSubmitting ? "打卡中" : "确认打卡") {
                    focusedField = nil
                    submit(
                        locationName.trimmingCharacters(in: .whitespacesAndNewlines),
                        note.trimmingCharacters(in: .whitespacesAndNewlines)
                    )
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .frame(maxWidth: .infinity)
                .disabled(isSubmitting || locationName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(24)
        .contentShape(Rectangle())
        .onTapGesture { focusedField = nil }
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("完成") {
                    // 无论使用哪种系统键盘，都提供一致、明确的键盘收起操作。
                    focusedField = nil
                }
            }
        }
        .alert("暂时无法打卡", isPresented: $isNearbyCheckinAlertPresented) {
            Button("知道了", role: .cancel) {}
        } message: {
            Text("和其他打卡点太近啦，请换个位置重试")
        }
    }
}
