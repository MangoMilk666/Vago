import Foundation

/// 对齐 FastAPI `{ code, message, data }` 响应；`Value` 是泛型，调用处决定 data 的具体模型。
struct APIEnvelope<Value: Decodable>: Decodable {
    let code: Int
    let message: String
    let data: Value?
}

/// Codable 同时包含 Encodable / Decodable，可在 JSON 与 Keychain 二进制数据之间转换。
struct TokenPair: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    let sessionId: String?
}

/// 登录接口返回的业务数据，字段名通过 Codable 自动映射同名 JSON camelCase 字段。
struct LoginResponse: Decodable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    let sessionId: String?
    let userInfo: UserProfile

    var tokens: TokenPair {
        TokenPair(accessToken: accessToken, refreshToken: refreshToken, expiresIn: expiresIn, sessionId: sessionId)
    }
}

/// Identifiable 提供稳定 id，SwiftUI 的 List / ForEach 用它识别列表元素。
struct UserProfile: Codable, Identifiable {
    let uuid: String
    let nickname: String
    let phone: String?
    let email: String?
    let avatarUrl: String?

    var id: String { uuid }
}

struct Trip: Decodable, Identifiable {
    let uuid: String
    let title: String
    let destination: String?
    let startDate: Date
    let endDate: Date
    let status: Int

    var id: String { uuid }
}

struct ItineraryDay: Decodable, Identifiable {
    let uuid: String
    let dayDate: Date
    let dayIndex: Int
    let transportation: String?
    let accommodation: String?
    let notes: String?
    let spots: [ItinerarySpot]

    var id: String { uuid }
}

struct ItinerarySpot: Decodable, Identifiable {
    let uuid: String
    let name: String
    let address: String?

    var id: String { uuid }
}

/// iOS 离线队列中的 GPS 样本；clientUuid 是服务端去重所需的稳定幂等键。
struct PendingLocationSample: Codable, Identifiable {
    let id: UUID
    let tripUuid: String
    let latitude: Double
    let longitude: Double
    let accuracyM: Double?
    let speedMps: Double?
    let recordedAt: Date

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

/// FastAPI 返回的已同步轨迹点，供 MapKit 读取与渲染。
struct FootprintLocation: Decodable, Identifiable {
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
    let acceptedCount: Int
    let duplicateCount: Int
}

/// 手动打卡请求，使用当前位置并绑定进行中的正式行程。
/// 可序列化
struct CheckinRequest: Encodable {
    let tripUuid: String
    let locationName: String
    let latitude: Double
    let longitude: Double
    let note: String?
    let checkedAt: Date
}

/// 可反序列化的VO
struct Checkin: Decodable, Identifiable {
    let uuid: String
    let tripUuid: String
    let locationName: String
    let latitude: Double
    let longitude: Double
    let note: String?
    let checkedAt: Date

    var id: String { uuid }
}
