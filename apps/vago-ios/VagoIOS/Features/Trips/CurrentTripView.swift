import SwiftUI

struct CurrentTripView: View {
    // 当前行程 Tab 只关心 status=2 的正式行程，不承担计划草稿列表职责。
    @EnvironmentObject private var session: SessionStore
    // Optional Trip 让页面能区分“尚未加载”“没有进行中行程”和“已取得行程”。
    @State private var trip: Trip?
    @State private var isLoading = true
    @State private var errorMessage = ""
    @State private var loadedUserUuid: String?
    // View 保持轻量：数据请求委托给 APIClient，页面只负责展示状态。
    private let client = APIClient()

    var body: some View {
        // Group 只组织条件内容，本身不会产生额外布局容器。
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView("正在读取当前行程")
                } else if let trip {
                    TripDetailView(trip: trip)
                } else {
                    ContentUnavailableView("暂无进行中的行程", systemImage: "suitcase", description: Text("开始一个正式行程后，它会在这里出现。"))
                }
            }
            .navigationTitle("行程")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { Task { await refresh() } } label: { Image(systemName: "arrow.clockwise") } } }
            // 用户切换后才重新初始读取；同一用户因视图重算再次出现时不重复请求。
            // task(id:) 仅在 id 改变时重新执行；它是避免 Tab 重绘造成重复请求的关键。
            .task(id: session.profile?.uuid) { await loadInitially() }
            .alert("暂时无法读取行程", isPresented: Binding(get: { !errorMessage.isEmpty }, set: { if !$0 { errorMessage = "" } })) { Button("好的", role: .cancel) {} } message: { Text(errorMessage) }
        }
    }

    private func load() async {
        // do/catch 与 Python try/except 对应，把网络错误转换为页面可展示状态。
        isLoading = true
        defer { isLoading = false }
        do {
            let trips: [Trip] = try await client.request(path: "travel/trips", tokenProvider: session)
            // 后端约定 status=2 表示进行中，iOS 首页仅展示当前这一份正式行程。
            trip = trips.first(where: { $0.status == 2 })
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func loadInitially() async {
        // guard 同时校验用户存在与尚未读取该用户；条件不满足就立即 return。
        guard let userUuid = session.profile?.uuid, loadedUserUuid != userUuid else { return }
        // 请求开始前即记录用户，避免 SwiftUI 重建期间并发发起相同初始请求。
        loadedUserUuid = userUuid
        await load()
    }

    private func refresh() async {
        await load()
    }
}

private struct TripDetailView: View {
    // private 表示此详情视图只被当前文件使用，避免把内部页面误当作跨模块 API。
    @EnvironmentObject private var session: SessionStore
    let trip: Trip
    @State private var days: [ItineraryDay] = []
    @State private var isLoading = true
    @State private var loadedTripUuid: String?
    @State private var errorMessage = ""
    private let client = APIClient()

    var body: some View {
        List {
            Section {
                Text(trip.destination ?? "未设置目的地").font(.headline)
                Text("\(trip.startDate.formatted(date: .abbreviated, time: .omitted)) - \(trip.endDate.formatted(date: .abbreviated, time: .omitted))").foregroundStyle(.secondary)
            } header: { Text(trip.title) }
            Section("每日安排") {
                if isLoading { ProgressView() }
                // 分支条件：接口异常时展示真实错误，不能把失败悄悄降级为“没有日程”。
                if !errorMessage.isEmpty {
                    ContentUnavailableView("暂时无法读取日程", systemImage: "exclamationmark.icloud", description: Text(errorMessage))
                } else {
                    // ForEach 依赖 ItineraryDay 的 Identifiable.id 来做增量更新和导航复用。
                    ForEach(days) { day in
                        NavigationLink { ItineraryDayView(day: day) } label: {
                            VStack(alignment: .leading) {
                                Text("第 \(day.dayIndex) 天 · \(day.dayDate.formatted(date: .abbreviated, time: .omitted))")
                                Text(day.spots.map(\.name).joined(separator: " · ").isEmpty ? "暂未安排地点" : day.spots.map(\.name).joined(separator: " · "))
                                    .font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(trip.title)
        // 行程 UUID 改变时才读取新的日程，防止 Tab 切换或列表重绘重复请求。
        .task(id: trip.uuid) { await loadDaysInitially() }
    }

    private func loadDays() async {
        // defer 类似 finally，无论请求结果如何都结束 loading 状态。
        isLoading = true
        errorMessage = ""
        defer { isLoading = false }
        do {
            days = try await client.request(path: "travel/trips/\(trip.uuid)/days", tokenProvider: session)
        } catch {
            // 日程读取失败不能伪装成空日程，否则会掩盖服务端限流等真实故障。
            errorMessage = error.localizedDescription
        }
    }

    private func loadDaysInitially() async {
        guard loadedTripUuid != trip.uuid else { return }
        // 请求开始前记录 UUID，保证同一行程只有一个初始读取任务。
        loadedTripUuid = trip.uuid
        await loadDays()
    }
}

private struct ItineraryDayView: View {
    // let 表示输入日程不可在详情页直接修改，符合已结束行程等只读展示场景。
    let day: ItineraryDay
    var body: some View {
        List {
            if let transportation = day.transportation { Section("交通") { Text(transportation) } }
            if let accommodation = day.accommodation { Section("住宿") { Text(accommodation) } }
            Section("地点") {
                ForEach(day.spots) { spot in
                    VStack(alignment: .leading) { Text(spot.name); if let address = spot.address { Text(address).font(.subheadline).foregroundStyle(.secondary) } }
                }
            }
            if let notes = day.notes, !notes.isEmpty { Section("备注") { Text(notes) } }
        }
        .navigationTitle("第 \(day.dayIndex) 天")
    }
}
