import CoreLocation
import Foundation

/// 对齐 FastAPI `{ code, message, data }` 响应；`Value` 是泛型，调用处决定 data 的具体模型。
struct APIEnvelope<Value: Decodable>: Decodable {
    // 业务状态码，与 HTTP status code 配合使用。
    let code: Int
    // 后端返回的可展示消息，失败时用于 iOS 的错误提示。
    let message: String
    // 可选值表示部分成功响应可能不携带业务数据，例如注销接口。
    let data: Value?
}

/// Codable 同时包含 Encodable / Decodable，可在 JSON 与 Keychain 二进制数据之间转换。
struct TokenPair: Codable {
    // 短期访问令牌，用于携带在 Authorization 请求头中。
    let accessToken: String
    // 用于换取新 access token 的长期令牌，不能放入 UserDefaults。
    let refreshToken: String
    // 后端声明的 access token 有效秒数，当前客户端保留以兼容接口。
    let expiresIn: Int
    // 服务端会话标识，可能为空以兼容历史登录响应。
    let sessionId: String?
}

/// 登录接口返回的业务数据，字段名通过 Codable 自动映射同名 JSON camelCase 字段。
struct LoginResponse: Decodable {
    // 登录接口把 token 与用户资料一起返回，避免客户端额外请求一次 profile。
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    let sessionId: String?
    let userInfo: UserProfile

    var tokens: TokenPair {
        // 计算属性不占用额外存储；在保存 Keychain 前将接口模型转换为领域内的 TokenPair。
        TokenPair(accessToken: accessToken, refreshToken: refreshToken, expiresIn: expiresIn, sessionId: sessionId)
    }
}

/// Identifiable 提供稳定 id，SwiftUI 的 List / ForEach 用它识别列表元素。
struct UserProfile: Codable, Identifiable {
    // 与 FastAPI user_uuid 对应，也是 SwiftUI 列表的稳定主键来源。
    let uuid: String
    // 用户主动设置的展示名称。
    let nickname: String
    // 手机号、邮箱和头像都允许服务端为空，因此 Swift 使用 Optional（?）接收。
    let phone: String?
    let email: String?
    let avatarUrl: String?

    // Identifiable 要求 id；使用后端 UUID 可避免列表刷新时错误复用视图。
    var id: String { uuid }
}

/// 正式行程摘要。status 与 FastAPI Trip 状态一致：1 未开始、2 进行中、3 已结束。
struct Trip: Decodable, Identifiable {
    // 行程主键，同时作为 SwiftUI 列表稳定标识。
    let uuid: String
    // 用户输入或计划转换后生成的行程名称。
    let title: String
    // 目的地可以暂未设置，所以用 Optional 接收 JSON null。
    let destination: String?
    // 行程起止日期由 APIClient 的自定义日期解码器转换为 Date。
    let startDate: Date
    let endDate: Date
    // 1=未开始、2=进行中、3=已结束；客户端用它筛选当前可记录足迹的行程。
    let status: Int

    var id: String { uuid }
}

struct ItineraryDay: Decodable, Identifiable {
    // 每日安排记录的主键，而非自然日字符串。
    let uuid: String
    // 该行程日对应的实际日期与第几天序号。
    let dayDate: Date
    let dayIndex: Int
    // 三个 Optional 字段允许用户只填写部分行程安排。
    let transportation: String?
    let accommodation: String?
    let notes: String?
    let spots: [ItinerarySpot]

    var id: String { uuid }
}

struct ItinerarySpot: Decodable, Identifiable {
    // 行程日内地点记录的主键与名称。
    let uuid: String
    let name: String
    let address: String?

    var id: String { uuid }
}

/// iOS 离线队列中的 GPS 样本；clientUuid 是服务端去重所需的稳定幂等键。
struct PendingLocationSample: Codable, Identifiable {
    // 客户端生成的 UUID，批量同步时作为服务端幂等去重键。
    let id: UUID
    // 位置必须绑定所属正式行程，避免不同旅行的轨迹混在一起。
    let tripUuid: String
    let latitude: Double
    let longitude: Double
    let accuracyM: Double?
    let speedMps: Double?
    let recordedAt: Date

    // 默认参数 id: UUID = UUID() 让调用方创建普通样本时无需手动生成标识。
    init(
        id: UUID = UUID(),
        tripUuid: String,
        latitude: Double,
        longitude: Double,
        accuracyM: Double?,
        speedMps: Double?,
        recordedAt: Date
    ) {
        self.id = id
        self.tripUuid = tripUuid
        self.latitude = latitude
        self.longitude = longitude
        self.accuracyM = accuracyM
        self.speedMps = speedMps
        self.recordedAt = recordedAt
    }

    /// Codable 默认将 id 编码为 UUID；服务端契约使用 clientUuid，因此显式映射字段名称。
    enum CodingKeys: String, CodingKey {
        case id = "clientUuid"
        case tripUuid, latitude, longitude, accuracyM, speedMps, recordedAt
    }
}

/// 当前可用于地图定位或打卡的单次定位结果；它不等同于已保存的足迹样本。
struct CurrentLocationFix {
    // Core Location 的坐标、采样时间和水平误差共同决定此位置是否足够新鲜、可信。
    let coordinate: CLLocationCoordinate2D
    let recordedAt: Date
    let accuracyM: CLLocationAccuracy

    /// 单次定位过期后仍可展示在地图上，但打卡等操作应重新请求系统定位。
    func isFresh(within interval: TimeInterval = 30, now: Date = Date()) -> Bool {
        now.timeIntervalSince(recordedAt) <= interval
    }
}

/// FastAPI 返回的已同步轨迹点，供 MapKit 读取与渲染。
struct FootprintLocation: Decodable, Identifiable {
    // 已写入 FastAPI/MySQL 的轨迹点主键，与本地 PendingLocationSample 的 id 不同。
    let uuid: String
    let latitude: Double
    let longitude: Double
    let accuracyM: Double?
    let speedMps: Double?
    let recordedAt: Date

    var id: String { uuid }
}

/// 批量 GPS 同步结果；成功后 iOS 才能从本地队列移除对应样本。
struct LocationSyncResult: Decodable {
    // 新接收数量与命中幂等去重的重复数量；两者都代表本地样本可安全移除。
    let acceptedCount: Int
    let duplicateCount: Int
}

/// 手动打卡请求，使用当前位置并绑定进行中的正式行程；Encodable 表示仅需要写入 JSON。
struct CheckinRequest: Encodable {
    // 归属行程、展示地点、坐标、可选备注和用户触发时刻组成一次打卡事实。
    let tripUuid: String
    let locationName: String
    let latitude: Double
    let longitude: Double
    let note: String?
    let checkedAt: Date
}

/// 服务端已持久化的打卡记录；Decodable 表示只从 JSON 读取，不由客户端直接编码。
struct Checkin: Decodable, Identifiable {
    // uuid 是服务端主键；tripUuid 保留归属关系，供地图按行程加载。
    let uuid: String
    let tripUuid: String
    let locationName: String
    let latitude: Double
    let longitude: Double
    let note: String?
    let checkedAt: Date

    var id: String { uuid }
}
