import CoreLocation
import Foundation

/// 供地图渲染的一段连续足迹；它是原始 GPS 样本的派生视图，不会改写服务端事实数据。
struct FootprintSegment: Identifiable {
    // 同一段的首尾稳定合并键能在 SwiftUI 刷新时提供稳定标识。
    let id: String
    let locations: [FootprintDisplayPoint]

    var coordinates: [CLLocationCoordinate2D] {
        locations.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
    }

    var smoothedCoordinates: [CLLocationCoordinate2D] {
        FootprintRouteBuilder.smooth(FootprintRouteBuilder.lineCoordinates(from: locations))
    }
}

/// 将服务端返回的离散 GPS 采样整理为可阅读的个人旅行路线。
enum FootprintRouteBuilder {
    // 线条显示可略去相近顶点；可信连接仍逐点检查完整足迹。
    static let minimumLineVertexDistanceMeters: CLLocationDistance = 15

    // 两端使用相同阈值，避免弱信号长缺口、停止重启或城市跳跃被误画成连续路线。
    private static let maximumSparseGap: TimeInterval = 20 * 60
    private static let maximumDistanceAcrossSparseGapMeters: CLLocationDistance = 1_000
    private static let maximumHardGap: TimeInterval = 2 * 60 * 60
    private static let maximumContinuousDistanceMeters: CLLocationDistance = 5_000
    private static let maximumTrustedAccuracyMeters: CLLocationAccuracy = 100
    private static let maximumLikelyContinuousSpeedMetersPerSecond: CLLocationSpeed = 55
    private static let maximumSmoothEdgeMeters: CLLocationDistance = 120
    private static let maximumSmoothTurnDegrees: Double = 65
    private static let maximumSmoothDeviationMeters: CLLocationDistance = 5

    static func segments(from locations: [FootprintDisplayPoint]) -> [FootprintSegment] {
        // 保留质量差或坐标无效的时间位置作为断线信号，不能先过滤后把它两侧的样本直接连上。
        let sortedLocations = locations.sorted(by: isEarlierInRoute)
        guard !sortedLocations.isEmpty else { return [] }

        var results: [FootprintSegment] = []
        var currentSegment: [FootprintDisplayPoint] = []

        for location in sortedLocations {
            // 分支条件：无效坐标、低质量自动定位或损坏速度值构成断点，点本身不参与路线几何。
            guard isValidCoordinate(location), isUsableMotion(location) else {
                appendIfRenderable(currentSegment, to: &results)
                currentSegment = []
                continue
            }

            guard let previous = currentSegment.last else {
                currentSegment = [location]
                continue
            }

            let timeGap = location.recordedAt.timeIntervalSince(previous.recordedAt)
            let distance = distance(from: previous, to: location)
            let hasSparseGapWithLargeMove = timeGap > maximumSparseGap && distance > maximumDistanceAcrossSparseGapMeters

            // 分支条件：显式段切换、时间倒退、长时间停顿、稀疏大位移或不可信连接时关闭当前段。
            if hasExplicitSegmentBoundary(previous, location)
                || timeGap <= 0
                || timeGap > maximumHardGap
                || hasSparseGapWithLargeMove
                || isUntrustworthyConnection(distance: distance, timeGap: timeGap, previous: previous, next: location) {
                appendIfRenderable(currentSegment, to: &results)
                currentSegment = [location]
            } else {
                // 连续段保存每一个可信足迹点位，后续的显示筛选不能改变断线判断。
                currentSegment.append(location)
            }
        }
        appendIfRenderable(currentSegment, to: &results)
        return results
    }

    /// 只简化线条的显示顶点；段首尾、手动打卡和明确转角仍沿用原始位置。
    static func lineCoordinates(from locations: [FootprintDisplayPoint]) -> [CLLocationCoordinate2D] {
        guard locations.count > 2 else { return locations.map(coordinate(for:)) }
        var selected = [locations[0]]
        for index in 1..<(locations.count - 1) {
            let location = locations[index]
            let previous = locations[index - 1]
            let next = locations[index + 1]
            let isTurn = turnAngle(
                previous: coordinate(for: previous),
                vertex: coordinate(for: location),
                next: coordinate(for: next)
            ) > maximumSmoothTurnDegrees
            // 手动打卡是路线事实顶点；自动点只有足够远或形成转角时才需要画进线条。
            if location.kind == .manualCheckin
                || isTurn
                || distance(from: selected[selected.count - 1], to: location) >= minimumLineVertexDistanceMeters {
                selected.append(location)
            }
        }
        selected.append(locations[locations.count - 1])
        return selected.map(coordinate(for:))
    }

