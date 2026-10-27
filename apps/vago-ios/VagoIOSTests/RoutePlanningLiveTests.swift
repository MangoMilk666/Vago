import MapKit
import XCTest
@testable import VagoIOS

final class RoutePlanningLiveTests: XCTestCase {
    func testMainlandWalkingRouteFromAppleMaps() async throws {
        try requireLiveMapService()
        try await verifyRoute(city: "杭州", from: "浙江大学 紫金港校区", to: "浙江工商大学 下沙校区")
    }

    func testHangzhouEnglishPlaceNamesAreSearchable() async throws {
        try requireLiveMapService()
        let university = try await MapKitPlaceSearch.search(city: "杭州", query: "Zhejiang University")
        let sportsCenter = try await MapKitPlaceSearch.search(city: "杭州", query: "Hangzhou Olympic sports center")
        XCTAssertFalse(university.isEmpty)
        XCTAssertFalse(sportsCenter.isEmpty)
    }

    func testOverseasWalkingRouteFromAppleMaps() async throws {
        try requireLiveMapService()
        try await verifyRoute(city: "新加坡", from: "Marina Bay Sands", to: "Merlion Park")
    }

    func testWalkingRoutesFromFixedCoordinatesWithoutPlaceSearch() async throws {
        // 测试：绕过地点搜索，分别确认三个地区的固定坐标能否取得真实步行路线。
        try requireLiveMapService()
        let cases: [(String, CLLocationCoordinate2D, CLLocationCoordinate2D)] = [
            ("杭州", CLLocationCoordinate2D(latitude: 30.2550, longitude: 120.1650), CLLocationCoordinate2D(latitude: 30.2530, longitude: 120.1700)),
            ("新加坡", CLLocationCoordinate2D(latitude: 1.2834, longitude: 103.8607), CLLocationCoordinate2D(latitude: 1.2868, longitude: 103.8545)),
            ("纽约", CLLocationCoordinate2D(latitude: 40.7580, longitude: -73.9855), CLLocationCoordinate2D(latitude: 40.7536, longitude: -73.9832)),
        ]
        for (city, origin, destination) in cases {
            let request = MKDirections.Request()
            request.source = MKMapItem(placemark: MKPlacemark(coordinate: origin))
            request.destination = MKMapItem(placemark: MKPlacemark(coordinate: destination))
            request.transportType = .walking
            do {
                let response = try await MKDirections(request: request).calculate()
                let first = response.routes.first
                print("MKDirections \(city): routes=\(response.routes.count), distance=\(first?.distance ?? 0), points=\(first?.polyline.pointCount ?? 0)")
                XCTAssertGreaterThan(first?.polyline.pointCount ?? 0, 1, "\(city) 未返回可绘制的路线")
            } catch {
                let detail = error as NSError
                XCTFail("\(city) 路线请求失败：\(detail.domain)/\(detail.code) \(detail.localizedDescription)；底层错误：\(detail.userInfo[NSUnderlyingErrorKey] ?? "无")")
            }
        }
    }

    private func verifyRoute(city: String, from originName: String, to destinationName: String) async throws {
        let origin = try await search(city: city, query: originName)
        let destination = try await search(city: city, query: destinationName)
        let distance = CLLocation(latitude: origin.placemark.coordinate.latitude, longitude: origin.placemark.coordinate.longitude)
            .distance(from: CLLocation(latitude: destination.placemark.coordinate.latitude, longitude: destination.placemark.coordinate.longitude))
        XCTAssertLessThan(distance, 100_000, "地点结果可能不在同一地区：\(origin.placemark.title ?? "") / \(destination.placemark.title ?? "")")
        let request = MKDirections.Request()
        request.source = origin
        request.destination = destination
        request.transportType = .walking
        let response = try await MKDirections(request: request).calculate()
        XCTAssertFalse(response.routes.isEmpty)
        XCTAssertGreaterThan(response.routes.first?.polyline.pointCount ?? 0, 1)
    }

    private func search(city: String, query: String) async throws -> MKMapItem {
        let items = try await MapKitPlaceSearch.search(city: city, query: query)
        return try XCTUnwrap(items.first, "地点查询无结果：\(city) / \(query)")
    }

    private func requireLiveMapService() throws {
        // 真实地图网络测试在 Xcode 的 Test Scheme 中设置环境变量后运行。
        try XCTSkipUnless(ProcessInfo.processInfo.environment["VAGO_MAPKIT_LIVE_TEST"] == "1")
    }
}
