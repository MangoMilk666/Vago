import CoreLocation
import MapKit
import SwiftUI

/// 旅行中记录页：以地图作为主画布，叠加定位控制与手动打卡入口。
struct TrackingView: View {
    @EnvironmentObject private var session: SessionStore
    @StateObject private var tracking = LocationTrackingStore()
    @State private var trip: Trip?
    @State private var serverLocations: [FootprintLocation] = []
    @State private var checkins: [Checkin] = []
    @State private var isLoading = true
    @State private var isCheckingIn = false
    @State private var isCheckinSheetPresented = false
    @State private var message = ""
    private let client = APIClient()

    var body: some View {
        Group {
            // 分支条件：初次读取数据时展示加载状态；完成后再依据是否有进行中行程选择内容。
            if isLoading {
                ProgressView("正在读取旅行记录")
            } else if let trip {
                mapContent(for: trip)
            } else {
                ContentUnavailableView("暂无进行中的行程", systemImage: "location.slash", description: Text("行程开始后可以记录足迹。"))
            }
        }
        // 让 Tab 内的每一种状态都按屏幕可用空间布局，而不是跟随内容高度收缩。
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .task { await load() }
        .onDisappear { tracking.stopTracking() }
        .sheet(isPresented: $isCheckinSheetPresented) {
            CheckinSheet(isSubmitting: isCheckingIn) { locationName, note in
                guard let trip else { return }
                Task { await createCheckin(for: trip, locationName: locationName, note: note) }
            }
            .presentationDetents([.medium])
            .presentationDragIndicator(.visible)
        }
    }

    private func mapContent(for trip: Trip) -> some View {
        ZStack {
            // 地图延伸至屏幕边缘并位于 TabBar 下方，保持 Apple Maps 式的连续地图画布。
            TrackingMap(locations: serverLocations, checkins: checkins, latestSample: tracking.latestSample)
                .ignoresSafeArea()

            VStack(spacing: 16) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(trip.title).font(.headline)
                        Text(tracking.isTracking ? "正在记录位置" : "尚未开始记录")
                            .font(.caption)
                            .foregroundStyle(tracking.isTracking ? .green : .secondary)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))

                    Spacer()

                    Button { Task { await load() } } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel("刷新足迹数据")
                }

                Spacer()

                VStack(spacing: 10) {
                    if !message.isEmpty {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 9)
                            .background(.ultraThinMaterial, in: Capsule())
                    }
                    if let syncError = tracking.syncError {
                        Text("同步未完成：\(syncError)")
                            .font(.footnote)
                            .foregroundStyle(.red)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 9)
                            .background(.ultraThinMaterial, in: Capsule())
                    }
                    HStack(spacing: 12) {
                        Button {
                            // 分支条件：记录已开启时停止定位，否则为当前正式行程申请权限并开始采样。
                            if tracking.isTracking {
                                tracking.stopTracking()
                            } else if let userUuid = session.profile?.uuid {
                                tracking.startTracking(tripUuid: trip.uuid, userUuid: userUuid, session: session)
                            }
                        } label: {
                            Label(tracking.isTracking ? "停止记录" : "开始记录", systemImage: tracking.isTracking ? "stop.fill" : "location.fill")
                        }
                        .buttonStyle(.borderedProminent)

                        Button { Task { await syncAndReload() } } label: {
                            Image(systemName: "arrow.triangle.2.circlepath")
                        }
                        .buttonStyle(.bordered)
                        .accessibilityLabel("同步待传记录")

                        Button { isCheckinSheetPresented = true } label: {
                            Label("打卡", systemImage: "mappin.and.ellipse")
                        }
                        .buttonStyle(.bordered)
                        .disabled(tracking.latestSample == nil)
                    }
                    if tracking.pendingCount > 0 {
                        Text("本机待同步 \(tracking.pendingCount) 条位置记录")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.horizontal)
            .padding(.top, 12)
            .padding(.bottom, 74)
        }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let trips: [Trip] = try await client.request(path: "travel/trips", tokenProvider: session)
            trip = trips.first(where: { $0.status == 2 })
            // 分支条件：存在进行中行程时才读取其轨迹与打卡，并恢复该用户的待传队列。
            if let trip {
                async let loadedLocations: [FootprintLocation] = client.request(path: "footprints/trips/\(trip.uuid)/locations", tokenProvider: session)
                async let loadedCheckins: [Checkin] = client.request(path: "footprints/trips/\(trip.uuid)/checkins", tokenProvider: session)
                serverLocations = try await loadedLocations
                checkins = try await loadedCheckins
                if let userUuid = session.profile?.uuid {
                    tracking.prepare(tripUuid: trip.uuid, userUuid: userUuid, session: session)
                    await tracking.syncPendingSamples()
                }
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func syncAndReload() async {
        await tracking.syncPendingSamples()
        guard let trip else { return }
        serverLocations = (try? await client.request(path: "footprints/trips/\(trip.uuid)/locations", tokenProvider: session)) ?? serverLocations
    }

    private func createCheckin(for trip: Trip, locationName: String, note: String) async {
        guard let sample = tracking.latestSample else { return }
        isCheckingIn = true
        defer { isCheckingIn = false }
        do {
            let payload = CheckinRequest(
                tripUuid: trip.uuid,
                locationName: locationName,
                latitude: sample.latitude,
                longitude: sample.longitude,
                note: note.isEmpty ? nil : note,
                checkedAt: Date()
            )
            let checkin: Checkin = try await client.request(path: "footprints/checkins", method: "POST", body: payload, tokenProvider: session)
            checkins.append(checkin)
            message = "已记录本次打卡"
            // 仅在服务端写入成功后收起输入 sheet，保留失败时用户已填写的内容。
            isCheckinSheetPresented = false
        } catch {
            message = error.localizedDescription
        }
    }
}

