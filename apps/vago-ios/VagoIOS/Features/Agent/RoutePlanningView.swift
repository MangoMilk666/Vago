import MapKit
import SwiftUI

private struct RoutePlace: Identifiable {
    let item: MKMapItem
    let id = UUID()

    var title: String { item.name ?? "未命名地点" }
    var subtitle: String { item.placemark.title ?? "" }
}

/// 直接用地区和地点名称搜索，再核对返回地址，避免城市解析失败阻断所有地点查询。
enum MapKitPlaceSearch {
    static func search(city: String, query: String) async throws -> [MKMapItem] {
        let normalizedCity = city.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalizedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedCity.isEmpty else { throw SearchError.cityRequired }
        guard !normalizedQuery.isEmpty else { return [] }
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = "\(normalizedCity) \(normalizedQuery)"
        request.resultTypes = [.pointOfInterest, .address]
        let response = try await MKLocalSearch(request: request).start()
        return response.mapItems.filter { item in
            // 地名可能在多个国家重复；只展示地址确实包含指定地区的结果。
            let area = [item.placemark.locality, item.placemark.subAdministrativeArea,
                        item.placemark.administrativeArea, item.placemark.country,
                        item.placemark.title]
                .compactMap { $0 }
                .joined(separator: " ")
            return area.localizedStandardContains(normalizedCity)
        }
    }

    enum SearchError: LocalizedError {
        case cityRequired

        var errorDescription: String? {
            switch self {
            case .cityRequired: "请先填写城市或地区"
            }
        }
    }
}

private enum RouteMode: String, CaseIterable, Identifiable {
    case walking = "步行"
    case driving = "驾车"
    case transit = "公交"

    var id: String { rawValue }

    var transportType: MKDirectionsTransportType {
        switch self {
        case .walking: .walking
        case .driving: .automobile
        case .transit: .transit
        }
    }
}