    /// 自动取景围住可信路线点与有效手动打卡；低质量 GPS 仍用于分段，但不拉远镜头。
    static func viewportLocations(
        from segments: [FootprintSegment],
        manualCheckins: [FootprintDisplayPoint]
    ) -> [FootprintDisplayPoint] {
        var locationsByKey: [String: FootprintDisplayPoint] = [:]
        for location in segments.flatMap(\.locations) + manualCheckins where isValidCoordinate(location) {
            locationsByKey[location.stableKey] = location
        }
        return locationsByKey.values.sorted { $0.stableKey < $1.stableKey }
    }

    /// 只对平缓、密集且插值偏离受限的路线使用 Catmull-Rom；其余退回原始圆角折线。
    static func smooth(_ coordinates: [CLLocationCoordinate2D]) -> [CLLocationCoordinate2D] {
        guard coordinates.count >= 3 else { return coordinates }
        guard isSafeToSmooth(coordinates) else { return coordinates }
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

    private static func makeSegment(_ locations: [FootprintDisplayPoint]) -> FootprintSegment {
        let firstID = locations.first?.stableKey ?? "empty"
        let lastID = locations.last?.stableKey ?? firstID
        return FootprintSegment(id: "\(firstID)-\(lastID)", locations: locations)
    }

    private static func appendIfRenderable(
        _ locations: [FootprintDisplayPoint],
        to results: inout [FootprintSegment]
    ) {
        guard !locations.isEmpty else { return }
        results.append(makeSegment(locations))
    }

    /// 过滤有效的坐标
    private static func isValidCoordinate(_ location: FootprintDisplayPoint) -> Bool {
        location.latitude.isFinite && location.longitude.isFinite
            && (-90...90).contains(location.latitude)
            && (-180...180).contains(location.longitude)
    }

    private static func isUsableMotion(_ location: FootprintDisplayPoint) -> Bool {
        guard location.kind == .automaticGPS else { return true }
        // 分支条件：无精度的旧点可兼容；负值、非有限值和超过 100 米的低质量自动点成为断点。
        if let accuracy = location.accuracyM,
           (!accuracy.isFinite || accuracy < 0 || accuracy > maximumTrustedAccuracyMeters) {
            return false
        }
        // 分支条件：速度缺失的旧点可兼容；负值或非有限速度字段不用于可信轨迹。
        if let speed = location.speedMps, (!speed.isFinite || speed < 0) {
            return false
        }
        return true
    }

    private static func isEarlierInRoute(_ lhs: FootprintDisplayPoint, _ rhs: FootprintDisplayPoint) -> Bool {
        // 分支条件：时间相同时按 stableKey 排序，保证远端与本地合并后仍有确定的路线连接顺序。
        lhs.recordedAt == rhs.recordedAt ? lhs.stableKey < rhs.stableKey : lhs.recordedAt < rhs.recordedAt
    }
    
    private static func distance(from lhs: FootprintDisplayPoint, to rhs: FootprintDisplayPoint) -> CLLocationDistance {
        CLLocation(latitude: lhs.latitude, longitude: lhs.longitude)
            .distance(from: CLLocation(latitude: rhs.latitude, longitude: rhs.longitude))
    }

    private static func coordinate(for location: FootprintDisplayPoint) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: location.latitude, longitude: location.longitude)
    }

    private static func hasExplicitSegmentBoundary(_ previous: FootprintDisplayPoint, _ next: FootprintDisplayPoint) -> Bool {
        // 分支条件：两个历史点都没有段标识时继续使用旧的时间/距离推断；只要一侧有标识且不同就保守断开。
        previous.trackingSegmentUuid != nil || next.trackingSegmentUuid != nil
            ? previous.trackingSegmentUuid != next.trackingSegmentUuid
            : false
    }

    private static func isUntrustworthyConnection(
        distance: CLLocationDistance,
        timeGap: TimeInterval,
        previous: FootprintDisplayPoint,
        next: FootprintDisplayPoint
    ) -> Bool {
        guard timeGap > 0 else { return true }
        // 超过 5 公里的点仍保留为新段端点；这里只拒绝“把两点连线”的解释，不删除旅行事实。
        if distance > maximumContinuousDistanceMeters { return true }
        let impliedSpeed = distance / timeGap
        let hasReportedImpossibleSpeed = max(previous.speedMps ?? 0, next.speedMps ?? 0) > maximumLikelyContinuousSpeedMetersPerSecond
        // 分支条件：推算或设备上报速度超过约 198 km/h 时，不将其解释为可信步行/旅行轨迹。
        return impliedSpeed > maximumLikelyContinuousSpeedMetersPerSecond || hasReportedImpossibleSpeed
    }

    private static func isSafeToSmooth(_ coordinates: [CLLocationCoordinate2D]) -> Bool {
        for index in 1..<(coordinates.count - 1) {
            let previous = coordinates[index - 1]
            let vertex = coordinates[index]
            let next = coordinates[index + 1]
            let incomingDistance = coordinateDistance(previous, vertex)
            let outgoingDistance = coordinateDistance(vertex, next)
            // 分支条件：有稀疏长边或急转时保留原始折线，避免插值切角、过冲或抹掉小环路。
            if incomingDistance > maximumSmoothEdgeMeters || outgoingDistance > maximumSmoothEdgeMeters
                || turnAngle(previous: previous, vertex: vertex, next: next) > maximumSmoothTurnDegrees {
                return false
            }
        }

        for index in 0..<(coordinates.count - 1) {
            let p0 = coordinates[max(index - 1, 0)]
            let p1 = coordinates[index]
            let p2 = coordinates[index + 1]
            let p3 = coordinates[min(index + 2, coordinates.count - 1)]
            let edgeLength = coordinateDistance(p1, p2)
            let allowedDeviation = min(maximumSmoothDeviationMeters, edgeLength * 0.15)
            for step in 1...3 {
                let candidate = catmullRom(p0: p0, p1: p1, p2: p2, p3: p3, t: Double(step) / 4)
                // 分支条件：插值点离原始足迹点连线超过容差时回退，原始坐标始终不被改写。
                if distance(candidate, fromSegmentStart: p1, to: p2) > allowedDeviation { return false }
            }
        }
        return true
    }

    private static func coordinateDistance(_ lhs: CLLocationCoordinate2D, _ rhs: CLLocationCoordinate2D) -> CLLocationDistance {
        CLLocation(latitude: lhs.latitude, longitude: lhs.longitude)
            .distance(from: CLLocation(latitude: rhs.latitude, longitude: rhs.longitude))
    }

    private static func turnAngle(
        previous: CLLocationCoordinate2D,
        vertex: CLLocationCoordinate2D,
        next: CLLocationCoordinate2D
    ) -> Double {
        let latitudeScale = 111_320.0
        let longitudeScale = latitudeScale * cos(vertex.latitude * .pi / 180)
        let incoming = CLLocationCoordinate2D(
            latitude: (vertex.latitude - previous.latitude) * latitudeScale,
            longitude: (vertex.longitude - previous.longitude) * longitudeScale
        )
        let outgoing = CLLocationCoordinate2D(
            latitude: (next.latitude - vertex.latitude) * latitudeScale,
            longitude: (next.longitude - vertex.longitude) * longitudeScale
        )
        let incomingLength = hypot(incoming.latitude, incoming.longitude)
        let outgoingLength = hypot(outgoing.latitude, outgoing.longitude)
        guard incomingLength > 0, outgoingLength > 0 else { return 180 }
        let dotProduct = incoming.latitude * outgoing.latitude + incoming.longitude * outgoing.longitude
        let cosine = min(1, max(-1, dotProduct / (incomingLength * outgoingLength)))
        return acos(cosine) * 180 / .pi
    }

    private static func distance(
        _ point: CLLocationCoordinate2D,
        fromSegmentStart start: CLLocationCoordinate2D,
        to end: CLLocationCoordinate2D
    ) -> CLLocationDistance {
        let latitudeScale = 111_320.0
        let longitudeScale = latitudeScale * cos(start.latitude * .pi / 180)
        let startX = start.longitude * longitudeScale
        let startY = start.latitude * latitudeScale
        let endX = end.longitude * longitudeScale
        let endY = end.latitude * latitudeScale
        let pointX = point.longitude * longitudeScale
        let pointY = point.latitude * latitudeScale
        let deltaX = endX - startX
        let deltaY = endY - startY
        let lengthSquared = deltaX * deltaX + deltaY * deltaY
        guard lengthSquared > 0 else { return hypot(pointX - startX, pointY - startY) }
        let projection = min(1, max(0, ((pointX - startX) * deltaX + (pointY - startY) * deltaY) / lengthSquared))
        let nearestX = startX + projection * deltaX
        let nearestY = startY + projection * deltaY
        return hypot(pointX - nearestX, pointY - nearestY)
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

/// 仅筛选地图上的自动采样圆点；底层路线和打卡 Annotation 使用完整数据，不受缩放影响。
enum FootprintPointSelector {
    // 地图可见宽度超过街道级范围时只画路线；此值只影响自动点的显示。
    static let maximumVisibleWidthMeters: CLLocationDistance = 2_500

    private struct Candidate {
        let key: String
        let point: CGPoint
        let priority: Int
        let order: Int
    }

    private struct Cell: Hashable {
        let x: Int
        let y: Int
    }

    static func visibleAutomaticKeys(
        in segments: [FootprintSegment],
        manualCheckins: [FootprintDisplayPoint] = [],
        visibleWidthMeters: CLLocationDistance,
        project: (CLLocationCoordinate2D) -> CGPoint?,
        visibleRect: CGRect? = nil,
        minimumSpacing: CGFloat = 30,
        turnThresholdDegrees: CGFloat = 35
    ) -> Set<String> {
        guard visibleWidthMeters <= maximumVisibleWidthMeters else { return [] }
        var candidates: [Candidate] = []
        var order = 0
        for segment in segments {
            let automaticIndexes = segment.locations.indices.filter { segment.locations[$0].kind == .automaticGPS }
            for (automaticOrder, index) in automaticIndexes.enumerated() {
                let location = segment.locations[index]
                guard let point = project(coordinate(for: location)), point.x.isFinite, point.y.isFinite,
                      visibleRect?.contains(point) ?? true else { continue }
                let isEndpoint = automaticOrder == 0 || automaticOrder == automaticIndexes.count - 1
                let hasNeighbors = index > 0 && index < segment.locations.count - 1
                let isTurn = hasNeighbors && turnAngle(
                    project(coordinate(for: segment.locations[index - 1])),
                    point,
                    project(coordinate(for: segment.locations[index + 1]))
                ) >= turnThresholdDegrees
                candidates.append(Candidate(
                    key: location.stableKey,
                    point: point,
                    priority: isEndpoint ? 2 : (isTurn ? 1 : 0),
                    order: order
                ))
                order += 1
            }
        }

        // 优先挑选段首尾和转角，但所有候选最终都须避开已经显示的圆点。
        candidates.sort { $0.priority == $1.priority ? $0.order < $1.order : $0.priority > $1.priority }
        var occupied: [Cell: [CGPoint]] = [:]
        for checkin in manualCheckins {
            if let point = project(coordinate(for: checkin)), point.x.isFinite, point.y.isFinite {
                occupied[cell(for: point, spacing: minimumSpacing), default: []].append(point)
            }
        }
        var visibleKeys = Set<String>()
        for candidate in candidates {
            let cell = cell(for: candidate.point, spacing: minimumSpacing)
            var overlaps = false
            for x in (cell.x - 1)...(cell.x + 1) {
                for y in (cell.y - 1)...(cell.y + 1) {
                    if occupied[Cell(x: x, y: y), default: []].contains(where: {
                        hypot(candidate.point.x - $0.x, candidate.point.y - $0.y) < minimumSpacing
                    }) {
                        overlaps = true
                        break
                    }
                }
                if overlaps { break }
            }
            if overlaps { continue }
            visibleKeys.insert(candidate.key)
            occupied[cell, default: []].append(candidate.point)
        }
        return visibleKeys
    }

    private static func cell(for point: CGPoint, spacing: CGFloat) -> Cell {
        Cell(x: Int(floor(point.x / spacing)), y: Int(floor(point.y / spacing)))
    }

    private static func coordinate(for point: FootprintDisplayPoint) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: point.latitude, longitude: point.longitude)
    }

    private static func turnAngle(_ previous: CGPoint?, _ vertex: CGPoint?, _ next: CGPoint?) -> CGFloat {
        guard let previous, let vertex, let next else { return 0 }
        let incoming = CGPoint(x: vertex.x - previous.x, y: vertex.y - previous.y)
        let outgoing = CGPoint(x: next.x - vertex.x, y: next.y - vertex.y)
        let incomingLength = hypot(incoming.x, incoming.y)
        let outgoingLength = hypot(outgoing.x, outgoing.y)
        guard incomingLength > 0, outgoingLength > 0 else { return 0 }
        let cosine = min(1, max(-1, (incoming.x * outgoing.x + incoming.y * outgoing.y) / (incomingLength * outgoingLength)))
        return acos(cosine) * 180 / .pi
    }
}
