import Foundation
import XCTest
@testable import VagoIOS

final class LocalFootprintStoreTests: XCTestCase {
    @MainActor
    func testCachedFootprintsSurviveStoreRecreationAndRemainUserIsolated() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("vago-footprints-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let databaseURL = directory.appendingPathComponent("footprints.store")
        let footprint = makeFootprint()

        var firstStore: LocalFootprintStore? = LocalFootprintStore(storeURL: databaseURL)
        firstStore?.upsert(footprint, userUuid: "user-a", isPendingUpload: true)
        XCTAssertNil(firstStore?.persistenceError)
        firstStore = nil

        var restoredStore: LocalFootprintStore? = LocalFootprintStore(storeURL: databaseURL)
        let restored = try XCTUnwrap(restoredStore?.footprints(userUuid: "user-a", tripUuid: "trip-a").first)
        XCTAssertEqual(restored.footprint.clientEventUuid, footprint.clientEventUuid)
        XCTAssertTrue(restored.isPendingUpload)
        XCTAssertTrue(restoredStore?.footprints(userUuid: "user-b", tripUuid: "trip-a").isEmpty == true)

        restoredStore?.upsert(footprint, userUuid: "user-a", isPendingUpload: false)
        let confirmed = try XCTUnwrap(restoredStore?.footprints(userUuid: "user-a", tripUuid: "trip-a").first)
        XCTAssertFalse(confirmed.isPendingUpload)
        XCTAssertEqual(confirmed.footprint.locationName, "离线打卡")
        restoredStore = nil
        try FileManager.default.removeItem(at: directory)
    }

    @MainActor
    func testSnapshotRefreshKeepsPendingCheckinAndReplacesSyncedHistory() throws {
        let store = LocalFootprintStore(inMemory: true)
        let synced = makeFootprint(event: "synced-event", name: "旧地点")
        let pending = makeFootprint(event: UUID().uuidString, name: "待同步")
        store.upsert(synced, userUuid: "user-a", isPendingUpload: false)
        store.upsert(pending, userUuid: "user-a", isPendingUpload: true)

        let refreshed = makeFootprint(event: "synced-event", name: "更新地点")
        store.replaceSnapshot([refreshed], userUuid: "user-a", tripUuid: "trip-a")

        let records = store.footprints(userUuid: "user-a", tripUuid: "trip-a")
        XCTAssertEqual(records.count, 2)
        XCTAssertEqual(records.first(where: { $0.clientEventUuid == "synced-event" })?.footprint.locationName, "更新地点")
        XCTAssertTrue(records.first(where: { $0.clientEventUuid == pending.clientEventUuid })?.isPendingUpload == true)
    }

    private func makeFootprint(event: String = UUID().uuidString, name: String = "离线打卡") -> TravelFootprint {
        TravelFootprint(
            uuid: event,
            clientEventUuid: event,
            tripUuid: "trip-a",
            footprintType: .manualCheckin,
            latitude: 1.3,
            longitude: 103.8,
            accuracyM: nil,
            speedMps: nil,
            trackingSegmentUuid: "segment-a",
            locationName: name,
            note: "本地保存",
            occurredAt: Date(timeIntervalSince1970: 1_000)
        )
    }
}
