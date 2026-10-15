import Foundation

/// 跨 Tab 共享的行程摘要状态；它只缓存服务器已确认的业务事实，不取代 Travel Domain 的权限与状态校验。
@MainActor
final class TripContextStore: ObservableObject {
    // 已读取的用户行程列表，行程页与记录页共用，避免状态切换后两边暂时展示不同的当前行程。
    @Published private(set) var trips: [Trip] = []
    // 与行程状态分离的唯一前台足迹记录目标；多个 Trip 可同时处于进行中。
    @Published private(set) var recordingTrip: Trip?
    private var selectedRecordingTripUuid: String?
    private var userUuid: String?

    private static func tripsCacheKey(for userUuid: String) -> String {
        "vago.trip.cached-list.\(userUuid)"
    }

    private static func selectionKey(for userUuid: String) -> String {
        "vago.trip.recording-selection.\(userUuid)"
    }

    func replaceTrips(_ trips: [Trip], for userUuid: String) {
        // 分支条件：账号变化时先丢弃旧账号内存数据，防止 Tab 切换时短暂回显其他用户的行程。
        prepareAccount(userUuid)
        self.trips = trips
        if let data = try? JSONEncoder().encode(trips) {
            UserDefaults.standard.set(data, forKey: Self.tripsCacheKey(for: userUuid))
        }
        reconcileRecordingTrip()
    }

    func restoreCachedTrips(for userUuid: String) {
        prepareAccount(userUuid)
        reconcileRecordingTrip()
    }

    func upsert(_ trip: Trip, for userUuid: String) {
        // 分支条件：尚未完整读取列表时也可接收开始、结束或编辑接口的单项响应。
        prepareAccount(userUuid)
        if let index = trips.firstIndex(where: { $0.uuid == trip.uuid }) {
            trips[index] = trip
        } else {
            trips.insert(trip, at: 0)
        }
        reconcileRecordingTrip()
    }

    func selectRecordingTrip(_ trip: Trip, for userUuid: String) {
        guard self.userUuid == userUuid, trips.contains(where: { $0.uuid == trip.uuid }) else { return }
        selectedRecordingTripUuid = trip.uuid
        recordingTrip = trip
        UserDefaults.standard.set(trip.uuid, forKey: Self.selectionKey(for: userUuid))
    }

    private func reconcileRecordingTrip() {
        if let selectedRecordingTripUuid,
           let selected = trips.first(where: { $0.uuid == selectedRecordingTripUuid }) {
            recordingTrip = selected
            return
        }
        let inProgressTrips = trips.filter { $0.status == TripStatus.inProgress.rawValue }
        let inferredTrip = inProgressTrips.count == 1 ? inProgressTrips.first : nil
        selectedRecordingTripUuid = inferredTrip?.uuid
        recordingTrip = inferredTrip
        if let inferredTrip, let userUuid {
            UserDefaults.standard.set(inferredTrip.uuid, forKey: Self.selectionKey(for: userUuid))
        } else if let userUuid {
            UserDefaults.standard.removeObject(forKey: Self.selectionKey(for: userUuid))
        }
    }

    private func prepareAccount(_ userUuid: String) {
        guard self.userUuid != userUuid else { return }
        self.userUuid = userUuid
        if let data = UserDefaults.standard.data(forKey: Self.tripsCacheKey(for: userUuid)),
           let cachedTrips = try? JSONDecoder().decode([Trip].self, from: data) {
            trips = cachedTrips
        } else {
            trips = []
        }
        recordingTrip = nil
        selectedRecordingTripUuid = UserDefaults.standard.string(forKey: Self.selectionKey(for: userUuid))
    }

    func reset() {
        trips = []
        recordingTrip = nil
        selectedRecordingTripUuid = nil
        userUuid = nil
    }
}
