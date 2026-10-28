import MapKit
import SwiftUI

private struct RoutePlace: Identifiable {
    let item: MKMapItem
    let id = UUID()

    var title: String { item.name ?? "未命名地点" }
    var subtitle: String { item.placemark.title ?? "" }
}

private enum RoutePlaceField: Hashable {
    case origin, destination
}

/// 先定位城市，再在城市附近搜索地点；地址显示语言不参与地点归属判断。
enum MapKitPlaceSearch {
    static func search(city: String, query: String) async throws -> [MKMapItem] {
        let normalizedCity = city.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalizedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedCity.isEmpty else { throw SearchError.cityRequired }
        guard !normalizedQuery.isEmpty else { return [] }

        let cityRequest = MKLocalSearch.Request()
        cityRequest.naturalLanguageQuery = normalizedCity
        cityRequest.resultTypes = [.address]
        let cityResponse = try await MKLocalSearch(request: cityRequest).start()
        // 地区查询只取中国大陆且名称确实对应输入城市的结果，避免同名地点落在别的国家。
        guard let cityItem = cityResponse.mapItems.first(where: { item in
            item.placemark.isoCountryCode == "CN" &&
                ([item.name, item.placemark.locality, item.placemark.administrativeArea]
                    .compactMap { $0 }
                    .contains { $0.localizedStandardContains(normalizedCity) || normalizedCity.localizedStandardContains($0) })
        }) else {
            throw SearchError.cityNotFound
        }

        let cityLocation = cityItem.placemark.location ?? CLLocation(
            latitude: cityItem.placemark.coordinate.latitude,
            longitude: cityItem.placemark.coordinate.longitude
        )
        let request = MKLocalSearch.Request()
        // 地点名称独立查询，城市用地图范围约束，避免“杭州市 浙江大学”被当作一个地址解析。
        request.naturalLanguageQuery = normalizedQuery
        request.region = MKCoordinateRegion(
            center: cityItem.placemark.coordinate,
            span: MKCoordinateSpan(latitudeDelta: 1.2, longitudeDelta: 1.2)
        )
        request.resultTypes = [.pointOfInterest, .address]
        let response = try await MKLocalSearch(request: request).start()
        return response.mapItems.filter { item in
            // MapKit 的 region 只是搜索提示，按实际坐标排除远离城市的同名地点。
            let location = item.placemark.location ?? CLLocation(
                latitude: item.placemark.coordinate.latitude,
                longitude: item.placemark.coordinate.longitude
            )
            return item.placemark.isoCountryCode == "CN" && cityLocation.distance(from: location) <= 80_000
        }
    }

    enum SearchError: LocalizedError {
        case cityRequired, cityNotFound

        var errorDescription: String? {
            switch self {
            case .cityRequired: "请先填写城市或地区"
            case .cityNotFound: "无法定位中国大陆城市，请输入完整城市名称（例如杭州市）"
            }
        }
    }
}

private enum RouteMode: String, CaseIterable, Identifiable {
    case walking = "步行"
    case driving = "驾车"
    case transit = "公交"

    var id: String { rawValue }

    var apiValue: String {
        switch self {
        case .walking: "walking"
        case .driving: "driving"
        case .transit: "transit"
        }
    }

    var transportType: MKDirectionsTransportType {
        switch self {
        case .walking: .walking
        case .driving: .automobile
        case .transit: .transit
        }
    }
}

private struct PlanningPlaceSearch: Encodable {
    let countryCode = "CN"
    let city: String
    let query: String
}

private struct PlanningServerPlace: Decodable {
    let id: String
    let name: String
    let latitude: Double
    let longitude: Double
    let cityCode: String?
}

private struct PlanningRouteSearch: Encodable {
    let countryCode = "CN"
    let city: String
    let cityCode: String?
    let mode: String
    let fromItemId: String
    let toItemId: String
    let originLatitude: Double
    let originLongitude: Double
    let destinationLatitude: Double
    let destinationLongitude: Double
    let coordinateSystem = "GCJ-02"
}

private struct PlanningServerRoute: Decodable {
    let routeChoiceId: String
    let provider: String
    let mode: String
    let routeDurationMinutes: Int
    let queriedAt: String
}

struct PlanningProposalCreateRequest: Encodable {
    struct Brief: Encodable {
        let startDate: String
        let endDate: String
        let timezone = "Asia/Shanghai"
        let hardConstraints: [String] = []
    }

    struct Item: Encodable {
        let id: String
        let name: String
        let kind = "custom"
        let city: String
        let latitude: Double
        let longitude: Double
        let coordinateSystem = "GCJ-02"
        let startTime: String
        let endTime: String
        let provider = "amap"
    }

