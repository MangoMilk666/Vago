import CoreLocation
import MapKit
import SwiftUI

/// 地图画布只负责渲染个人空间数据；定位和网络请求仍由上层现有能力处理。
struct TravelMapCanvas: View {
    // 三类输入分别来自服务端轨迹、服务端打卡与当前定位；当前定位不必已经保存成足迹。
    let locations: [FootprintLocation]
    let checkins: [Checkin]
    let currentLocation: CurrentLocationFix?
    let locateRequestID: Int
    // MapCameraPosition 是 SwiftUI Map 的可写镜头状态，允许跟随与用户自由浏览共存。
    @State private var cameraPosition: MapCameraPosition = .automatic
    @State private var cameraMode: CameraMode = .automatic
    @State private var hasInitializedCamera = false
    @State private var routeSegments: [FootprintSegment] = []

    private enum CameraMode {
        case automatic
        case following
        case freeBrowsing
    }

    var body: some View {
        // Map 的闭包是 MapContentBuilder，内部声明的 Marker、Annotation、Polyline 会成为地图叠加物。
        Map(position: $cameraPosition) {
            // 每段都由时间顺序的有效 GPS 样本构成，断段后不会再用直线穿越未经过区域。
            ForEach(routeSegments) { segment in
                if segment.locations.count > 1 {
                    MapPolyline(coordinates: segment.smoothedCoordinates)
                        // 双层圆角描边让路线更接近旅行足迹，而不是一组生硬的 sample 连线。
                        .stroke(.indigo.opacity(0.22), style: StrokeStyle(lineWidth: 8, lineCap: .round, lineJoin: .round))
                    MapPolyline(coordinates: segment.smoothedCoordinates)
                        .stroke(.indigo, style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
                } else if let location = segment.locations.first {
                    // 分支条件：孤立点不连线，只用轻量符号表达曾取得过一次有效位置。
                    Marker("轨迹", coordinate: coordinate(for: location))
                        .tint(.indigo)
                }
            }
            // Annotation 支持自定义 SwiftUI 内容，因此打卡使用彩色 SF Symbol 与普通轨迹区分。
            ForEach(checkins) { checkin in
                Annotation(checkin.locationName, coordinate: coordinate(for: checkin)) {
                    Image(systemName: "mappin.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.orange)
                        .shadow(radius: 2)
                }
            }
            // 分支条件：有有效定位时显示唯一当前位置标记，不再与旧采样 Marker 争夺语义。
            if let currentLocation {
                Annotation("当前位置", coordinate: currentLocation.coordinate) {
                    Image(systemName: "location.circle.fill")
                        .font(.title)
                        .foregroundStyle(.blue)
                        .background(.white, in: Circle())
                }
            }
        }
        .mapStyle(.standard(elevation: .realistic))
        .mapControls {
            MapCompass()
            MapScaleView()
        }
        .onAppear {
            rebuildRoutes()
            // 页面初次进入已请求定位时，后续回调应直接带动镜头回到用户当前位置。
            if locateRequestID > 0 {
                cameraMode = .following
                moveCameraToCurrentLocation()
            }
            initializeCameraIfNeeded()
        }
        .onChange(of: contentSignature) { _, _ in
            // 分支条件：首批远端数据到达时才自动适配范围；后续刷新不得抢走用户已拖动的镜头。
            rebuildRoutes()
            initializeCameraIfNeeded()
        }
        .onChange(of: locateRequestID) { _, _ in
            cameraMode = .following
            moveCameraToCurrentLocation()
        }
        .onChange(of: currentLocation?.recordedAt) { _, _ in
            // 分支条件：只有跟随模式才随新的 GPS 回调移动，自由浏览时保留用户手势结果。
            if cameraMode == .following {
                moveCameraToCurrentLocation()
            }
        }
        .onChange(of: cameraPosition) { _, newPosition in
            // positionedByUser 由 MapKit 标记真实手势移动；程序设置 camera 不会取消用户请求的跟随。
            if newPosition.positionedByUser {
                cameraMode = .freeBrowsing
            }
        }
    }

    private func coordinate(for location: FootprintLocation) -> CLLocationCoordinate2D {
        // MapKit 使用 CLLocationCoordinate2D；领域模型保留 Double 便于 JSON 解码与服务端契约对齐。
        CLLocationCoordinate2D(latitude: location.latitude, longitude: location.longitude)
    }

    private func coordinate(for checkin: Checkin) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: checkin.latitude, longitude: checkin.longitude)
    }

