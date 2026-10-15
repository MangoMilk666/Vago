import CoreLocation
import XCTest
@testable import VagoIOS

final class FootprintGeometryTests: XCTestCase {
    func testWalkingSegmentKeepsManualCheckinAsRouteVertex() {
        let points = [
            point("gps-a", northMeters: 0, minute: 0, segment: "segment-a"),
            point("checkin", northMeters: 25, minute: 1, segment: "segment-a", kind: .manualCheckin),
            point("gps-b", northMeters: 50, minute: 2, segment: "segment-a"),
        ]

        let segments = FootprintRouteBuilder.segments(from: points)

        XCTAssertEqual(segments.count, 1)
        XCTAssertEqual(segments[0].locations.map(\.stableKey), ["gps-a", "checkin", "gps-b"])
    }

    func testExplicitRestartAndLowQualityFixCreateBoundaries() {
        let points = [
            point("before", northMeters: 0, minute: 0, segment: "segment-a"),
            point("restart", northMeters: 30, minute: 1, segment: "segment-b"),
            point("poor-fix", northMeters: 60, minute: 2, segment: "segment-b", accuracy: 250),
            point("after", northMeters: 90, minute: 3, segment: "segment-b"),
        ]

        let segments = FootprintRouteBuilder.segments(from: points)

        XCTAssertEqual(segments.map { $0.locations.map(\.stableKey) }, [["before"], ["restart"], ["after"]])
    }

    func testLowQualityFixBreaksRouteButDoesNotExpandViewport() {
        let before = point("before", northMeters: 0, minute: 0, segment: "same")
        let drift = FootprintDisplayPoint(
            stableKey: "drift",
            serverUuid: nil,
            tripUuid: "trip",
            latitude: 1,
            longitude: 0,
            accuracyM: 250,
            speedMps: 1,
            trackingSegmentUuid: "same",
            recordedAt: Date(timeIntervalSince1970: 60),
            source: .remote,
            kind: .automaticGPS,
            locationName: nil,
            note: nil
        )
        let after = point("after", northMeters: 100, minute: 2, segment: "same")
        let checkin = point("checkin", northMeters: 50, minute: 3, segment: "same", kind: .manualCheckin)
        let footprints = [before, drift, after, checkin]

        let segments = FootprintRouteBuilder.segments(from: footprints)
        let viewport = FootprintRouteBuilder.viewportLocations(
            from: segments,
            manualCheckins: [checkin]
        )

        XCTAssertEqual(segments.map { $0.locations.map(\.stableKey) }, [["before"], ["after", "checkin"]])
        XCTAssertEqual(Set(viewport.map(\.stableKey)), ["before", "after", "checkin"])
        XCTAssertFalse(viewport.contains { $0.stableKey == "drift" })
        XCTAssertLessThan(viewport.map(\.latitude).max() ?? 0, 1)
    }

    func testLongGapAndCrossCityJumpDoNotConnectWithinSameSegmentID() {
        let points = [
            point("nearby", northMeters: 0, minute: 0, segment: "same"),
            point("after-long-gap", northMeters: 20, minute: 180, segment: "same"),
            point("city-jump", northMeters: 100_000, minute: 181, segment: "same"),
        ]

        let segments = FootprintRouteBuilder.segments(from: points)

        XCTAssertEqual(segments.map { $0.locations.map(\.stableKey) }, [["nearby"], ["after-long-gap"], ["city-jump"]])
    }

    func testReportedSuspiciousSpeedSeparatesBothSidesOfFootprint() {
        let points = [
            point("before", northMeters: 0, minute: 0, segment: "same"),
            point("fast", northMeters: 30, minute: 1, segment: "same", speed: 80),
            point("after", northMeters: 60, minute: 2, segment: "same"),
        ]

        let segments = FootprintRouteBuilder.segments(from: points)

        XCTAssertEqual(segments.map { $0.locations.map(\.stableKey) }, [["before"], ["fast"], ["after"]])
    }

    func testLegacyFootprintsWithoutSegmentIDCanStillConnect() {
        let points = [
            point("older", northMeters: 0, minute: 0, segment: nil),
            point("middle", northMeters: 25, minute: 1, segment: nil),
            point("newer", northMeters: 50, minute: 2, segment: nil),
        ]

        let segments = FootprintRouteBuilder.segments(from: [points[2], points[0], points[1]])

        XCTAssertEqual(segments.count, 1)
        XCTAssertEqual(segments[0].locations.map(\.stableKey), ["older", "middle", "newer"])
    }

    func testSmoothingFallsBackForSharpTurnAndSparseEdge() {
        let corner = [coordinate(northMeters: 0, eastMeters: 0), coordinate(northMeters: 20, eastMeters: 0), coordinate(northMeters: 20, eastMeters: 20)]
        let sparse = [coordinate(northMeters: 0, eastMeters: 0), coordinate(northMeters: 200, eastMeters: 0), coordinate(northMeters: 220, eastMeters: 0)]
        let smallLoop = [
            coordinate(northMeters: 0, eastMeters: 0),
            coordinate(northMeters: 20, eastMeters: 0),
            coordinate(northMeters: 20, eastMeters: 20),
            coordinate(northMeters: 0, eastMeters: 20),
            coordinate(northMeters: 0, eastMeters: 0),
        ]
        let gentleWalk = [
            coordinate(northMeters: 0, eastMeters: 0),
            coordinate(northMeters: 20, eastMeters: 0),
            coordinate(northMeters: 40, eastMeters: 3),
            coordinate(northMeters: 60, eastMeters: 8),
        ]

        XCTAssertEqual(FootprintRouteBuilder.smooth(corner).count, corner.count)
        XCTAssertEqual(FootprintRouteBuilder.smooth(sparse).count, sparse.count)
        XCTAssertEqual(FootprintRouteBuilder.smooth(smallLoop).count, smallLoop.count)
        XCTAssertGreaterThan(FootprintRouteBuilder.smooth(gentleWalk).count, gentleWalk.count)
    }

