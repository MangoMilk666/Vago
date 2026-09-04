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
