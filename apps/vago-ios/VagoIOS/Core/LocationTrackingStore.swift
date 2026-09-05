import CoreLocation
import Foundation
import SwiftUI

/// 管理定位权限、前台采样与离线队列；服务端仍是最终的足迹数据源。
@MainActor
final class LocationTrackingStore: NSObject, ObservableObject, CLLocationManagerDelegate {
    // 继承 NSObject 是采用 Objective-C Core Location delegate 协议的系统要求。
    // 这些 @Published 值驱动 TrackingView；private(set) 防止 View 直接篡改定位状态。
    @Published private(set) var authorizationStatus: CLAuthorizationStatus
    @Published private(set) var currentLocation: CurrentLocationFix?
    @Published private(set) var latestSample: PendingLocationSample?
    @Published private(set) var isTracking = false
    @Published private(set) var pendingCount = 0
    @Published private(set) var syncError: String?
    @Published private(set) var locationError: String?
    @Published private(set) var isRequestingCurrentLocation = false

    // CLLocationManager 是系统定位服务入口；delegate 回调由它主动调用。
    private let manager = CLLocationManager()
    private let client = APIClient()
    private var currentTripUuid: String?
    private var currentUserUuid: String?
    private var session: SessionStore?
    // 用户点过“开始记录”才为 true；页面切换、定位授权或一次 Locate 都不能隐式打开它。
    private var hasRecordingIntent = false
    // 本项目只申请前台定位，进入后台时停止连续采样，回到前台再依据记录意图恢复。
    private var isAppActive = true
    // Continuation 将 Core Location delegate 的回调桥接为 async/await，供“点击打卡后获取一次新位置”使用。
    private var locationRequestContinuation: CheckedContinuation<CurrentLocationFix, Error>?
    private var locationRequestTimeoutTask: Task<Void, Never>?

    override init() {
        // override 表示重写 NSObject 的构造方法；super.init() 必须在使用 self 前完成。
        authorizationStatus = CLLocationManager().authorizationStatus
        super.init()
        manager.delegate = self
        // 第一版仅在 App 前台以约 20 米间隔采样，先控制功耗和隐私边界。
        manager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
        manager.distanceFilter = 20
    }

    func startTracking(tripUuid: String, userUuid: String, session: SessionStore) {
        // 将运行期上下文准备与“开始系统定位”分开，页面加载时可单独调用 prepare 恢复离线队列。
        prepare(tripUuid: tripUuid, userUuid: userUuid, session: session)
        hasRecordingIntent = true
        locationError = nil
        requestLocationPermissionIfNeeded()
        // 分支条件：用户已授予定位权限时立即开始采样；否则等待系统回调后的授权结果。
        resumeTrackingIfNeeded()
    }

    func prepare(tripUuid: String, userUuid: String, session: SessionStore) {
        // 页面加载可先恢复待传队列，但不得因此主动请求系统定位权限。
        // 分支条件：账号切换时清空运行期位置，避免 A 账号的当前坐标短暂显示在 B 的地图上。
        if let currentUserUuid, currentUserUuid != userUuid {
            resetRuntimeState()
        }
        currentTripUuid = tripUuid
        currentUserUuid = userUuid
        self.session = session
        pendingCount = pendingSamples(for: userUuid).count
    }

    func stopTracking() {
        // 用户明确停止后清除记录意图；之后的授权或迟到定位回调不得再次写入足迹。
        hasRecordingIntent = false
        manager.stopUpdatingLocation()
        isTracking = false
    }

    /// 为地图定位触发一次异步请求；调用方不需要等待结果时使用这个便捷入口。
    func requestCurrentLocation() {
        Task { _ = try? await requestFreshLocation() }
    }

