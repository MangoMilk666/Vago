import CoreLocation
import MapKit
import SwiftUI

/// 旅行中记录页：负责启动前台定位、展示已同步轨迹并提供一次手动打卡。
struct TrackingView: View {
    @EnvironmentObject private var session: SessionStore
    @StateObject private var tracking = LocationTrackingStore()
    @State private var trip: Trip?
    @State private var serverLocations: [FootprintLocation] = []
    @State private var locationName = ""
    @State private var note = ""
    @State private var isLoading = true
    @State private var isCheckingIn = false
    @State private var message = ""
    private let client = APIClient()

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView("正在读取旅行记录")
                } else if let trip {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 20) {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(trip.title).font(.headline)
                                Text(trip.destination ?? "当前行程")
                                    .foregroundStyle(.secondary)
                                Text(tracking.isTracking ? "正在记录位置" : "尚未开始记录")
                                    .font(.subheadline)
                                    .foregroundStyle(tracking.isTracking ? .green : .secondary)
                            }

                            TrackingMap(locations: serverLocations, latestSample: tracking.latestSample)
                                .frame(height: 260)
                                .clipShape(RoundedRectangle(cornerRadius: 12))

                            VStack(alignment: .leading, spacing: 12) {
                                Text("位置记录").font(.headline)
                                Text(permissionDescription)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                                HStack {
                                    Button(tracking.isTracking ? "停止记录" : "开始记录") {
                                        //分支条件：记录已开启时停止定位，否则为当前正式行程申请权限并开始采样。
                                        if tracking.isTracking {
                                            tracking.stopTracking()
                                        } else if let userUuid = session.profile?.uuid {
                                            tracking.startTracking(tripUuid: trip.uuid, userUuid: userUuid, session: session)
                                        }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    Button("同步待传记录") { Task { await syncAndReload() } }
                                        .buttonStyle(.bordered)
                                }
                                if tracking.pendingCount > 0 {
                                    Text("本机待同步 \(tracking.pendingCount) 条位置记录")
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                }
                                if let syncError = tracking.syncError {
                                    Text("同步未完成：\(syncError)")
                                        .font(.footnote)
                                        .foregroundStyle(.red)
                                }
                            }

                            VStack(alignment: .leading, spacing: 12) {
                                Text("手动打卡").font(.headline)
                                TextField("地点名称", text: $locationName)
                                    .textFieldStyle(.roundedBorder)
                                TextField("记录一点感受（可选）", text: $note, axis: .vertical)
                                    .textFieldStyle(.roundedBorder)
                                Button(isCheckingIn ? "打卡中" : "在当前位置打卡") {
                                    Task { await createCheckin(for: trip) }
                                }
                                .buttonStyle(.bordered)
                                .disabled(tracking.latestSample == nil || locationName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isCheckingIn)
                            }
                            if !message.isEmpty {
                                Text(message).font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                        .padding()
                    }
                } else {
                    ContentUnavailableView("暂无进行中的行程", systemImage: "location.slash", description: Text("行程开始后可以记录足迹。"))
                }
            }
            .navigationTitle("记录")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { Task { await load() } } label: { Image(systemName: "arrow.clockwise") } } }
            .task { await load() }
            .onDisappear { tracking.stopTracking() }
        }
    }

    private var permissionDescription: String {
        switch tracking.authorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse:
            return "定位权限已开启。第一版仅在应用打开期间采样。"
        case .denied, .restricted:
            return "请在系统设置中允许 Vago 使用定位，才能记录足迹。"
        case .notDetermined:
            return "开始记录时会请求定位权限。"
        @unknown default:
            return "定位权限状态暂不可用。"
        }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let trips: [Trip] = try await client.request(path: "travel/trips", tokenProvider: session)
            trip = trips.first(where: { $0.status == 2 })
            // 分支条件：存在进行中行程时读取它已同步的轨迹，用于跨设备或重启后的地图恢复。
            if let trip {
                serverLocations = try await client.request(path: "footprints/trips/\(trip.uuid)/locations", tokenProvider: session)
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

    private func createCheckin(for trip: Trip) async {
        guard let sample = tracking.latestSample else { return }
        isCheckingIn = true
        defer { isCheckingIn = false }
        do {
            let payload = CheckinRequest(
                tripUuid: trip.uuid,
                locationName: locationName.trimmingCharacters(in: .whitespacesAndNewlines),
                latitude: sample.latitude,
                longitude: sample.longitude,
                note: note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : note,
                checkedAt: Date()
            )
            let _: Checkin = try await client.request(path: "footprints/checkins", method: "POST", body: payload, tokenProvider: session)
            locationName = ""
            note = ""
            message = "已记录本次打卡"
        } catch {
            message = error.localizedDescription
        }
    }
}

private struct TrackingMap: View {
    let locations: [FootprintLocation]
    let latestSample: PendingLocationSample?

    var body: some View {
        Map(initialPosition: .region(initialRegion)) {
            ForEach(locations) { location in
                Marker("轨迹", coordinate: CLLocationCoordinate2D(latitude: location.latitude, longitude: location.longitude))
            }
            if let latestSample {
                Marker("当前位置", coordinate: CLLocationCoordinate2D(latitude: latestSample.latitude, longitude: latestSample.longitude))
                    .tint(.indigo)
            }
        }
    }

    private var initialRegion: MKCoordinateRegion {
        let coordinate: CLLocationCoordinate2D
        // 分支条件：优先以最新本地样本居中；没有时回退到已同步轨迹，最后显示全球默认位置。
        if let latestSample {
            coordinate = CLLocationCoordinate2D(latitude: latestSample.latitude, longitude: latestSample.longitude)
        } else if let location = locations.last {
            coordinate = CLLocationCoordinate2D(latitude: location.latitude, longitude: location.longitude)
        } else {
            // fallback：写死的位置：central region of Singapore, near the MacRitchie Reservoir.
            coordinate = CLLocationCoordinate2D(latitude: 1.3521, longitude: 103.8198)
        }
        return MKCoordinateRegion(center: coordinate, latitudinalMeters: 1_000, longitudinalMeters: 1_000)
    }
}
