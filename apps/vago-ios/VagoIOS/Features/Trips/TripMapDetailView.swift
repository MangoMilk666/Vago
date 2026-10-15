import SwiftUI

/// 指定行程的只读旅行地图；历史浏览与当前定位采集分开，避免误向历史行程写入足迹数据。
struct TripMapDetailView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var tracking: LocationTrackingStore
    let trip: Trip
    @State private var points: [FootprintDisplayPoint] = []
    @State private var isLoading = true
    @State private var errorMessage = ""
    @State private var isShowingCachedData = false
    // 仅控制自动 GPS 圆点图层；轨迹折线与手动打卡标记始终保留。
    @State private var areFootprintSamplesVisible = true
    private let client = APIClient()

    var body: some View {
        ZStack(alignment: .top) {
            TravelMapCanvas(
                locations: points,
                currentLocation: nil,
                locateRequestID: 0,
                areFootprintSamplesVisible: areFootprintSamplesVisible,
                // 历史浏览页不承担打卡编辑职责，点击标记不会打开会改变事实的编辑流程。
                onSelectCheckin: { _ in }
            )
            .ignoresSafeArea(edges: .bottom)

            if isLoading {
                ProgressView("正在读取旅行地图")
                    .padding()
                    .background(.ultraThinMaterial, in: Capsule())
            } else if !errorMessage.isEmpty {
                VStack(spacing: 10) {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                    Button("重新读取") { Task { await load() } }
                        .buttonStyle(.bordered)
                }
                .padding()
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
                .padding()
            } else if points.isEmpty {
                ContentUnavailableView("暂无足迹数据", systemImage: "map", description: Text("这份行程暂时还没有已同步的轨迹或打卡。"))
                    .padding()
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
                    .padding()
            }
            if isShowingCachedData {
                Text("离线显示本机已缓存的足迹")
                    .font(.footnote)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(.ultraThinMaterial, in: Capsule())
                    .frame(maxHeight: .infinity, alignment: .top)
                    .padding(.top, 12)
            }
        }
        .navigationTitle("旅行地图")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { areFootprintSamplesVisible.toggle() } label: {
                    Image(systemName: areFootprintSamplesVisible ? "circle.grid.2x2.fill" : "circle.grid.2x2")
                }
                .accessibilityLabel(areFootprintSamplesVisible ? "隐藏自动 GPS 采样点" : "显示自动 GPS 采样点")
            }
            ToolbarItem(placement: .topBarTrailing) {
                Button { Task { await load() } } label: { Image(systemName: "arrow.clockwise") }
                    .accessibilityLabel("刷新旅行地图")
            }
        }
        .task(id: trip.uuid) { await load() }
    }

    private func load() async {
        isLoading = true
        errorMessage = ""
        isShowingCachedData = false
        defer { isLoading = false }
        if let userUuid = session.profile?.uuid {
            let cached = LocalFootprintStore.shared.footprints(userUuid: userUuid, tripUuid: trip.uuid)
            let cachedPoints = cached.map { FootprintDisplayPoint.cached($0.footprint, pending: $0.isPendingUpload) }
            let pendingGPS = tracking.pendingSamples(for: trip.uuid, userUuid: userUuid)
                .map { FootprintDisplayPoint.local($0, source: .pending) }
            let localPoints = Self.merge(cachedPoints + pendingGPS)
            if !localPoints.isEmpty {
                points = localPoints
                isLoading = false
            }
        }
        do {
            let footprints: [TravelFootprint] = try await client.request(
                path: "footprints/trips/\(trip.uuid)/footprints",
                tokenProvider: session
            )
            // 服务端按发生时间返回足迹点位；地图显示模型交给现有分段构建器排序、断段与绘制。
            let pendingGPS: [FootprintDisplayPoint]
            if let userUuid = session.profile?.uuid {
                pendingGPS = tracking.pendingSamples(for: trip.uuid, userUuid: userUuid)
                    .map { FootprintDisplayPoint.local($0, source: .pending) }
            } else {
                pendingGPS = []
            }
            points = Self.merge(footprints.map(FootprintDisplayPoint.remote) + pendingGPS)
            if let userUuid = session.profile?.uuid {
                LocalFootprintStore.shared.replaceSnapshot(footprints, userUuid: userUuid, tripUuid: trip.uuid)
            }
        } catch {
            if points.isEmpty {
                errorMessage = error.localizedDescription
            } else {
                isShowingCachedData = true
            }
        }
    }

    private static func merge(_ points: [FootprintDisplayPoint]) -> [FootprintDisplayPoint] {
        var pointsByKey: [String: FootprintDisplayPoint] = [:]
        for point in points {
            // 同一 client event 同时存在于本地队列和服务端快照时，优先采用服务端事实。
            if let existing = pointsByKey[point.stableKey], case .remote = existing.source { continue }
            pointsByKey[point.stableKey] = point
        }
        return pointsByKey.values.sorted {
            $0.recordedAt == $1.recordedAt ? $0.stableKey < $1.stableKey : $0.recordedAt < $1.recordedAt
        }
    }
}