    private var contentSignature: String {
        // 仅以服务端内容的稳定标识触发首屏初始化，不因每次 SwiftUI body 重算而重置镜头。
        locations.map(\.uuid).joined(separator: ",") + checkins.map(\.uuid).joined(separator: ",")
    }

    private func rebuildRoutes() {
        // 将纯计算结果缓存为 State，Map camera 的细小变化不会重复处理整段轨迹。
        routeSegments = FootprintRouteBuilder.segments(from: locations)
    }

    private func initializeCameraIfNeeded() {
        guard !hasInitializedCamera else { return }
        // 分支条件：尚无任何远端资料时保持自动区域，待第一批数据回来再适配真实范围。
        guard !locations.isEmpty || !checkins.isEmpty || currentLocation != nil else { return }
        hasInitializedCamera = true
        cameraPosition = .region(fittedRegion)
    }

    private func moveCameraToCurrentLocation() {
        guard let currentLocation else { return }
        cameraPosition = .region(
            MKCoordinateRegion(center: currentLocation.coordinate, latitudinalMeters: 900, longitudinalMeters: 900)
        )
    }

    private var fittedRegion: MKCoordinateRegion {
        var coordinates = locations.map(coordinate(for:)) + checkins.map(coordinate(for:))
        if let currentLocation { coordinates.append(currentLocation.coordinate) }
        guard let first = coordinates.first else {
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 1.3521, longitude: 103.8198),
                latitudinalMeters: 1_000,
                longitudinalMeters: 1_000
            )
        }
        let latitudes = coordinates.map(\.latitude)
        let longitudes = coordinates.map(\.longitude)
        let latitudeDelta = max((latitudes.max() ?? first.latitude) - (latitudes.min() ?? first.latitude), 0.008)
        let longitudeDelta = max((longitudes.max() ?? first.longitude) - (longitudes.min() ?? first.longitude), 0.008)
        // 对真实范围增加留白，单点至少展示约 900 米区域，避免首屏缩放过近。
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(
                latitude: ((latitudes.max() ?? first.latitude) + (latitudes.min() ?? first.latitude)) / 2,
                longitude: ((longitudes.max() ?? first.longitude) + (longitudes.min() ?? first.longitude)) / 2
            ),
            span: MKCoordinateSpan(latitudeDelta: latitudeDelta * 1.35, longitudeDelta: longitudeDelta * 1.35)
        )
    }
}

/// 保持地图画布干净的浮层入口；复杂操作改由 sheet 承接。
struct TravelMapControls: View {
    // 控制层只接收值和闭包，不直接持有 APIClient 或 Store，保持 UI 可复用、容易预览与测试。
    let trip: Trip
    let isTracking: Bool
    let isRefreshing: Bool
    let isPreparingCheckin: Bool
    let message: String
    let syncError: String?
    let locationError: String?
    // () -> Void 表示无参数、无返回值的回调；父视图将具体状态变更作为闭包传进来。
    let onShowTrackingControls: () -> Void
    let onRefresh: () -> Void
    let onLocate: () -> Void
    let onCheckIn: () -> Void