    /// 请求一条新的 GPS 坐标并等待结果；单次请求不会进入足迹离线队列。
    func requestFreshLocation() async throws -> CurrentLocationFix {
        // 分支条件：定位尚在进行时拒绝第二次请求，避免多个按钮各自等待同一个系统回调。
        guard locationRequestContinuation == nil else {
            throw LocationRequestError.requestInProgress
        }
        locationError = nil
        isRequestingCurrentLocation = true
        return try await withCheckedThrowingContinuation { continuation in
            locationRequestContinuation = continuation
            requestLocationPermissionIfNeeded()
            // 分支条件：已有权限时立即请求坐标；首次授权完成后由授权 delegate 继续请求。
            if isAuthorized {
                manager.requestLocation()
            } else if authorizationStatus != .notDetermined {
                finishLocationRequest(with: .failure(LocationRequestError.permissionDenied))
            }
            // 分支条件：同步获知权限被拒绝时 continuation 已结束，无需再创建无效超时任务。
            guard locationRequestContinuation != nil else { return }
            locationRequestTimeoutTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(10))
                // 分支条件：十秒内仍没有 delegate 回调时结束等待，按钮恢复可点击而不是永久 loading。
                guard !Task.isCancelled else { return }
                self?.finishLocationRequest(with: .failure(LocationRequestError.timedOut))
            }
        }
    }

    /// App 生命周期由应用根部转交，避免某个 Tab 或 sheet 的显示状态意外停止记录。
    func handleScenePhase(_ phase: ScenePhase) {
        isAppActive = phase == .active
        // 分支条件：应用离开前台时停止连续定位；恢复前台才按用户先前意图继续记录。
        if isAppActive {
            resumeTrackingIfNeeded()
        } else {
            manager.stopUpdatingLocation()
            isTracking = false
        }
    }

    /// 注销或账号切换时只清理内存、停止系统服务，不删除按 userUuid 隔离的离线待传队列。
    func reset() {
        resetRuntimeState()
        currentTripUuid = nil
        currentUserUuid = nil
        session = nil
        pendingCount = 0
    }

    func requestLocationPermissionIfNeeded() {
        // 分支条件：首次使用定位功能时才请求系统权限，避免启动应用就打断用户。
        if authorizationStatus == .notDetermined {
            manager.requestWhenInUseAuthorization()
        }
    }

    func syncPendingSamples() async {
        // guard let 是 Swift 的提前返回写法：缺少登录上下文时不进入后续嵌套逻辑。
        guard let userUuid = currentUserUuid, let session else { return }
        let pending = pendingSamples(for: userUuid)
        guard !pending.isEmpty else { return }
        syncError = nil

        // 按行程和每批 100 条拆分，既满足后端契约，也让失败重试的范围保持小。
        // KeyPath 写法 \.tripUuid 表示“取元素的 tripUuid 属性”，用于按行程分组。
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
        // nonisolated 允许系统在非主 Actor 回调该方法；UI 更新再显式切回 @MainActor。
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

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor [weak self] in
            self?.handleLocationFailure(error)
        }
    }

    private func handleAuthorizationChange(_ status: CLAuthorizationStatus) {
        authorizationStatus = status
        // 分支条件：授权后仅恢复用户已明确开始的记录，或补发等待中的一次定位请求。
        if isAuthorized {
            locationError = nil
            if locationRequestContinuation != nil {
                manager.requestLocation()
            }
            resumeTrackingIfNeeded()
        } else if !isAuthorized {
            manager.stopUpdatingLocation()
            isTracking = false
            if authorizationStatus != .notDetermined {
                locationError = "未获得定位权限，请在系统设置中允许 Vago 使用定位。"
                finishLocationRequest(with: .failure(LocationRequestError.permissionDenied))
            }
        }
    }

    private func handleLocationUpdate(_ location: CLLocation) {
        // CLLocation 同时包含坐标、精度、速度和时间戳，是 Core Location 的单次原始测量结果。
        // 分支条件：系统报告负精度或缓存过旧坐标时，丢弃不可靠样本。
        guard location.horizontalAccuracy >= 0, location.timestamp > Date().addingTimeInterval(-120) else {
            locationError = "暂时无法取得有效定位，请稍后重试。"
            return
        }
        // 每次有效回调都先更新可展示的当前位置；Locate 不需要行程，也绝不因此保存轨迹。
        let fix = CurrentLocationFix(
            coordinate: location.coordinate,
            recordedAt: location.timestamp,
            accuracyM: location.horizontalAccuracy
        )
        currentLocation = fix
        locationError = nil
        finishLocationRequest(with: .success(fix))
        // 分支条件：仅用户已开始记录、应用在前台且会话/行程完整时才持久化 GPS 样本。
        guard hasRecordingIntent, isAppActive,
              let tripUuid = currentTripUuid,
              let userUuid = currentUserUuid,
              let session,
              case .signedIn = session.state else { return }
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
        // Task 创建独立异步任务，采样回调无需等待上传结束，避免阻塞后续定位事件。
        Task { await syncPendingSamples() }
    }

    private func handleLocationFailure(_ error: Error) {
        // 分支条件：locationUnknown 是系统可恢复的临时状态，继续等待本次十秒请求的后续回调。
        if let locationError = error as? CLError, locationError.code == .locationUnknown {
            return
        }
        // CLError 可识别用户关闭位置服务等常见情形，其余错误保留系统提供的本地化说明。
        if let locationError = error as? CLError, locationError.code == .denied {
            self.locationError = "定位服务已关闭，请在系统设置中开启后重试。"
        } else {
            locationError = "定位失败：\(error.localizedDescription)"
        }
        finishLocationRequest(with: .failure(error))
    }

    private func resumeTrackingIfNeeded() {
        // 分支条件：只有前台、已授权、用户仍希望记录且上下文有效时才恢复连续采样。
        guard isAppActive, isAuthorized, hasRecordingIntent,
              currentTripUuid != nil, currentUserUuid != nil,
              let session, case .signedIn = session.state else { return }
        manager.startUpdatingLocation()
        isTracking = true
    }

    private func resetRuntimeState() {
        manager.stopUpdatingLocation()
        hasRecordingIntent = false
        finishLocationRequest(with: .failure(LocationRequestError.cancelled))
        isTracking = false
        currentLocation = nil
        latestSample = nil
        syncError = nil
        locationError = nil
    }

    private func finishLocationRequest(with result: Result<CurrentLocationFix, Error>) {
        let continuation = locationRequestContinuation
        locationRequestContinuation = nil
        locationRequestTimeoutTask?.cancel()
        locationRequestTimeoutTask = nil
        isRequestingCurrentLocation = false
        continuation?.resume(with: result)
    }

    private var isAuthorized: Bool {
        // 计算属性每次读取时根据当前授权状态计算，不额外存储可能过期的 Bool。
        authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways
    }

    private func storageKey(for userUuid: String) -> String {
        // 以 userUuid 隔离 UserDefaults key，避免同一设备切换账号后混读待传轨迹。
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

/// 单次定位的可预期失败类型，View 可据此展示稳定文案而不依赖系统原始错误文本。
private enum LocationRequestError: LocalizedError {
    case permissionDenied
    case requestInProgress
    case timedOut
    case cancelled

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "未获得定位权限，请在系统设置中允许 Vago 使用定位。"
        case .requestInProgress:
            return "正在获取当前位置，请稍候。"
        case .timedOut:
            return "暂时无法获取当前位置，请检查定位后重试。"
        case .cancelled:
            return "定位请求已取消。"
        }
    }
}

private struct LocationSyncPayload: Encodable {
    // 后端 batch sync 契约：每个请求只属于一个行程，samples 是该行程的本地样本列表。
    let tripUuid: String
    let samples: [PendingLocationSample]
}

private extension Array {
    /// 将离线队列切成固定大小批次，避免一次网络请求过大。
    func chunked(into size: Int) -> [[Element]] {
        stride(from: 0, to: count, by: size).map { Array(self[$0..<Swift.min($0 + size, count)]) }
    }
}
