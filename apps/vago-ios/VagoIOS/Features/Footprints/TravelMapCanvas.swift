import CoreLocation
import MapKit
import SwiftUI

/// 地图画布只负责渲染个人空间数据；定位和网络请求仍由上层现有能力处理。
struct TravelMapCanvas: View {
    // 三类输入分别来自服务端轨迹、服务端打卡与尚未同步的最新本地采样。
    let locations: [FootprintLocation]
    let checkins: [Checkin]
    let latestSample: PendingLocationSample?

    var body: some View {
        // Map 的闭包是 MapContentBuilder，内部声明的 Marker、Annotation、Polyline 会成为地图叠加物。
        Map(initialPosition: .region(initialRegion)) {
            // 分支条件：至少两个轨迹点才绘制连线，单点仅作为位置标记展示。
            if locations.count > 1 {
                MapPolyline(coordinates: locations.map(coordinate(for:)))
                    .stroke(.indigo, lineWidth: 4)
            }
            // 已同步点绘制为普通标记；大量轨迹点时后续可按产品需要改为抽稀或仅显示 polyline。
            ForEach(locations) { location in
                Marker("轨迹", coordinate: coordinate(for: location))
                    .tint(.indigo)
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
            // 分支条件：本地最新样本尚未同步时仍立即显示，满足“本地 pending + 服务端数据合并”的体验。
            if let latestSample {
                Marker("当前位置", coordinate: CLLocationCoordinate2D(latitude: latestSample.latitude, longitude: latestSample.longitude))
                    .tint(.red)
            }
        }
        .mapStyle(.standard(elevation: .realistic))
        .mapControls {
            MapCompass()
            MapScaleView()
        }
    }

    private func coordinate(for location: FootprintLocation) -> CLLocationCoordinate2D {
        // MapKit 使用 CLLocationCoordinate2D；领域模型保留 Double 便于 JSON 解码与服务端契约对齐。
        CLLocationCoordinate2D(latitude: location.latitude, longitude: location.longitude)
    }

    private func coordinate(for checkin: Checkin) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: checkin.latitude, longitude: checkin.longitude)
    }

    private var initialRegion: MKCoordinateRegion {
        // 计算属性随输入数据变化重新推导首屏区域，不需要另存一份易过期的 camera state。
        let center: CLLocationCoordinate2D
        // 分支条件：优先以最新本地样本居中；没有时使用已同步轨迹或打卡，最后才显示默认位置。
        if let latestSample {
            center = CLLocationCoordinate2D(latitude: latestSample.latitude, longitude: latestSample.longitude)
        } else if let location = locations.last {
            center = coordinate(for: location)
        } else if let checkin = checkins.last {
            center = coordinate(for: checkin)
        } else {
            center = CLLocationCoordinate2D(latitude: 1.3521, longitude: 103.8198)
        }
        // 米为单位的跨度比经纬度 delta 更直观，也能在不同纬度保持大致一致的可见范围。
        return MKCoordinateRegion(center: center, latitudinalMeters: 1_000, longitudinalMeters: 1_000)
    }
}

/// 保持地图画布干净的浮层入口；复杂操作改由 sheet 承接。
struct TravelMapControls: View {
    // 控制层只接收值和闭包，不直接持有 APIClient 或 Store，保持 UI 可复用、容易预览与测试。
    let trip: Trip
    let isTracking: Bool
    let isRefreshing: Bool
    let hasLocationSample: Bool
    let message: String
    let syncError: String?
    // () -> Void 表示无参数、无返回值的回调；父视图将具体状态变更作为闭包传进来。
    let onShowTrackingControls: () -> Void
    let onRefresh: () -> Void
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
                HStack(spacing: 10) {
                    Button(action: onShowTrackingControls) {
                        Label("记录", systemImage: isTracking ? "record.circle.fill" : "location.fill")
                    }
                    .buttonStyle(.borderedProminent)

                    Button(action: onCheckIn) {
                        Label("打卡", systemImage: "mappin.and.ellipse")
                    }
                    .buttonStyle(.bordered)
                    .disabled(!hasLocationSample)
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
