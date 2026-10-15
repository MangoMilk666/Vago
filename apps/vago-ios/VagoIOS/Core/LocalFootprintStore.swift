import Foundation
import Combine
import SwiftData

/// 以 SwiftData 在设备磁盘保存已同步足迹副本和离线手动打卡。
@Model
final class LocalFootprintRecord {
    @Attribute(.unique) var storageKey: String
    var userUuid: String
    var tripUuid: String
    var serverUuid: String?
    var clientEventUuid: String
    var footprintType: String
    var latitude: Double
    var longitude: Double
    var accuracyM: Double?
    var speedMps: Double?
    var trackingSegmentUuid: String?
    var locationName: String?
    var note: String?
    var occurredAt: Date
    var isPendingUpload: Bool

    init(userUuid: String, footprint: TravelFootprint, isPendingUpload: Bool) {
        storageKey = Self.key(userUuid: userUuid, clientEventUuid: footprint.clientEventUuid)
        self.userUuid = userUuid
        tripUuid = footprint.tripUuid
        serverUuid = isPendingUpload ? nil : footprint.uuid
        clientEventUuid = footprint.clientEventUuid
        footprintType = footprint.footprintType.rawValue
        latitude = footprint.latitude
        longitude = footprint.longitude
        accuracyM = footprint.accuracyM
        speedMps = footprint.speedMps
        trackingSegmentUuid = footprint.trackingSegmentUuid
        locationName = footprint.locationName
        note = footprint.note
        occurredAt = footprint.occurredAt
        self.isPendingUpload = isPendingUpload
    }

    static func key(userUuid: String, clientEventUuid: String) -> String {
        "\(userUuid)|\(FootprintMergeKey.normalize(clientEventUuid))"
    }

    var footprint: TravelFootprint {
        TravelFootprint(
            uuid: serverUuid ?? clientEventUuid,
            clientEventUuid: clientEventUuid,
            tripUuid: tripUuid,
            footprintType: TravelFootprintType(rawValue: footprintType) ?? .automaticGPS,
            latitude: latitude,
            longitude: longitude,
            accuracyM: accuracyM,
            speedMps: speedMps,
            trackingSegmentUuid: trackingSegmentUuid,
            locationName: locationName,
            note: note,
            occurredAt: occurredAt
        )
    }
}

/// 封装 SwiftData 写入；Repository 和同步器共用同一份按账号隔离的磁盘数据。
@MainActor
final class LocalFootprintStore: ObservableObject {
    static let shared = LocalFootprintStore()

    @Published private(set) var persistenceError: String? = nil
    private let container: ModelContainer?

    init(inMemory: Bool = false, storeURL: URL? = nil) {
        do {
            let configuration = storeURL.map { ModelConfiguration(url: $0) }
                ?? ModelConfiguration(isStoredInMemoryOnly: inMemory)
            container = try ModelContainer(
                for: LocalFootprintRecord.self,
                configurations: configuration
            )
        } catch {
            container = nil
            persistenceError = "本地足迹数据库无法打开：\(error.localizedDescription)"
        }
    }

    func footprints(userUuid: String, tripUuid: String) -> [LocalFootprintRecord] {
        guard let context = container?.mainContext else { return [] }
        let user = userUuid
        let trip = tripUuid
        let descriptor = FetchDescriptor<LocalFootprintRecord>(
            predicate: #Predicate { $0.userUuid == user && $0.tripUuid == trip },
            sortBy: [SortDescriptor(\.occurredAt)]
        )
        return (try? context.fetch(descriptor)) ?? []
    }

    func pendingManualCheckins(userUuid: String) -> [LocalFootprintRecord] {
        guard let context = container?.mainContext else { return [] }
        let user = userUuid
        let descriptor = FetchDescriptor<LocalFootprintRecord>(
            predicate: #Predicate {
                $0.userUuid == user && $0.isPendingUpload && $0.footprintType == "MANUAL_CHECKIN"
            },
            sortBy: [SortDescriptor(\.occurredAt)]
        )
        return (try? context.fetch(descriptor)) ?? []
    }

    func replaceSnapshot(_ items: [TravelFootprint], userUuid: String, tripUuid: String) {
        guard let context = container?.mainContext else { return }
        let incomingKeys = Set(items.map { LocalFootprintRecord.key(userUuid: userUuid, clientEventUuid: $0.clientEventUuid) })
        for record in footprints(userUuid: userUuid, tripUuid: tripUuid)
        where !record.isPendingUpload && !incomingKeys.contains(record.storageKey) {
            context.delete(record)
        }
        for footprint in items where footprint.tripUuid == tripUuid {
            upsert(footprint, userUuid: userUuid, isPendingUpload: false, in: context)
        }
        save(context)
    }

    func upsert(_ footprint: TravelFootprint, userUuid: String, isPendingUpload: Bool) {
        guard let context = container?.mainContext else { return }
        upsert(footprint, userUuid: userUuid, isPendingUpload: isPendingUpload, in: context)
        save(context)
    }

    func upsertMany(_ items: [TravelFootprint], userUuid: String, isPendingUpload: Bool = false) {
        guard let context = container?.mainContext else { return }
        for footprint in items {
            upsert(footprint, userUuid: userUuid, isPendingUpload: isPendingUpload, in: context)
        }
        save(context)
    }

    private func upsert(_ footprint: TravelFootprint, userUuid: String, isPendingUpload: Bool, in context: ModelContext) {
        let storageKey = LocalFootprintRecord.key(userUuid: userUuid, clientEventUuid: footprint.clientEventUuid)
        let descriptor = FetchDescriptor<LocalFootprintRecord>(predicate: #Predicate { $0.storageKey == storageKey })
        if let record = try? context.fetch(descriptor).first {
            record.tripUuid = footprint.tripUuid
            record.serverUuid = isPendingUpload ? nil : footprint.uuid
            record.footprintType = footprint.footprintType.rawValue
            record.latitude = footprint.latitude
            record.longitude = footprint.longitude
            record.accuracyM = footprint.accuracyM
            record.speedMps = footprint.speedMps
            record.trackingSegmentUuid = footprint.trackingSegmentUuid
            record.locationName = footprint.locationName
            record.note = footprint.note
            record.occurredAt = footprint.occurredAt
            record.isPendingUpload = isPendingUpload
        } else {
            context.insert(LocalFootprintRecord(userUuid: userUuid, footprint: footprint, isPendingUpload: isPendingUpload))
        }
    }

    func deleteAll(for userUuid: String) {
        guard let context = container?.mainContext else { return }
        let user = userUuid
        let descriptor = FetchDescriptor<LocalFootprintRecord>(predicate: #Predicate { $0.userUuid == user })
        for record in (try? context.fetch(descriptor)) ?? [] {
            context.delete(record)
        }
        save(context)
    }

    private func save(_ context: ModelContext) {
        do {
            try context.save()
            persistenceError = nil
        } catch {
            persistenceError = "本地足迹保存失败：\(error.localizedDescription)"
        }
    }
}