    @MainActor
    func testLocalPointRemainsVisibleUntilRemoteSnapshotTakesOver() throws {
        let userUuid = "footprint-test-\(UUID().uuidString)"
        let tripUuid = "trip-test"
        let storageKey = "vago.location.pending.\(userUuid)"
        let defaults = UserDefaults.standard
        defer { defaults.removeObject(forKey: storageKey) }

        let sample = PendingLocationSample(
            tripUuid: tripUuid,
            latitude: 1.3,
            longitude: 103.8,
            accuracyM: 8,
            speedMps: 1,
            trackingSegmentUuid: "segment-a",
            recordedAt: Date(timeIntervalSince1970: 1_000)
        )
        defaults.set(try JSONEncoder().encode([sample]), forKey: storageKey)

        let tracking = LocationTrackingStore()
        tracking.prepare(tripUuid: tripUuid, userUuid: userUuid, session: SessionStore())
        let repository = FootprintRepository()
        repository.prepare(userUuid: userUuid, tripUuid: tripUuid, tracking: tracking)
        XCTAssertEqual(repository.displayPoints.map(\.stableKey), [sample.id.uuidString.lowercased()])

        repository.recordConfirmedSamples([sample], tracking: tracking)
        defaults.set(try JSONEncoder().encode([PendingLocationSample]()), forKey: storageKey)
        repository.refreshLocalSamples(from: tracking)
        XCTAssertEqual(repository.displayPoints.count, 1)

        let remote = TravelFootprint(
            uuid: "server-footprint",
            clientEventUuid: sample.id.uuidString.lowercased(),
            tripUuid: tripUuid,
            footprintType: .automaticGPS,
            latitude: sample.latitude,
            longitude: sample.longitude,
            accuracyM: sample.accuracyM,
            speedMps: sample.speedMps,
            trackingSegmentUuid: sample.trackingSegmentUuid,
            locationName: nil,
            note: nil,
            occurredAt: sample.recordedAt
        )
        repository.replaceRemoteFootprints([remote])

        XCTAssertEqual(repository.displayPoints.count, 1)
        XCTAssertEqual(repository.displayPoints.first?.source, .remote)
    }

    func testPointDensityFollowsProjectedScreenSpacingAndKeepsTurnsAndEndpoints() {
        let points = [
            point("a", northMeters: 0, eastMeters: 0, minute: 0, segment: "s"),
            point("b", northMeters: 10, eastMeters: 0, minute: 1, segment: "s"),
            point("c", northMeters: 20, eastMeters: 0, minute: 2, segment: "s"),
            point("turn", northMeters: 30, eastMeters: 0, minute: 3, segment: "s"),
            point("d", northMeters: 30, eastMeters: 10, minute: 4, segment: "s"),
            point("checkin", northMeters: 30, eastMeters: 15, minute: 5, segment: "s", kind: .manualCheckin),
            point("e", northMeters: 30, eastMeters: 20, minute: 6, segment: "s"),
            point("end", northMeters: 30, eastMeters: 30, minute: 7, segment: "s"),
        ]
        let segment = FootprintSegment(id: "s", locations: points)
        let street = FootprintPointSelector.visibleAutomaticKeys(in: [segment], project: { projected($0, scale: 2) })
        let world = FootprintPointSelector.visibleAutomaticKeys(in: [segment], project: { projected($0, scale: 0.2) })

        XCTAssertGreaterThan(street.count, world.count)
        XCTAssertTrue(street.contains("a"))
        XCTAssertTrue(street.contains("turn"))
        XCTAssertTrue(street.contains("end"))
        XCTAssertFalse(street.contains("checkin"))
        XCTAssertTrue(world.contains("a"))
        XCTAssertTrue(world.contains("end"))
    }

    private func point(
        _ key: String,
        northMeters: Double,
        eastMeters: Double = 0,
        minute: Int,
        segment: String?,
        kind: FootprintDisplayPoint.FootprintKind = .automaticGPS,
        accuracy: Double? = 8,
        speed: Double? = 1
    ) -> FootprintDisplayPoint {
        FootprintDisplayPoint(
            stableKey: key,
            serverUuid: nil,
            tripUuid: "trip",
            latitude: northMeters / 111_320,
            longitude: eastMeters / 111_320,
            accuracyM: kind == .manualCheckin ? nil : accuracy,
            speedMps: kind == .manualCheckin ? nil : speed,
            trackingSegmentUuid: segment,
            recordedAt: Date(timeIntervalSince1970: TimeInterval(minute * 60)),
            source: .pending,
            kind: kind,
            locationName: nil,
            note: nil
        )
    }

    private func coordinate(northMeters: Double, eastMeters: Double) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: northMeters / 111_320, longitude: eastMeters / 111_320)
    }

    private func projected(_ coordinate: CLLocationCoordinate2D, scale: CGFloat) -> CGPoint {
        CGPoint(x: coordinate.longitude * 111_320 * scale, y: coordinate.latitude * 111_320 * scale)
    }
}
