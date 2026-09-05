import CoreLocation
import Foundation

/// 供地图渲染的一段连续足迹；它是原始 GPS 样本的派生视图，不会改写服务端事实数据。
struct FootprintSegment: Identifiable {
    // 同一段的首尾样本 UUID 能在 SwiftUI 刷新时提供稳定标识。
    let id: String
    let locations: [FootprintLocation]

    var coordinates: [CLLocationCoordinate2D] {
        locations.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
    }

    var smoothedCoordinates: [CLLocationCoordinate2D] {
        FootprintRouteBuilder.smooth(coordinates)
    }
}

/// 将服务端返回的离散 GPS 采样整理为可阅读的个人旅行路线。
enum FootprintRouteBuilder {
    // 15 米内的连续样本通常只是 GPS 抖动或短时间重复回调，渲染时只保留较新的一个。
    static let minimumRenderDistanceMeters: CLLocationDistance = 15
    
    // 重要逻辑: 两次记录间隔过长或跨越过远时宁可断线，不能在地图上伪造一段经过路径。
    private static let maximumContinuousGap: TimeInterval = 5 * 60
    private static let maximumContinuousDistanceMeters: CLLocationDistance = 5_000

    static func segments(from locations: [FootprintLocation]) -> [FootprintSegment] {
        let sortedLocations = locations
            .filter(isValidCoordinate)
            // 服务端已经按时间排序；客户端仍显式排序，防止缓存、刷新或未来接口变化导致错误连线。
            .sorted {
                $0.recordedAt == $1.recordedAt ? $0.uuid < $1.uuid : $0.recordedAt < $1.recordedAt
            }
        guard !sortedLocations.isEmpty else { return [] }

        var results: [FootprintSegment] = []
        var currentSegment: [FootprintLocation] = [sortedLocations[0]]

        for location in sortedLocations.dropFirst() {
            guard let previous = currentSegment.last else { continue }
            let timeGap = location.recordedAt.timeIntervalSince(previous.recordedAt)
            let distance = distance(from: previous, to: location)

            // 分支条件：时间倒退、长时间无样本或异常远跳时关闭当前段，避免产生跨城市直线。
            if timeGap <= 0 || timeGap > maximumContinuousGap || distance > maximumContinuousDistanceMeters {
                results.append(makeSegment(currentSegment))
                currentSegment = [location]
            } else if distance < minimumRenderDistanceMeters {
                // 分支条件：连续点距离不足 15 米时用更新时间更晚的样本替换，保留最新位置且减少抖动。
                currentSegment[currentSegment.count - 1] = location
            } else {
                currentSegment.append(location)
            }
        }
        results.append(makeSegment(currentSegment))
        return results
    }

    /// 使用 Catmull-Rom 插值使密集 GPS 折线的视觉转折更自然；原始样本仍保留在两端经过。
    static func smooth(_ coordinates: [CLLocationCoordinate2D]) -> [CLLocationCoordinate2D] {
        guard coordinates.count >= 3 else { return coordinates }
        var result: [CLLocationCoordinate2D] = [coordinates[0]]
        // 每一段曲线通常由前后 4 个点共同决定
        for index in 0..<(coordinates.count - 1) {
            let p0 = coordinates[max(index - 1, 0)]
            let p1 = coordinates[index]
            let p2 = coordinates[index + 1]
            let p3 = coordinates[min(index + 2, coordinates.count - 1)]
            // 每段插入三个中间点；这是纯展示插值，不承担道路匹配或导航语义。
            for step in 1...4 {
                let t = Double(step) / 4
                result.append(catmullRom(p0: p0, p1: p1, p2: p2, p3: p3, t: t))
            }
        }
        return result
    }

    private static func makeSegment(_ locations: [FootprintLocation]) -> FootprintSegment {
        let firstID = locations.first?.uuid ?? "empty"
        let lastID = locations.last?.uuid ?? firstID
        return FootprintSegment(id: "\(firstID)-\(lastID)", locations: locations)
    }
    /// 过滤有效的坐标
    private static func isValidCoordinate(_ location: FootprintLocation) -> Bool {
        location.latitude.isFinite && location.longitude.isFinite
            && (-90...90).contains(location.latitude)
            && (-180...180).contains(location.longitude)
    }
    
    private static func distance(from lhs: FootprintLocation, to rhs: FootprintLocation) -> CLLocationDistance {
        CLLocation(latitude: lhs.latitude, longitude: lhs.longitude)
            .distance(from: CLLocation(latitude: rhs.latitude, longitude: rhs.longitude))
    }
    /// 计算Catmull-Rom 插值，用于平滑的曲线渲染
    private static func catmullRom(
        p0: CLLocationCoordinate2D,
        p1: CLLocationCoordinate2D,
        p2: CLLocationCoordinate2D,
        p3: CLLocationCoordinate2D,
        t: Double
    ) -> CLLocationCoordinate2D {
        let t2 = t * t
        let t3 = t2 * t
        func interpolate(_ a: Double, _ b: Double, _ c: Double, _ d: Double) -> Double {
            0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
        }
        return CLLocationCoordinate2D(
            latitude: interpolate(p0.latitude, p1.latitude, p2.latitude, p3.latitude),
            longitude: interpolate(p0.longitude, p1.longitude, p2.longitude, p3.longitude)
        )
    }
}