/// 设备端查询地点和路线；结果仅供预览，不生成服务端认可的 routeChoiceId。
struct RoutePlanningView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.appTheme) private var theme
    @State private var city = ""
    @State private var originQuery = ""
    @State private var destinationQuery = ""
    @State private var origin: RoutePlace?
    @State private var destination: RoutePlace?
    @State private var originResults: [RoutePlace] = []
    @State private var destinationResults: [RoutePlace] = []
    @State private var mode: RouteMode = .walking
    @State private var routes: [MKRoute] = []
    @State private var selectedRouteIndex: Int?
    @State private var cameraPosition: MapCameraPosition = .automatic
    @State private var isLoading = false
    @State private var errorMessage = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var directionsTask: Task<Void, Never>?

    let onAskAgent: (String) -> Void

    private var selectedRoute: MKRoute? {
        guard let selectedRouteIndex, routes.indices.contains(selectedRouteIndex) else { return nil }
        return routes[selectedRouteIndex]
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    introduction
                    TextField("城市或地区，例如杭州、新加坡", text: $city)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("搜索地区")
                        .onChange(of: city) { _, _ in
                            searchTask?.cancel()
                            origin = nil
                            destination = nil
                            originResults = []
                            destinationResults = []
                            clearRoutes()
                        }
                    placeField(title: "起点", query: $originQuery, selection: origin, results: originResults, isOrigin: true)
                    placeField(title: "终点", query: $destinationQuery, selection: destination, results: destinationResults, isOrigin: false)
                    Picker("出行方式", selection: $mode) {
                        ForEach(RouteMode.allCases) { option in Text(option.rawValue).tag(option) }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: mode) { _, _ in clearRoutes() }
                    Button {
                        directionsTask?.cancel()
                        directionsTask = Task { await findRoutes() }
                    } label: {
                        HStack {
                            if isLoading { ProgressView().tint(.white) }
                            Text(isLoading ? "正在查询路线" : "查询路线")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(theme.accent)
                    .disabled(origin == nil || destination == nil || isLoading)

                    if !errorMessage.isEmpty {
                        Text(errorMessage).font(.footnote).foregroundStyle(.red)
                    }
                    if !routes.isEmpty { routeResults }
                }
                .padding()
            }
            .navigationTitle("地点与路线")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") { dismiss() }
                }
            }
            .onDisappear {
                searchTask?.cancel()
                directionsTask?.cancel()
            }
        }
        .presentationDetents([.large])
    }

    private var introduction: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("用地图核对下一段旅程", systemImage: "map.fill")
                .font(.headline)
            Text("在设备上使用 Apple 地图搜索和比较路线。选中后可带着路线信息继续问 Agent。")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text("设备端查询 · 尚未经 Vago 服务端核验")
                .font(.caption)
                .foregroundStyle(.orange)
        }
    }

    private func placeField(title: String, query: Binding<String>, selection: RoutePlace?, results: [RoutePlace], isOrigin: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold))
            HStack {
                TextField("搜索\(title)名称", text: Binding(
                    get: { query.wrappedValue },
                    set: { newValue in
                        searchTask?.cancel()
                        query.wrappedValue = newValue
                        // 仅在用户编辑输入框时清除旧坐标；选择搜索结果时保留新地点。
                        if isOrigin { origin = nil; originResults = [] }
                        else { destination = nil; destinationResults = [] }
                        clearRoutes()
                    }
                ))
                    .textFieldStyle(.roundedBorder)
                Button("搜索") {
                    searchTask?.cancel()
                    searchTask = Task { await searchPlaces(query: query.wrappedValue, isOrigin: isOrigin) }
                }
                .disabled(city.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || query.wrappedValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            if let selection {
                Label(selection.title, systemImage: "checkmark.circle.fill")
                    .font(.caption)
                    .foregroundStyle(theme.accent)
            }
            ForEach(results) { place in
                Button {
                    if isOrigin { origin = place; originQuery = place.title; originResults = [] }
                    else { destination = place; destinationQuery = place.title; destinationResults = [] }
                    clearRoutes()
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(place.title).font(.subheadline)
                        Text(place.subtitle).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(.plain)
                .padding(.vertical, 5)
            }
        }
    }

    private var routeResults: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("路线候选 · \(routes.count) 条").font(.headline)
            ForEach(routes.indices, id: \.self) { index in
                let route = routes[index]
                Button {
                    selectedRouteIndex = index
                    // 使用真实道路折线的范围取景，地图上可继续缩放和拖动。
                    let rect = route.polyline.boundingMapRect
                    cameraPosition = .rect(rect.insetBy(dx: -rect.width * 0.15, dy: -rect.height * 0.15))
                } label: {
                    HStack {
                        Text("路线 \(index + 1)")
                        Spacer()
                        Text("\(Int(route.expectedTravelTime / 60)) 分钟 · \(route.distance.formatted(.number.precision(.fractionLength(0)))) 米")
                    }
                    .font(.subheadline)
                    .padding(12)
                    .background(selectedRouteIndex == index ? theme.accent.opacity(0.12) : Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
            }
            if let selectedRoute, let origin, let destination {
                Map(position: $cameraPosition) {
                    MapPolyline(selectedRoute.polyline)
                        .stroke(theme.accent, lineWidth: 5)
                    Annotation(origin.title, coordinate: origin.item.placemark.coordinate) {
                        Image(systemName: "a.circle.fill").foregroundStyle(theme.accent).font(.title2)
                    }
                    Annotation(destination.title, coordinate: destination.item.placemark.coordinate) {
                        Image(systemName: "b.circle.fill").foregroundStyle(theme.accent).font(.title2)
                    }
                }
                .mapControls { MapCompass(); MapScaleView() }
                .frame(height: 340)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                Text("Apple 地图 · 设备端路线预览，尚未经服务端核验")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button("带着这条路线问 Agent") {
                    let summary = "请结合这条设备端 Apple 地图路线给我建议：\(origin.title)到\(destination.title)，\(mode.rawValue)，预计\(Int(selectedRoute.expectedTravelTime / 60))分钟，约\(Int(selectedRoute.distance))米。这条路线尚未经 Vago 服务端核验。"
                    onAskAgent(summary)
                }
                .buttonStyle(.borderedProminent)
                .tint(theme.accent)
            }
        }
    }

    private func clearRoutes() {
        directionsTask?.cancel()
        routes = []
        selectedRouteIndex = nil
        errorMessage = ""
    }

    private func searchPlaces(query: String, isOrigin: Bool) async {
        do {
            let items = try await MapKitPlaceSearch.search(city: city, query: query)
            guard !Task.isCancelled else { return }
            let places = items.prefix(8).map(RoutePlace.init)
            if isOrigin { originResults = places } else { destinationResults = places }
            errorMessage = places.isEmpty ? "没有找到对应地点，请尝试更具体的名称" : ""
        } catch {
            guard !Task.isCancelled else { return }
            errorMessage = "地点查询失败：\(error.localizedDescription)"
        }
    }

    private func findRoutes() async {
        guard let origin, let destination else { return }
        isLoading = true
        errorMessage = ""
        defer { isLoading = false }
        let request = MKDirections.Request()
        request.source = origin.item
        request.destination = destination.item
        request.transportType = mode.transportType
        request.requestsAlternateRoutes = true
        do {
            let response = try await MKDirections(request: request).calculate()
            guard !Task.isCancelled else { return }
            routes = response.routes
            selectedRouteIndex = nil
            if routes.isEmpty { errorMessage = "当前地区与出行方式没有可用路线" }
        } catch {
            guard !Task.isCancelled else { return }
            errorMessage = "路线查询失败：\(error.localizedDescription)"
        }
    }
}