    struct Leg: Encodable {
        let fromItemId: String
        let toItemId: String
        let routeDurationMinutes: Int
        let bufferMinutes = 0
        let provider: String
        let mode: String
        let queriedAt: String
        let routeChoiceId: String
    }

    struct Day: Encodable {
        let day = 1
        let date: String
        let city: String
        let timezone = "Asia/Shanghai"
        let items: [Item]
        let legs: [Leg]
    }

    struct Content: Encodable {
        let days: [Day]
    }

    let idempotencyKey: String
    let targetKind = "new_plan"
    let brief: Brief
    let content: Content
}

struct PlanningProposalSummary: Decodable, Identifiable {
    let uuid: String
    let version: Int
    let status: String

    var id: String { uuid }
}

struct PlanningProposalDetail: Decodable {
    struct Validation: Decodable {
        struct Check: Decodable {
            let status: String
            let message: String
        }
        let checks: [Check]
    }

    let conversationUuid: String
    let version: Int
    let status: String
    let validation: Validation?
}

enum MapKitRouteCheck {
    // 判断设备是否取得了能展示的路线；服务端来源核验仍由 FastAPI 单独完成。
    static func isDisplayable(_ route: MKRoute) -> Bool {
        route.polyline.pointCount > 1 && route.distance > 0 && route.expectedTravelTime > 0
    }
}

/// 设备端用 MapKit 预览；保存候选时另由服务端查询同一组地点并签发高德路线引用。
struct RoutePlanningView: View {
    @EnvironmentObject private var session: SessionStore
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
    @State private var travelDate = Date()
    @State private var originStart = Calendar.current.date(from: DateComponents(hour: 9)) ?? Date()
    @State private var originEnd = Calendar.current.date(from: DateComponents(hour: 9, minute: 30)) ?? Date()
    @State private var destinationStart = Calendar.current.date(from: DateComponents(hour: 12)) ?? Date()
    @State private var destinationEnd = Calendar.current.date(from: DateComponents(hour: 13)) ?? Date()
    @State private var isSaving = false
    @State private var savedProposal: PlanningProposalDetail?
    @State private var proposalVersions: [PlanningProposalSummary] = []
    @State private var pendingProposal: PlanningProposalCreateRequest?
    @State private var savedRouteSummary: String?
    @FocusState private var focusedPlaceField: RoutePlaceField?
    private let client = APIClient()

