import CoreLocation
import Foundation

/// 管理定位权限、前台采样与离线队列；服务端仍是最终的足迹数据源。
@MainActor
final class LocationTrackingStore: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published private(set) var authorizationStatus: CLAuthorizationStatus
    @Published private(set) var latestSample: PendingLocationSample?
    @Published private(set) var isTracking = false
    @Published private(set) var pendingCount = 0
    @Published private(set) var syncError: String?

    private let manager = CLLocationManager()
    private let client = APIClient()
    private var currentTripUuid: String?
    private var currentUserUuid: String?
    private var session: SessionStore?

    override init() {
        authorizationStatus = CLLocationManager().authorizationStatus
        super.init()
        manager.delegate = self
        // 第一版仅在 App 前台以约 20 米间隔采样，先控制功耗和隐私边界。
        manager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
        manager.distanceFilter = 20
    }

    func startTracking(tripUuid: String, userUuid: String, session: SessionStore) {
        prepare(tripUuid: tripUuid, userUuid: userUuid, session: session)
        requestLocationPermissionIfNeeded()
        // 分支条件：用户已授予定位权限时立即开始采样；否则等待系统回调后的授权结果。
        if isAuthorized {
            manager.startUpdatingLocation()
            isTracking = true
        }
    }

    func prepare(tripUuid: String, userUuid: String, session: SessionStore) {
        // 页面加载可先恢复待传队列，但不得因此主动请求系统定位权限。
        currentTripUuid = tripUuid
        currentUserUuid = userUuid
        self.session = session
        pendingCount = pendingSamples(for: userUuid).count
    }

    func stopTracking() {
        manager.stopUpdatingLocation()
        isTracking = false
    }

    func requestLocationPermissionIfNeeded() {
        // 分支条件：首次使用定位功能时才请求系统权限，避免启动应用就打断用户。
        if authorizationStatus == .notDetermined {
            manager.requestWhenInUseAuthorization()
        }
    }

    func syncPendingSamples() async {
        guard let userUuid = currentUserUuid, let session else { return }
        let pending = pendingSamples(for: userUuid)
        guard !pending.isEmpty else { return }
        syncError = nil

        // 按行程和每批 100 条拆分，既满足后端契约，也让失败重试的范围保持小。
        let groups = Dictionary(grouping: pending, by: \.tripUuid)
        do {
            for (tripUuid, samples) in groups {
                for batch in samples.chunked(into: 100) {
                    let payload = LocationSyncPayload(tripUuid: tripUuid, samples: batch)
                    let _: LocationSyncResult = try await client.request(
                        path: "footprints/location-samples/sync",
                        method: "POST",
                        body: payload,
                        tokenProvider: session
                    )
                    removePendingSamples(batch, for: userUuid)
                }
            }
        } catch {
            // 同步失败时不删除本地队列，下一次采样、打开页面或手动刷新都会再次尝试。
            syncError = error.localizedDescription
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        // Core Location 的 delegate 不保证运行于 MainActor，先桥接回 UI 状态所属的主 Actor。
        let status = manager.authorizationStatus
        Task { @MainActor [weak self] in
            self?.handleAuthorizationChange(status)
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        // 分支条件：系统没有返回位置时无需创建异步任务。
        guard let location = locations.last else { return }
        Task { @MainActor [weak self] in
            self?.handleLocationUpdate(location)
        }
    }

    private func handleAuthorizationChange(_ status: CLAuthorizationStatus) {
        authorizationStatus = status
        // 分支条件：授权后存在已选择的行程时，恢复此前等待的定位采样。
        if isAuthorized, currentTripUuid != nil {
            manager.startUpdatingLocation()
            isTracking = true
        } else if !isAuthorized {
            stopTracking()
        }
    }

    private func handleLocationUpdate(_ location: CLLocation) {
        guard let tripUuid = currentTripUuid, let userUuid = currentUserUuid else { return }
        // 分支条件：系统报告负精度或缓存过旧坐标时，丢弃不可靠样本。
        guard location.horizontalAccuracy >= 0, location.timestamp > Date().addingTimeInterval(-120) else { return }
        let sample = PendingLocationSample(
            tripUuid: tripUuid,
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            accuracyM: location.horizontalAccuracy,
            speedMps: location.speed >= 0 ? location.speed : nil,
            recordedAt: location.timestamp
        )
        latestSample = sample
        append(sample, for: userUuid)
        Task { await syncPendingSamples() }
    }

    private var isAuthorized: Bool {
        authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways
    }

    private func storageKey(for userUuid: String) -> String {
        "vago.location.pending.\(userUuid)"
    }

    private func pendingSamples(for userUuid: String) -> [PendingLocationSample] {
        guard let data = UserDefaults.standard.data(forKey: storageKey(for: userUuid)) else { return [] }
        // 分支条件：本地缓存无法解码时清空损坏数据，避免它阻塞新的采样和同步。
        guard let samples = try? JSONDecoder().decode([PendingLocationSample].self, from: data) else {
            UserDefaults.standard.removeObject(forKey: storageKey(for: userUuid))
            return []
        }
        return samples
    }

    private func append(_ sample: PendingLocationSample, for userUuid: String) {
        var samples = pendingSamples(for: userUuid)
        samples.append(sample)
        save(samples, for: userUuid)
    }

    private func removePendingSamples(_ sentSamples: [PendingLocationSample], for userUuid: String) {
        let sentIds = Set(sentSamples.map(\.id))
        save(pendingSamples(for: userUuid).filter { !sentIds.contains($0.id) }, for: userUuid)
    }

    private func save(_ samples: [PendingLocationSample], for userUuid: String) {
        // UserDefaults 仅保存非敏感、短期 GPS 待传队列；登录令牌仍保存在 Keychain。
        if let data = try? JSONEncoder().encode(samples) {
            UserDefaults.standard.set(data, forKey: storageKey(for: userUuid))
        }
        pendingCount = samples.count
    }
}

private struct LocationSyncPayload: Encodable {
    let tripUuid: String
    let samples: [PendingLocationSample]
}

private extension Array {
    /// 将离线队列切成固定大小批次，避免一次网络请求过大。
    func chunked(into size: Int) -> [[Element]] {
        stride(from: 0, to: count, by: size).map { Array(self[$0..<Swift.min($0 + size, count)]) }
    }
}
