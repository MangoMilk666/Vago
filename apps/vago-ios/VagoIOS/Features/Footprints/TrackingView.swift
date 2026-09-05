import CoreLocation
import MapKit
import SwiftUI

/// 旅行中记录页：以地图作为主画布，叠加定位控制与手动打卡入口。
struct TrackingView: View {
    // 此 View 组合现有定位 Store 与 FastAPI 数据，不在这里实现 Core Location 或持久化细节。
    @EnvironmentObject private var session: SessionStore
    // App 注入的定位 Store 与登录会话同生命周期，离开记录 Tab 不会停止用户主动开启的记录。
    @EnvironmentObject private var tracking: LocationTrackingStore
    @State private var trip: Trip?
    @State private var serverLocations: [FootprintLocation] = []
    @State private var checkins: [Checkin] = []
    @State private var isLoading = true
    @State private var isRefreshing = false
    @State private var isCheckingIn = false
    @State private var isPreparingCheckin = false
    @State private var isTrackingSheetPresented = false
    @State private var isCheckinSheetPresented = false
    @State private var message = ""
    @State private var loadError = ""
    @State private var checkinError = ""
    // 用户点“打卡”时冻结这一次的新位置，填写表单期间不会因共享位置过期而禁用提交。
    @State private var checkinLocation: CurrentLocationFix?
    @State private var isNearbyCheckinAlertPresented = false
    @State private var loadedUserUuid: String?
    @State private var locatedTripUuid: String?
    // 每次点击定位按钮递增，Canvas 据此恢复跟随模式；不是位置数据本身。
    @State private var locateRequestID = 0
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
                locations: serverLocations,
                checkins: checkins,
                currentLocation: tracking.currentLocation,
                locateRequestID: locateRequestID
            )
                .ignoresSafeArea()

            TravelMapControls(
                trip: trip,
                isTracking: tracking.isTracking,
                isRefreshing: isRefreshing,
                isPreparingCheckin: isPreparingCheckin,
                message: message,
                syncError: tracking.syncError,
                locationError: tracking.locationError,
                onShowTrackingControls: { isTrackingSheetPresented = true },
                onRefresh: { Task { await refreshMap() } },
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
        do {
            let trips: [Trip] = try await client.request(path: "travel/trips", tokenProvider: session)
            trip = trips.first(where: { $0.status == 2 })
            // 分支条件：存在进行中行程时才读取其轨迹与打卡，并恢复该用户的待传队列。
            if let trip {
                // async let 并行启动两个独立请求；分别 await 时才汇合结果，比串行读取更快。
                async let loadedLocations: [FootprintLocation] = client.request(path: "footprints/trips/\(trip.uuid)/locations", tokenProvider: session)
                async let loadedCheckins: [Checkin] = client.request(path: "footprints/trips/\(trip.uuid)/checkins", tokenProvider: session)
                serverLocations = try await loadedLocations
                checkins = try await loadedCheckins
                if let userUuid = session.profile?.uuid {
                    tracking.prepare(tripUuid: trip.uuid, userUuid: userUuid, session: session)
                    // 分支条件：每个进行中行程首次进入记录页时请求一次当前位置，定位不会写入足迹队列。
                    if locatedTripUuid != trip.uuid {
                        locatedTripUuid = trip.uuid
                        locateRequestID += 1
                        tracking.requestCurrentLocation()
                    }
                    await tracking.syncPendingSamples()
                }
            }
        } catch {
            // 分支条件：首次加载无可展示地图时展示独立错误页；已有数据刷新失败则保留原地图。
            if trip == nil {
                loadError = error.localizedDescription
            } else {
                messageDismissTask?.cancel()
                message = "刷新失败：\(error.localizedDescription)"
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

    private func syncAndReload() async {
        // 同步本地队列后只重新拉轨迹点，避免为一个按钮重复读取行程与打卡数据。
        await tracking.syncPendingSamples()
        guard let trip else { return }
        serverLocations = (try? await client.request(path: "footprints/trips/\(trip.uuid)/locations", tokenProvider: session)) ?? serverLocations
    }

    private func prepareCheckin() async {
        guard !isPreparingCheckin else { return }
        isPreparingCheckin = true
        defer { isPreparingCheckin = false }
        do {
            // 打卡前主动获取并冻结新坐标，静止超过 30 秒也不会让入口悄悄失效。
            checkinLocation = try await tracking.requestFreshLocation()
            checkinError = ""
            isNearbyCheckinAlertPresented = false
            isCheckinSheetPresented = true
        } catch {
            showTransientMessage(error.localizedDescription)
        }
    }

    private func createCheckin(for trip: Trip, location: CurrentLocationFix, locationName: String, note: String) async {
        // 分支条件：30 米内已有打卡时不禁用表单按钮，而是保留用户输入并弹出明确的换位置提示。
        if checkins.contains(where: { checkin in
            CLLocation(latitude: checkin.latitude, longitude: checkin.longitude)
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
            let payload = CheckinRequest(
                tripUuid: trip.uuid,
                locationName: locationName,
                latitude: location.coordinate.latitude,
                longitude: location.coordinate.longitude,
                note: note.isEmpty ? nil : note,
                checkedAt: Date()
            )
            let checkin: Checkin = try await client.request(path: "footprints/checkins", method: "POST", body: payload, tokenProvider: session)
            checkins.append(checkin)
            showCheckinSuccessMessage()
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