private struct TrackingMap: View {
    let locations: [FootprintLocation]
    let checkins: [Checkin]
    let latestSample: PendingLocationSample?

    var body: some View {
        Map(initialPosition: .region(initialRegion)) {
            // 分支条件：至少两个轨迹点才绘制连线，单点仅作为位置标记展示。
            if locations.count > 1 {
                MapPolyline(coordinates: locations.map(coordinate(for:)))
                    .stroke(.indigo, lineWidth: 4)
            }
            ForEach(locations) { location in
                Marker("轨迹", coordinate: coordinate(for: location))
                    .tint(.indigo)
            }
            ForEach(checkins) { checkin in
                Annotation(checkin.locationName, coordinate: coordinate(for: checkin)) {
                    Image(systemName: "mappin.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.orange)
                        .shadow(radius: 2)
                }
            }
            if let latestSample {
                Marker("当前位置", coordinate: CLLocationCoordinate2D(latitude: latestSample.latitude, longitude: latestSample.longitude))
                    .tint(.red)
            }
        }
        .mapStyle(.standard(elevation: .realistic))
        .mapControls {
            MapCompass()
            MapScaleView()
        }
    }

    private func coordinate(for location: FootprintLocation) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: location.latitude, longitude: location.longitude)
    }

    private func coordinate(for checkin: Checkin) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: checkin.latitude, longitude: checkin.longitude)
    }

    private var initialRegion: MKCoordinateRegion {
        let center: CLLocationCoordinate2D
        // 分支条件：优先以最新本地样本居中；没有时使用已同步轨迹或打卡，最后才显示默认位置。
        if let latestSample {
            center = CLLocationCoordinate2D(latitude: latestSample.latitude, longitude: latestSample.longitude)
        } else if let location = locations.last {
            center = coordinate(for: location)
        } else if let checkin = checkins.last {
            center = coordinate(for: checkin)
        } else {
            center = CLLocationCoordinate2D(latitude: 1.3521, longitude: 103.8198)
        }
        return MKCoordinateRegion(center: center, latitudinalMeters: 1_000, longitudinalMeters: 1_000)
    }
}

private struct CheckinSheet: View {
    private enum InputField {
        case locationName
        case note
    }

    let isSubmitting: Bool
    let submit: (String, String) -> Void
    @State private var locationName = ""
    @State private var note = ""
    // 弹层单独维护焦点，使用户可通过键盘完成键或点击输入区外主动收起键盘。
    @FocusState private var focusedField: InputField?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("在当前位置打卡")
                .font(.title3.bold())
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
            Spacer()
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
    }
}
