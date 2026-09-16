import SwiftUI

/// 指定行程的只读旅行地图；历史浏览与当前定位采集分开，避免误向历史行程写入观察数据。
struct TripMapDetailView: View {
    @EnvironmentObject private var session: SessionStore
    let trip: Trip
    @State private var points: [FootprintDisplayPoint] = []
    @State private var isLoading = true
    @State private var errorMessage = ""
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
        defer { isLoading = false }
        do {
            let observations: [TravelObservation] = try await client.request(
                path: "footprints/trips/\(trip.uuid)/observations",
                tokenProvider: session
            )
            // 服务端观察按发生时间返回；地图显示模型仍保留统一观察类型，交给现有分段构建器排序、断段与绘制。
            points = observations.map(FootprintDisplayPoint.remote)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
