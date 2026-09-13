import Foundation

/// 地图的统一显示点：既可来自服务端快照，也可来自本地待传或刚确认的样本。
struct FootprintDisplayPoint: Identifiable {
    enum Source {
        case remote
        case confirmed
        case pending
    }

    // stableKey 是 user + Trip 范围内的合并键；远端 clientUuid 缺失时退回 server UUID。
    let stableKey: String
    let tripUuid: String
    let latitude: Double
    let longitude: Double
    let accuracyM: Double?
    let speedMps: Double?
    // 显式记录段用于稳定断线；nil 表示历史样本尚未携带该信息。
    let trackingSegmentUuid: String?
    let recordedAt: Date
    let source: Source

    var id: String { stableKey }

    static func remote(_ location: FootprintLocation, tripUuid: String) -> Self {
        Self(
            stableKey: FootprintMergeKey.make(clientUuid: location.clientUuid, fallbackServerUuid: location.uuid),
            tripUuid: tripUuid,
            latitude: location.latitude,
            longitude: location.longitude,
            accuracyM: location.accuracyM,
            speedMps: location.speedMps,
            trackingSegmentUuid: location.trackingSegmentUuid,
            recordedAt: location.recordedAt,
            source: .remote
        )
    }

    static func local(_ sample: PendingLocationSample, source: Source) -> Self {
        Self(
            stableKey: FootprintMergeKey.normalize(sample.id.uuidString),
            tripUuid: sample.tripUuid,
            latitude: sample.latitude,
            longitude: sample.longitude,
            accuracyM: sample.accuracyM,
            speedMps: sample.speedMps,
            trackingSegmentUuid: sample.trackingSegmentUuid,
            recordedAt: sample.recordedAt,
            source: source
        )
    }
}

/// 后端允许任意非空字符串作幂等键；只有可解析 UUID 才规范化大小写，其他值保持原文。
enum FootprintMergeKey {
    static func make(clientUuid: String?, fallbackServerUuid: String) -> String {
        guard let clientUuid, !clientUuid.isEmpty else { return "server:\(fallbackServerUuid)" }
        return normalize(clientUuid)
    }

    static func normalize(_ value: String) -> String {
        UUID(uuidString: value)?.uuidString.lowercased() ?? value
    }
}
