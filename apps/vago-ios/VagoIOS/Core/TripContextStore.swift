import Foundation

/// 跨 Tab 共享的行程摘要状态；它只缓存服务器已确认的业务事实，不取代 Travel Domain 的权限与状态校验。
@MainActor
final class TripContextStore: ObservableObject {
    // 已读取的用户行程列表，行程页与记录页共用，避免状态切换后两边暂时展示不同的当前行程。
    @Published private(set) var trips: [Trip] = []
    // 服务端 status=2 的唯一进行中行程，也是定位记录和手动打卡的唯一写入目标。
    @Published private(set) var activeTrip: Trip?
    private var userUuid: String?

    func replaceTrips(_ trips: [Trip], for userUuid: String) {
        // 分支条件：账号变化时先丢弃旧账号内存数据，防止 Tab 切换时短暂回显其他用户的行程。
        if self.userUuid != userUuid {
            self.userUuid = userUuid
            self.trips = []
            activeTrip = nil
        }
        self.trips = trips
        activeTrip = trips.first(where: { $0.status == TripStatus.inProgress.rawValue })
    }

    func upsert(_ trip: Trip, for userUuid: String) {
        // 分支条件：尚未完整读取列表时也可接收开始、结束或编辑接口的单项响应。
        if self.userUuid != userUuid {
            self.userUuid = userUuid
            trips = []
        }
        if let index = trips.firstIndex(where: { $0.uuid == trip.uuid }) {
            trips[index] = trip
        } else {
            trips.insert(trip, at: 0)
        }
        activeTrip = trips.first(where: { $0.status == TripStatus.inProgress.rawValue })
    }

    func replaceAfterSwitch(previousTripUuid: String?, newActiveTrip: Trip, for userUuid: String) {
        // 切换接口只回传新行程；将旧摘要本地标为已结束，随后刷新列表可得到其服务端完整版本。
        if let previousTripUuid, let index = trips.firstIndex(where: { $0.uuid == previousTripUuid }) {
            trips[index] = trips[index].withStatus(TripStatus.ended.rawValue)
        }
        upsert(newActiveTrip, for: userUuid)
        activeTrip = newActiveTrip
    }

    func reset() {
        trips = []
        activeTrip = nil
        userUuid = nil
    }
}
