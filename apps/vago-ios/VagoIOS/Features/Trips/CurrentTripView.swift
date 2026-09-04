import SwiftUI

struct CurrentTripView: View {
    @EnvironmentObject private var session: SessionStore
    @State private var trip: Trip?
    @State private var isLoading = true
    @State private var errorMessage = ""
    // View 保持轻量：数据请求委托给 APIClient，页面只负责展示状态。
    private let client = APIClient()

    var body: some View {
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
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { Task { await load() } } label: { Image(systemName: "arrow.clockwise") } } }
            // 页面首次出现时加载；比 onAppear 更适合调用可取消的 async 任务。
            .task { await load() }
            .alert("暂时无法读取行程", isPresented: Binding(get: { !errorMessage.isEmpty }, set: { if !$0 { errorMessage = "" } })) { Button("好的", role: .cancel) {} } message: { Text(errorMessage) }
        }
    }

    private func load() async {
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
}

private struct TripDetailView: View {
    @EnvironmentObject private var session: SessionStore
    let trip: Trip
    @State private var days: [ItineraryDay] = []
    @State private var isLoading = true
    private let client = APIClient()

    var body: some View {
        List {
            Section {
                Text(trip.destination ?? "未设置目的地").font(.headline)
                Text("\(trip.startDate.formatted(date: .abbreviated, time: .omitted)) - \(trip.endDate.formatted(date: .abbreviated, time: .omitted))").foregroundStyle(.secondary)
            } header: { Text(trip.title) }
            Section("每日安排") {
                if isLoading { ProgressView() }
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
        .navigationTitle(trip.title)
        .task { await loadDays() }
    }

    private func loadDays() async {
        defer { isLoading = false }
        // try? 将读取失败降级为空数组，避免一个日程接口错误导致行程详情无法打开。
        days = (try? await client.request(path: "travel/trips/\(trip.uuid)/days", tokenProvider: session)) ?? []
    }
}

private struct ItineraryDayView: View {
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