    var body: some View {
        // VStack + Spacer 将顶部信息和底部操作压到全屏地图的两端。
        VStack(spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(trip.title).font(.headline)
                    Text(isTracking ? "正在记录位置" : "尚未开始记录")
                        .font(.caption)
                        .foregroundStyle(isTracking ? .green : .secondary)
                }
                .mapOverlaySurface()

                Spacer()

                Button(action: onRefresh) {
                    // iOS 17 使用 ProgressView 表达刷新中，避免依赖 iOS 18 的旋转符号效果。
                    if isRefreshing {
                        ProgressView()
                    } else {
                        Image(systemName: "arrow.clockwise")
                    }
                }
                .mapOverlaySurface()
                .disabled(isRefreshing)
                .accessibilityLabel("刷新足迹数据")
            }

            Spacer()

            VStack(spacing: 8) {
                // 非空消息可能是短暂打卡成功反馈或保留的刷新错误，展示策略由父视图管理。
                if !message.isEmpty {
                    Text(message).mapStatusPill(tint: .secondary)
                }
                if let syncError {
                    Text("同步未完成：\(syncError)").mapStatusPill(tint: .red)
                }
                // 定位失败独立于网络同步失败，用户能直接判断下一步应检查权限还是网络。
                if let locationError {
                    Text(locationError).mapStatusPill(tint: .red)
                }
                HStack(spacing: 10) {
                    Button(action: onLocate) {
                        Image(systemName: "location.circle")
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel("回到当前位置")

                    Button(action: onShowTrackingControls) {
                        Label("记录", systemImage: isTracking ? "record.circle.fill" : "location.fill")
                    }
                    .buttonStyle(.borderedProminent)

                    Button(action: onCheckIn) {
                        if isPreparingCheckin {
                            ProgressView()
                        } else {
                            Label("打卡", systemImage: "mappin.and.ellipse")
                        }
                    }
                    .buttonStyle(.bordered)
                    // 仅在正在获取本次位置时避免重复请求；旧坐标过期不再让入口自动禁用。
                    .disabled(isPreparingCheckin)
                }
                .mapOverlaySurface()
            }
        }
    }
}

struct TrackingControlSheet: View {
    // @ObservedObject 表示 Store 由父视图所有；此 Sheet 只是观察其 @Published 更新。
    let trip: Trip
    @ObservedObject var tracking: LocationTrackingStore
    // userUuid 为 Optional，防御会话资料尚未恢复完成时用户点击控制入口。
    let userUuid: String?
    let session: SessionStore
    let onSync: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("位置记录").font(.title3.bold())
                Spacer()
                Button("完成") { dismiss() }
            }
            Text(tracking.isTracking ? "正在记录 \(trip.title) 的前台位置。" : permissionDescription)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button(tracking.isTracking ? "停止记录" : "开始记录") {
                // 分支条件：记录已开启时停止定位，否则为当前行程开始采样。
                if tracking.isTracking {
                    tracking.stopTracking()
                } else if let userUuid {
                    tracking.startTracking(tripUuid: trip.uuid, userUuid: userUuid, session: session)
                }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!tracking.isTracking && userUuid == nil)
            Button("同步待传记录", action: onSync)
                .buttonStyle(.bordered)
            if tracking.pendingCount > 0 {
                Text("本机待同步 \(tracking.pendingCount) 条位置记录")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(24)
    }

    private var permissionDescription: String {
        // switch 穷举 Core Location 的授权枚举；@unknown default 让未来系统新增 case 时仍能安全降级。
        switch tracking.authorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse:
            return "定位权限已开启。第一版仅在应用打开期间采样。"
        case .denied, .restricted:
            return "请在系统设置中允许 Vago 使用定位，才能记录足迹。"
        case .notDetermined:
            return "开始记录时会请求定位权限。"
        @unknown default:
            return "定位权限状态暂不可用。"
        }
    }
}

private extension View {
    // extension 为现有协议添加项目内私有样式 helper，避免多个浮层复制 padding/background 修饰符。
    func mapOverlaySurface() -> some View {
        padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }
}

private extension Text {
    // Text 专用 helper 保持状态胶囊的字号、边距、材质背景一致。
    func mapStatusPill(tint: Color) -> some View {
        font(.footnote)
            .foregroundStyle(tint)
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(.ultraThinMaterial, in: Capsule())
    }
}
