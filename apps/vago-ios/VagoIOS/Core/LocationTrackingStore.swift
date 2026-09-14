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
    @Published private(set) var isSyncing = false
    // 本地队列每次增删都会递增，Repository 据此合并最新磁盘快照而不直接修改队列。
    @Published private(set) var localQueueRevision = 0
    // 每次同步结束发布已确认批次，地图 Repository 据此保留点位直到远端 GET 接管。
    @Published private(set) var lastConfirmedSamples: [PendingLocationSample] = []
    @Published private(set) var syncCompletionRevision = 0
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
    private var syncDelayTask: Task<Void, Never>?
    private var retrySyncTask: Task<Void, Never>?
    private var retryAttempt = 0
    // 每次用户开始记录或从后台回到前台都会创建新段，避免把中断前后的点错误连成一条线。
    private var trackingSegmentUuid: String?

    // 以下阈值只拦截确定不可用的实时定位，不用来删除真实但跨度较大的旅行移动。
    private let maximumAcceptedAccuracyMeters: CLLocationAccuracy = 100
    private let maximumPastSampleAge: TimeInterval = 120
    private let maximumFutureSampleOffset: TimeInterval = 60
    // 指南针方向是 GPS course 不可用（例如刚开始移动、低速行走）时的显示兜底，并不进入足迹数据。
    private var latestHeadingDegrees: CLLocationDirection?
    // 移动中的 GPS course 优先级高于手机朝向，避免用户手持角度改变时箭头偏离实际行进方向。
    private var latestCourseHeadingDegrees: CLLocationDirection?

    override init() {
        // override 表示重写 NSObject 的构造方法；super.init() 必须在使用 self 前完成。
        authorizationStatus = CLLocationManager().authorizationStatus
        super.init()
        manager.delegate = self
        // 第一版仅在 App 前台以约 20 米间隔采样，先控制功耗和隐私边界。
        manager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
        manager.distanceFilter = 20
        // 约 5 度才回调一次，避免用户轻微晃动手机时地图上的方向箭头持续抖动。
        manager.headingFilter = 5
    }

    func startTracking(tripUuid: String, userUuid: String, session: SessionStore) {
        // 将运行期上下文准备与“开始系统定位”分开，页面加载时可单独调用 prepare 恢复离线队列。
        prepare(tripUuid: tripUuid, userUuid: userUuid, session: session)
        hasRecordingIntent = true
        trackingSegmentUuid = UUID().uuidString.lowercased()
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
        pendingCount = allPendingSamples(for: userUuid).count
        localQueueRevision += 1
    }

    func stopTracking() {
        // 用户明确停止后清除记录意图；之后的授权或迟到定位回调不得再次写入足迹。
        hasRecordingIntent = false
        trackingSegmentUuid = nil
        manager.stopUpdatingLocation()
        manager.stopUpdatingHeading()
        isTracking = false
        // 用户停止记录时立即尝试交接仍在设备中的样本，无需等待定时器。
        Task { _ = await syncPendingSamples() }
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
                startHeadingUpdatesIfAvailable()
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
            // 回到前台是网络恢复后的常见时机，复用同一上传器重试离线队列。
            Task { _ = await syncPendingSamples() }
        } else {
            retrySyncTask?.cancel()
            retrySyncTask = nil
            manager.stopUpdatingLocation()
            manager.stopUpdatingHeading()
            isTracking = false
            // 分支条件：前台连续记录被生命周期打断时清空旧段，恢复后必须生成新的持久化边界。
            trackingSegmentUuid = nil
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

    /// 同步当前账号的离线样本，返回本次已被服务端确认、可交给地图临时保留的样本。
    func syncPendingSamples() async -> [PendingLocationSample] {
        // guard let 是 Swift 的提前返回写法：缺少登录上下文时不进入后续嵌套逻辑。
        guard let userUuid = currentUserUuid, let session else { return [] }
        // 分支条件：已有上传请求时不并发发起第二个请求，避免相同批次交叉删除或触发服务端限流。
        guard !isSyncing else { return [] }
        let pending = allPendingSamples(for: userUuid)
        guard !pending.isEmpty else { return [] }
        isSyncing = true
        defer { isSyncing = false }
        syncError = nil
        var confirmed: [PendingLocationSample] = []
        var errors: [String] = []
        var hasRetryableError = false

        // 按行程和每批 100 条拆分，既满足后端契约，也让失败重试的范围保持小。
        // KeyPath 写法 \.tripUuid 表示“取元素的 tripUuid 属性”，用于按行程分组。
        let groups = Dictionary(grouping: pending, by: \.tripUuid)
        for (tripUuid, samples) in groups {
            for batch in samples.chunked(into: 100) {
                do {
                    let payload = LocationSyncPayload(tripUuid: tripUuid, samples: batch)
                    let _: LocationSyncResult = try await client.request(
                        path: "footprints/location-samples/sync",
                        method: "POST",
                        body: payload,
                        tokenProvider: session
                    )
                    removePendingSamples(batch, for: userUuid)
                    confirmed.append(contentsOf: batch)
                } catch {
                    // 分支条件：某个 Trip 无法上传时只停止该行程后续批次，其余 Trip 仍可继续同步。
                    errors.append("\(tripUuid)：\(error.localizedDescription)")
                    hasRetryableError = hasRetryableError || isRetryableSyncError(error)
                    break
                }
            }
        }
        // 同步失败时不删除该批队列，下一次定时、前台恢复或手动刷新都会再次尝试。
        syncError = errors.isEmpty ? nil : errors.joined(separator: "\n")
        lastConfirmedSamples = confirmed
        syncCompletionRevision += 1
        // 分支条件：仅临时网络和服务端错误进入有限退避；删除行程等业务错误保留队列并等待用户处理。
        if hasRetryableError {
            scheduleRetryIfNeeded()
        } else if errors.isEmpty {
            retryAttempt = 0
        }
        return confirmed
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
        // 分支条件：系统没有返回位置时无需创建异步任务；有效数组中的每个点都应按时间处理，不能只取最后一个。
        guard !locations.isEmpty else { return }
        Task { @MainActor [weak self] in
            self?.handleLocationUpdates(locations)
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor [weak self] in
            self?.handleLocationFailure(error)
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        // 先在 delegate 线程提取 Sendable 的 Double，不能把非 Sendable 的 CLHeading 系统对象跨 Actor 传给主线程。
        let trueHeading = newHeading.trueHeading
        let magneticHeading = newHeading.magneticHeading
        Task { @MainActor [weak self] in
            self?.handleHeadingUpdate(trueHeading: trueHeading, magneticHeading: magneticHeading)
        }
    }

    private func handleAuthorizationChange(_ status: CLAuthorizationStatus) {
        authorizationStatus = status
        // 分支条件：授权后仅恢复用户已明确开始的记录，或补发等待中的一次定位请求。
        if isAuthorized {
            locationError = nil
            if locationRequestContinuation != nil {
                startHeadingUpdatesIfAvailable()
                manager.requestLocation()
            }
            resumeTrackingIfNeeded()
        } else if !isAuthorized {
            manager.stopUpdatingLocation()
            manager.stopUpdatingHeading()
            isTracking = false
            if authorizationStatus != .notDetermined {
                locationError = "未获得定位权限，请在系统设置中允许 Vago 使用定位。"
                finishLocationRequest(with: .failure(LocationRequestError.permissionDenied))
            }
        }
    }

    private func handleLocationUpdates(_ locations: [CLLocation]) {
        var didReceiveValidFix = false
        for location in locations.sorted(by: { $0.timestamp < $1.timestamp }) {
            // 分支条件：坐标、时间或精度明显无效时仅丢弃本点，不让一次漂移阻断后续正常样本。
            guard isUsableRealtimeLocation(location) else { continue }
            didReceiveValidFix = true
            updateCourseHeading(from: location)
            let fix = CurrentLocationFix(
                coordinate: location.coordinate,
                recordedAt: location.timestamp,
                accuracyM: location.horizontalAccuracy,
                headingDegrees: preferredHeading()
            )
            // 每次有效回调都更新可展示的当前位置；Locate 不需要行程，也绝不因此保存轨迹。
            currentLocation = fix
            locationError = nil
            finishLocationRequest(with: .success(fix))
            appendTrackingSampleIfNeeded(from: location)
        }
        // 分支条件：本批 Core Location 回调没有任何可信点时才提示失败，避免有效点后被一个坏点覆盖状态。
        if !didReceiveValidFix {
            locationError = "暂时无法取得有效定位，请稍后重试。"
        }
    }

    private func appendTrackingSampleIfNeeded(from location: CLLocation) {
        // 分支条件：仅用户已开始记录、应用在前台且会话/行程完整时才持久化 GPS 样本。
        guard hasRecordingIntent, isAppActive,
              let tripUuid = currentTripUuid,
              let userUuid = currentUserUuid,
              let session,
              case .signedIn = session.state else { return }
        // 分支条件：同一时间和坐标的重复 delegate 回调没有新旅行事实，不写入队列。
        if let latestSample,
           latestSample.tripUuid == tripUuid,
           latestSample.recordedAt == location.timestamp,
           latestSample.latitude == location.coordinate.latitude,
           latestSample.longitude == location.coordinate.longitude {
            return
        }
        let sample = PendingLocationSample(
            tripUuid: tripUuid,
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            accuracyM: location.horizontalAccuracy,
            speedMps: location.speed >= 0 ? location.speed : nil,
            trackingSegmentUuid: trackingSegmentUuid,
            recordedAt: location.timestamp
        )
        latestSample = sample
        append(sample, for: userUuid)
        scheduleSyncAfterSampling()
    }

    private func isUsableRealtimeLocation(_ location: CLLocation, now: Date = Date()) -> Bool {
        let coordinate = location.coordinate
        // isFinite 排除 NaN/Infinity；范围检查防止异常驱动把无效坐标带入持久化队列。
        guard coordinate.latitude.isFinite, coordinate.longitude.isFinite,
              (-90...90).contains(coordinate.latitude), (-180...180).contains(coordinate.longitude),
              location.horizontalAccuracy >= 0, location.horizontalAccuracy <= maximumAcceptedAccuracyMeters else {
            return false
        }
        let age = now.timeIntervalSince(location.timestamp)
        return age <= maximumPastSampleAge && age >= -maximumFutureSampleOffset
    }

    private func handleHeadingUpdate(trueHeading: CLLocationDirection, magneticHeading: CLLocationDirection) {
        // 分支条件：trueHeading 不可用时 Core Location 返回负数，此时采用磁北方向；两者都无效则保留旧值。
        let candidate = trueHeading >= 0 ? trueHeading : magneticHeading
        guard candidate.isFinite, candidate >= 0 else { return }
        latestHeadingDegrees = candidate
        // 指南针先到、GPS 点后到是正常时序；已有位置时仅更新箭头方向，不改变坐标或采样时间。
        if let currentLocation {
            self.currentLocation = CurrentLocationFix(
                coordinate: currentLocation.coordinate,
                recordedAt: currentLocation.recordedAt,
                accuracyM: currentLocation.accuracyM,
                headingDegrees: preferredHeading()
            )
        }
    }

    private func updateCourseHeading(from location: CLLocation) {
        // 分支条件：设备有可靠移动速度和 GPS course 时优先使用真实行进方向，避免手机朝向与前进方向不同。
        if location.speed >= 0.5, location.course >= 0, location.course.isFinite {
            latestCourseHeadingDegrees = location.course
        } else {
            // 分支条件：当前 GPS 点无法证明设备仍在移动时释放旧 course，改由实时指南针方向驱动箭头。
            latestCourseHeadingDegrees = nil
        }
    }

    private func preferredHeading() -> CLLocationDirection? {
        latestCourseHeadingDegrees ?? latestHeadingDegrees
    }

    private func startHeadingUpdatesIfAvailable() {
        // heading 来自 Core Location，不需要新增运动/陀螺仪授权；没有硬件能力的设备安全跳过。
        guard CLLocationManager.headingAvailable(), isAuthorized else { return }
        manager.startUpdatingHeading()
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
        // 分支条件：从后台中断恢复时旧段已被清空，现在创建新段以在服务端和其他设备上保留断点。
        if trackingSegmentUuid == nil {
            trackingSegmentUuid = UUID().uuidString.lowercased()
        }
        startHeadingUpdatesIfAvailable()
        manager.startUpdatingLocation()
        isTracking = true
    }

    private func resetRuntimeState() {
        manager.stopUpdatingLocation()
        manager.stopUpdatingHeading()
        hasRecordingIntent = false
        finishLocationRequest(with: .failure(LocationRequestError.cancelled))
        isTracking = false
        currentLocation = nil
        latestSample = nil
        latestHeadingDegrees = nil
        latestCourseHeadingDegrees = nil
        trackingSegmentUuid = nil
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

    /// 返回当前账号指定行程的磁盘待传快照；只读暴露给 Repository，写入仍由 Store 管理。
    func pendingSamples(for tripUuid: String) -> [PendingLocationSample] {
        guard let currentUserUuid else { return [] }
        return allPendingSamples(for: currentUserUuid).filter { $0.tripUuid == tripUuid }
    }

    private func storageKey(for userUuid: String) -> String {
        // 以 userUuid 隔离 UserDefaults key，避免同一设备切换账号后混读待传轨迹。
        "vago.location.pending.\(userUuid)"
    }

    private func allPendingSamples(for userUuid: String) -> [PendingLocationSample] {
        guard let data = UserDefaults.standard.data(forKey: storageKey(for: userUuid)) else { return [] }
        // 分支条件：本地缓存无法解码时清空损坏数据，避免它阻塞新的采样和同步。
        guard let samples = try? JSONDecoder().decode([PendingLocationSample].self, from: data) else {
            UserDefaults.standard.removeObject(forKey: storageKey(for: userUuid))
            return []
        }
        return samples
    }

    private func append(_ sample: PendingLocationSample, for userUuid: String) {
        var samples = allPendingSamples(for: userUuid)
        samples.append(sample)
        save(samples, for: userUuid)
    }

    private func removePendingSamples(_ sentSamples: [PendingLocationSample], for userUuid: String) {
        let sentIds = Set(sentSamples.map(\.id))
        save(allPendingSamples(for: userUuid).filter { !sentIds.contains($0.id) }, for: userUuid)
    }

    private func save(_ samples: [PendingLocationSample], for userUuid: String) {
        // UserDefaults 仅保存非敏感、短期 GPS 待传队列；登录令牌仍保存在 Keychain。
        if let data = try? JSONEncoder().encode(samples) {
            UserDefaults.standard.set(data, forKey: storageKey(for: userUuid))
        }
        pendingCount = samples.count
        localQueueRevision += 1
    }

    private func scheduleSyncAfterSampling() {
        guard let currentUserUuid else { return }
        // 分支条件：积累到 20 点时立即上传；较少样本在约 30 秒后合并上传，降低网络抖动和限流风险。
        if allPendingSamples(for: currentUserUuid).count >= 20 {
            syncDelayTask?.cancel()
            syncDelayTask = nil
            Task { _ = await syncPendingSamples() }
        } else if syncDelayTask == nil {
            syncDelayTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(30))
                guard !Task.isCancelled else { return }
                self?.syncDelayTask = nil
                _ = await self?.syncPendingSamples()
            }
        }
    }

    private func isRetryableSyncError(_ error: Error) -> Bool {
        if let apiError = error as? APIError,
           case let .server(_, statusCode) = apiError {
            return statusCode == 429 || statusCode >= 500
        }
        // URLSession 失败通常是弱网或断网，保留同一 clientUuid 后可以安全重试。
        return !(error is APIError)
    }

    private func scheduleRetryIfNeeded() {
        guard retrySyncTask == nil else { return }
        retryAttempt = min(retryAttempt + 1, 4)
        let delay = min(30.0 * pow(2, Double(retryAttempt - 1)), 300.0)
        retrySyncTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard !Task.isCancelled else { return }
            self?.retrySyncTask = nil
            // 分支条件：退避结束后仅前台重试，遵守当前应用不申请后台定位/上传的边界。
            guard self?.isAppActive == true else { return }
            _ = await self?.syncPendingSamples()
        }
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
