import Foundation

/// 协调足迹的本地与远端快照，供地图读取一份稳定、无重复的显示数据。
@MainActor
final class FootprintRepository: ObservableObject {
    @Published private(set) var displayPoints: [FootprintDisplayPoint] = []

    private var userUuid: String?
    private var tripUuid: String?
    private var remoteLocations: [FootprintLocation] = []
    // pending 样本来自 UserDefaults；每次远端刷新仍必须参与合并，不能被 GET 快照覆盖。
    private var pendingSamples: [PendingLocationSample] = []
    // 已确认点只保留在本次运行内，直到 GET 返回相同 clientUuid 后由远端快照接管。
    private var confirmedSamples: [PendingLocationSample] = []

    private static func activeTripStorageKey(for userUuid: String) -> String {
        "vago.footprint.active-trip.\(userUuid)"
    }

    static func cacheActiveTrip(_ trip: Trip, for userUuid: String) {
        // 仅保存最小行程摘要，供断网冷启动恢复本地足迹；服务端联网后仍会重新校验状态。
        guard let data = try? JSONEncoder().encode(trip) else { return }
        UserDefaults.standard.set(data, forKey: activeTripStorageKey(for: userUuid))
    }

    static func cachedActiveTrip(for userUuid: String) -> Trip? {
        guard let data = UserDefaults.standard.data(forKey: activeTripStorageKey(for: userUuid)) else { return nil }
        return try? JSONDecoder().decode(Trip.self, from: data)
    }

    func prepare(userUuid: String, tripUuid: String, tracking: LocationTrackingStore) {
        // 分支条件：账号或行程切换时丢弃旧内存快照，防止异步结果回填到新的地图。
        if self.userUuid != userUuid || self.tripUuid != tripUuid {
            self.userUuid = userUuid
            self.tripUuid = tripUuid
            remoteLocations = []
            pendingSamples = []
            confirmedSamples = []
        }
        refreshLocalSamples(from: tracking)
    }

    func replaceRemoteLocations(_ locations: [FootprintLocation]) {
        remoteLocations = locations
        // 远端已具备相同幂等键时，内存确认副本已完成交接，可安全释放。
        let remoteKeys = Set(locations.map { FootprintMergeKey.make(clientUuid: $0.clientUuid, fallbackServerUuid: $0.uuid) })
        confirmedSamples.removeAll { remoteKeys.contains(FootprintMergeKey.normalize($0.id.uuidString)) }
        rebuildDisplayPoints()
    }

    func refreshLocalSamples(from tracking: LocationTrackingStore) {
        guard let tripUuid else { return }
        pendingSamples = tracking.pendingSamples(for: tripUuid)
        rebuildDisplayPoints()
    }

    func recordConfirmedSamples(_ samples: [PendingLocationSample], tracking: LocationTrackingStore) {
        guard let tripUuid else { return }
        // 分支条件：只接收当前行程的成功批次，避免后台同步其他 Trip 时污染当前地图。
        let currentTripSamples = samples.filter { $0.tripUuid == tripUuid }
        let existingKeys = Set(confirmedSamples.map { FootprintMergeKey.normalize($0.id.uuidString) })
        confirmedSamples.append(contentsOf: currentTripSamples.filter {
            !existingKeys.contains(FootprintMergeKey.normalize($0.id.uuidString))
        })
        refreshLocalSamples(from: tracking)
    }

    private func rebuildDisplayPoints() {
        guard let tripUuid else {
            displayPoints = []
            return
        }
        var valuesByKey: [String: FootprintDisplayPoint] = [:]
        // 优先级依次提升：pending < confirmed < remote。远端读回后始终以服务端事实为准。
        for sample in pendingSamples where sample.tripUuid == tripUuid {
            let point = FootprintDisplayPoint.local(sample, source: .pending)
            valuesByKey[point.stableKey] = point
        }
        for sample in confirmedSamples where sample.tripUuid == tripUuid {
            let point = FootprintDisplayPoint.local(sample, source: .confirmed)
            valuesByKey[point.stableKey] = point
        }
        for location in remoteLocations {
            let point = FootprintDisplayPoint.remote(location, tripUuid: tripUuid)
            valuesByKey[point.stableKey] = point
        }
        displayPoints = valuesByKey.values.sorted {
            $0.recordedAt == $1.recordedAt ? $0.stableKey < $1.stableKey : $0.recordedAt < $1.recordedAt
        }
    }
}