    let conversationUuid: String?
    let onSaveProposal: (PlanningProposalCreateRequest) async throws -> PlanningProposalDetail
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
                    TextField("中国大陆城市，例如杭州、上海", text: $city)
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
                    if !proposalVersions.isEmpty { proposalList }
                    if let savedProposal { proposalDetail(savedProposal) }
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
            .task(id: conversationUuid) { await loadProposals() }
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
            Text("MapKit 路线供预览；保存候选时由服务端重新查询并核验高德路线")
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
                        // 如果输入框同步回已选地点的标题，仍保持选中状态；用户改写文字才清除旧地点。
                        if newValue == selection?.title { return }
                        searchTask?.cancel()
                        query.wrappedValue = newValue
                        if isOrigin { origin = nil; originResults = [] }
                        else { destination = nil; destinationResults = [] }
                        clearRoutes()
                    }
                ))
                    .textFieldStyle(.roundedBorder)
                    .focused($focusedPlaceField, equals: isOrigin ? .origin : .destination)
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
                    searchTask?.cancel()
                    focusedPlaceField = nil
                    clearRoutes()
                    // 用户点击结果即确认地点；标题回填后仍保留对应的 MKMapItem 坐标。
                    if isOrigin { originQuery = place.title; origin = place; originResults = [] }
                    else { destinationQuery = place.title; destination = place; destinationResults = [] }
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
                    pendingProposal = nil
                    savedProposal = nil
                    savedRouteSummary = nil
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
                Text("Apple 地图预览 · 保存时以服务端重新查询的路线为准")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                proposalForm(origin: origin, destination: destination)
                Button("带着这条路线问 Agent") {
                    let summary = "请结合这条设备端 Apple 地图路线给我建议：\(origin.title)到\(destination.title)，\(mode.rawValue)，预计\(Int(selectedRoute.expectedTravelTime / 60))分钟，约\(Int(selectedRoute.distance))米。这条路线尚未经 Vago 服务端核验。"
                    onAskAgent(summary)
                }
                .buttonStyle(.borderedProminent)
                .tint(theme.accent)
            }
        }
    }

    private var proposalList: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("当前会话的候选版本").font(.headline)
            ForEach(proposalVersions) { proposal in
                Button("版本 \(proposal.version) · \(proposal.status == "VALIDATED" ? "检查通过" : "需补充或调整")") {
                    Task { await loadProposal(version: proposal.version) }
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private func proposalForm(origin: RoutePlace, destination: RoutePlace) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("保存为当前会话候选").font(.headline)
            Text("服务端会重新查询这两个地点的高德路线，并将核验结果写入候选；地图上预览的仍是 Apple 路线。")
                .font(.caption).foregroundStyle(.secondary)
            DatePicker("旅行日期", selection: $travelDate, displayedComponents: .date)
            DatePicker("起点开始", selection: $originStart, displayedComponents: .hourAndMinute)
            DatePicker("起点结束", selection: $originEnd, displayedComponents: .hourAndMinute)
            DatePicker("终点开始", selection: $destinationStart, displayedComponents: .hourAndMinute)
            DatePicker("终点结束", selection: $destinationEnd, displayedComponents: .hourAndMinute)
            Text("以上时间按目的地当地时间填写（中国大陆为北京时间）")
                .font(.caption).foregroundStyle(.secondary)
            Button {
                Task { await saveProposal(origin: origin, destination: destination) }
            } label: {
                if isSaving { ProgressView() } else { Text("核验并保存候选") }
            }
            .buttonStyle(.borderedProminent)
            .tint(theme.accent)
            .disabled(isSaving)
            if let savedRouteSummary {
                Label(savedRouteSummary, systemImage: "checkmark.circle.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.green)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color.green.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
                    .accessibilityAddTraits(.updatesFrequently)
            }
        }
        .onChange(of: travelDate) { _, _ in invalidatePendingProposal() }
        .onChange(of: originStart) { _, _ in invalidatePendingProposal() }
        .onChange(of: originEnd) { _, _ in invalidatePendingProposal() }
        .onChange(of: destinationStart) { _, _ in invalidatePendingProposal() }
        .onChange(of: destinationEnd) { _, _ in invalidatePendingProposal() }
    }

    private func proposalDetail(_ proposal: PlanningProposalDetail) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("候选版本 \(proposal.version) · \(proposal.status == "VALIDATED" ? "检查通过" : "需补充或调整")")
                .font(.subheadline.weight(.semibold))
            ForEach(Array((proposal.validation?.checks ?? []).enumerated()), id: \.offset) { _, check in
                Text("\(check.status == "pass" ? "✓" : "·") \(check.message)")
                    .font(.caption)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(theme.accent.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
    }

    private func invalidatePendingProposal() {
        pendingProposal = nil
        savedProposal = nil
        savedRouteSummary = nil
    }

    private func clock(_ date: Date) -> String {
        let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
        return String(format: "%02d:%02d", parts.hour ?? 0, parts.minute ?? 0)
    }

    private func minutes(_ value: Date) -> Int {
        let parts = Calendar.current.dateComponents([.hour, .minute], from: value)
        return (parts.hour ?? 0) * 60 + (parts.minute ?? 0)
    }

    private func travelDay() -> String {
        let parts = Calendar.current.dateComponents([.year, .month, .day], from: travelDate)
        return String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
    }

    private func nearestServerPlace(to item: MKMapItem) async throws -> PlanningServerPlace {
        let places: [PlanningServerPlace] = try await client.request(
            path: "agent/planning/places/search", method: "POST",
            body: PlanningPlaceSearch(city: city, query: item.name ?? ""), tokenProvider: session
        )
        let deviceLocation = CLLocation(latitude: item.placemark.coordinate.latitude,
                                        longitude: item.placemark.coordinate.longitude)
        let nearest = places.min { left, right in
            let leftDistance = deviceLocation.distance(from: CLLocation(latitude: left.latitude, longitude: left.longitude))
            let rightDistance = deviceLocation.distance(from: CLLocation(latitude: right.latitude, longitude: right.longitude))
            return leftDistance < rightDistance
        }
        // 大陆 Apple 与高德使用不同坐标系；允许坐标偏移，但拒绝匹配到远处的同名地点。
        guard let nearest, let deviceName = item.name,
              (nearest.name.localizedStandardContains(deviceName) || deviceName.localizedStandardContains(nearest.name)),
              deviceLocation.distance(from: CLLocation(latitude: nearest.latitude, longitude: nearest.longitude)) <= 1_200 else {
            throw PlanningSaveError.placeMismatch
        }
        return nearest
    }

    private func buildProposal(origin: RoutePlace, destination: RoutePlace) async throws -> PlanningProposalCreateRequest {
        let firstStart = clock(originStart)
        let firstEnd = clock(originEnd)
        let lastStart = clock(destinationStart)
        let lastEnd = clock(destinationEnd)
        guard minutes(originStart) < minutes(originEnd), minutes(destinationStart) < minutes(destinationEnd) else {
            throw PlanningSaveError.invalidTimes
        }
        let serverOrigin = try await nearestServerPlace(to: origin.item)
        let serverDestination = try await nearestServerPlace(to: destination.item)
        let routes: [PlanningServerRoute] = try await client.request(
            path: "agent/planning/routes/search", method: "POST",
            body: PlanningRouteSearch(
                city: city, cityCode: serverOrigin.cityCode, mode: mode.apiValue,
                fromItemId: serverOrigin.id, toItemId: serverDestination.id,
                originLatitude: serverOrigin.latitude, originLongitude: serverOrigin.longitude,
                destinationLatitude: serverDestination.latitude, destinationLongitude: serverDestination.longitude
            ), tokenProvider: session
        )
        guard let serverRoute = routes.first else { throw PlanningSaveError.noRoute }
        guard serverOrigin.id != serverDestination.id,
              minutes(originEnd) + serverRoute.routeDurationMinutes <= minutes(destinationStart) else {
            throw PlanningSaveError.invalidTimes
        }
        let date = travelDay()
        let items = [
            PlanningProposalCreateRequest.Item(id: serverOrigin.id, name: serverOrigin.name, city: city,
                                               latitude: serverOrigin.latitude, longitude: serverOrigin.longitude,
                                               startTime: firstStart, endTime: firstEnd),
            PlanningProposalCreateRequest.Item(id: serverDestination.id, name: serverDestination.name, city: city,
                                               latitude: serverDestination.latitude, longitude: serverDestination.longitude,
                                               startTime: lastStart, endTime: lastEnd),
        ]
        let leg = PlanningProposalCreateRequest.Leg(
            fromItemId: serverOrigin.id, toItemId: serverDestination.id,
            routeDurationMinutes: serverRoute.routeDurationMinutes, provider: serverRoute.provider,
            mode: serverRoute.mode, queriedAt: serverRoute.queriedAt, routeChoiceId: serverRoute.routeChoiceId
        )
        return PlanningProposalCreateRequest(
            idempotencyKey: UUID().uuidString, brief: .init(startDate: date, endDate: date),
            content: .init(days: [.init(date: date, city: city, items: items, legs: [leg])])
        )
    }

    private func saveProposal(origin: RoutePlace, destination: RoutePlace) async {
        isSaving = true
        errorMessage = ""
        defer { isSaving = false }
        do {
            // 保存请求失败时保留同一份内容和幂等键；再次点击不会生成重复版本。
            if pendingProposal == nil { pendingProposal = try await buildProposal(origin: origin, destination: destination) }
            guard let pendingProposal else { return }
            let result = try await onSaveProposal(pendingProposal)
            savedProposal = result
            if let day = pendingProposal.content.days.first, day.items.count == 2, let leg = day.legs.first {
                savedRouteSummary = "已保存到当前会话 · 版本 \(result.version)\n\(day.items[0].name) → \(day.items[1].name) · 高德路线约 \(leg.routeDurationMinutes) 分钟"
            }
            await loadProposals(conversationUUID: result.conversationUuid)
        } catch {
            errorMessage = "保存候选失败：\(error.localizedDescription)"
        }
    }

    private func loadProposals() async {
        guard let conversationUuid else { proposalVersions = []; return }
        await loadProposals(conversationUUID: conversationUuid)
    }

    private func loadProposals(conversationUUID: String) async {
        do {
            let loaded: [PlanningProposalSummary] = try await client.request(
                path: "agent/conversations/\(conversationUUID)/proposals", tokenProvider: session
            )
            proposalVersions = loaded
        } catch {
            errorMessage = "读取候选版本失败：\(error.localizedDescription)"
        }
    }

    private func loadProposal(version: Int) async {
        guard let conversationUUID = savedProposal?.conversationUuid ?? conversationUuid else { return }
        do {
            let detail: PlanningProposalDetail = try await client.request(
                path: "agent/conversations/\(conversationUUID)/proposals/versions/\(version)", tokenProvider: session
            )
            savedProposal = detail
        } catch {
            errorMessage = "读取候选详情失败：\(error.localizedDescription)"
        }
    }

    private enum PlanningSaveError: LocalizedError {
        case placeMismatch, noRoute, invalidTimes

        var errorDescription: String? {
            switch self {
            case .placeMismatch: "服务端无法确认同一地点，请尝试使用更具体的中文地点名称"
            case .noRoute: "服务端没有查到对应的路线"
            case .invalidTimes: "请调整地点停留与交通时间，确保当天安排合理"
            }
        }
    }

    private func clearRoutes() {
        directionsTask?.cancel()
        routes = []
        selectedRouteIndex = nil
        errorMessage = ""
        pendingProposal = nil
        savedProposal = nil
        savedRouteSummary = nil
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
            routes = response.routes.filter(MapKitRouteCheck.isDisplayable)
            selectedRouteIndex = nil
            if routes.isEmpty { errorMessage = "当前地区与出行方式没有可用路线" }
        } catch {
            guard !Task.isCancelled else { return }
            errorMessage = "路线查询失败：\(error.localizedDescription)"
        }
    }
}
