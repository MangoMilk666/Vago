import Foundation
import UIKit

@MainActor
final class SessionStore: ObservableObject {
    // ObservableObject 发布的属性变化会驱动依赖它的 SwiftUI 视图更新。
    enum State { case launching, signedOut, signedIn }

    @Published private(set) var state: State = .launching
    @Published private(set) var profile: UserProfile?
    private(set) var tokens: TokenPair?
    private let client = APIClient()

    func restoreSession() async {
        do {
            guard let tokens = try KeychainStore.load() else {
                state = .signedOut
                return
            }
            self.tokens = tokens
            // 不仅信任本地 Keychain：启动时请求 profile，确认 token 仍被服务端接受。
            profile = try await client.request(path: "users/profile", tokenProvider: self)
            state = .signedIn
        } catch {
            // 分支条件：本地令牌过期或不可用时清理会话，避免进入半登录状态。
            KeychainStore.clear()
            tokens = nil
            state = .signedOut
        }
    }

    func login(phone: String, code: String) async throws {
        // identifierForVendor 在同一供应商的应用安装周期内稳定，可作为 iOS 设备会话标识。
        let deviceID = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
        let payload = PhoneLoginRequest(phone: phone, code: code, clientType: "ios", deviceId: deviceID)
        let response: LoginResponse = try await client.request(path: "auth/login/phone", method: "POST", body: payload)
        try KeychainStore.save(response.tokens)
        tokens = response.tokens
        profile = response.userInfo
        state = .signedIn
    }

    func sendSMSCode(to phone: String) async throws {
        let _: SMSCodeResponse = try await client.request(
            path: "auth/sms/send",
            method: "POST",
            body: SMSCodeRequest(phone: phone)
        )
    }

    func logout() async {
        let currentTokens = tokens
        if let currentTokens {
            try? await client.requestWithoutResponse(
                path: "auth/logout",
                method: "POST",
                body: RefreshRequest(refreshToken: currentTokens.refreshToken),
                accessToken: currentTokens.accessToken
            )
        }
        KeychainStore.clear()
        tokens = nil
        profile = nil
        state = .signedOut
    }

    fileprivate func validAccessToken() async throws -> String {
        guard let tokens else { throw APIError.unauthorized }
        return tokens.accessToken
    }

    fileprivate func refreshAccessToken() async throws -> String {
        guard let tokens else { throw APIError.unauthorized }
        // refresh token 只用于换取新 token 对，随后立即覆盖 Keychain 中的旧值。
        let refreshed: TokenPair = try await client.request(
            path: "auth/token/refresh",
            method: "POST",
            body: RefreshRequest(refreshToken: tokens.refreshToken)
        )
        try KeychainStore.save(refreshed)
        self.tokens = refreshed
        return refreshed.accessToken
    }
}

private struct PhoneLoginRequest: Encodable {
    let phone: String
    let code: String
    let clientType: String
    let deviceId: String
}

private struct RefreshRequest: Encodable { let refreshToken: String }
private struct SMSCodeRequest: Encodable { let phone: String }
private struct SMSCodeResponse: Decodable { let expireSeconds: Int }

@MainActor
final class APIClient {
    // 该客户端与 SessionStore 均固定在主 Actor，避免 Swift 6 下会话状态跨线程读写。
    // URLSession 自身不会占用主线程等待网络返回。
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        // FastAPI datetime 通常是完整 ISO 8601，而 Python date 会输出 yyyy-MM-dd；两者都需兼容。
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)
            // 格式化器限定在 Sendable 解码闭包内，避免 Swift 6 的 Actor 隔离警告。
            if let timestamp = ISO8601DateFormatter().date(from: value) {
                return timestamp
            }
            let calendarDateFormatter = DateFormatter()
            // 固定 POSIX locale 与 UTC，避免设备语言或时区导致 yyyy-MM-dd 被解析成不同日期。
            calendarDateFormatter.locale = Locale(identifier: "en_US_POSIX")
            calendarDateFormatter.timeZone = TimeZone(secondsFromGMT: 0)
            calendarDateFormatter.dateFormat = "yyyy-MM-dd"
            if let calendarDate = calendarDateFormatter.date(from: value) {
                return calendarDate
            }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "不支持的日期格式：\(value)"
            )
        }
        return decoder
    }()

    func request<Value: Decodable>(path: String, tokenProvider: SessionStore? = nil) async throws -> Value {
        let token = try await tokenProvider?.validAccessToken()
        return try await perform(path: path, method: "GET", body: nil, accessToken: token, tokenProvider: tokenProvider)
    }

    func request<Value: Decodable, Body: Encodable>(path: String, method: String, body: Body) async throws -> Value {
        try await perform(path: path, method: method, body: try JSONEncoder().encode(body), accessToken: nil, tokenProvider: nil)
    }

    func requestWithoutResponse<Body: Encodable>(path: String, method: String, body: Body, accessToken: String) async throws {
        let _: EmptyResponse = try await perform(path: path, method: method, body: try JSONEncoder().encode(body), accessToken: accessToken, tokenProvider: nil)
    }

    private func perform<Value: Decodable>(
        path: String,
        method: String,
        body: Data?,
        accessToken: String?,
        tokenProvider: SessionStore?,
        retried: Bool = false
    ) async throws -> Value {
        // URLRequest 类似 axios 的单次请求配置；body 已在上层编码为 JSON Data。
        var request = URLRequest(url: APIConfiguration.baseURL.appending(path: path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let accessToken { request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization") }
        if let body { request.httpBody = body }

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        // 分支条件：access token 首次失效时刷新一次并重放原请求，防止循环刷新。
        if httpResponse.statusCode == 401, let tokenProvider, !retried {
            let refreshedToken = try await tokenProvider.refreshAccessToken()
            return try await perform(path: path, method: method, body: body, accessToken: refreshedToken, tokenProvider: tokenProvider, retried: true)
        }
        guard 200..<300 ~= httpResponse.statusCode else {
            throw APIError.server(message: decodeMessage(from: data), statusCode: httpResponse.statusCode)
        }
        // JSONDecoder 相当于 Pydantic 响应模型的客户端反序列化与字段校验。
        let envelope = try decoder.decode(APIEnvelope<Value>.self, from: data)
        guard envelope.code == 200, let value = envelope.data else {
            throw APIError.server(message: envelope.message, statusCode: httpResponse.statusCode)
        }
        return value
    }

    private func decodeMessage(from data: Data) -> String {
        (try? decoder.decode(APIEnvelope<EmptyResponse>.self, from: data).message) ?? "请求失败，请稍后重试"
    }
}

private struct EmptyResponse: Decodable {}

enum APIError: LocalizedError {
    case unauthorized
    case invalidResponse
    case server(message: String, statusCode: Int)

    var errorDescription: String? {
        switch self {
        case .unauthorized: return "登录已失效，请重新登录"
        case .invalidResponse: return "服务响应异常"
        case let .server(message, _): return message
        }
    }
}
