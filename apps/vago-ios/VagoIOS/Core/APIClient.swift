import Foundation
import UIKit

@MainActor
final class SessionStore: ObservableObject {
    // @MainActor 将整个对象隔离到主线程；UI 状态修改不必额外 DispatchQueue.main.async。
    // ObservableObject 发布的属性变化会驱动依赖它的 SwiftUI 视图更新。
    enum State { case launching, signedOut, signedIn }

    // @Published 是 Combine 的发布属性；private(set) 允许页面读取，但只允许 Store 自己改变状态。
    @Published private(set) var state: State = .launching
    @Published private(set) var profile: UserProfile?
    // token 不发布到 UI，避免令牌变化无意义地触发视图重绘。
    private(set) var tokens: TokenPair?
    private let client = APIClient()

    func restoreSession() async {
        // async 函数可在 await 处挂起，网络请求期间不会阻塞主线程和首屏动画。
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
        // throws 把网络或 Keychain 错误交给 LoginView 展示，Store 不在这里决定 UI 文案。
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
        // let _: 忽略成功响应中的 expireSeconds，只关心请求是否成功。
        let _: SMSCodeResponse = try await client.request(
            path: "auth/sms/send",
            method: "POST",
            body: SMSCodeRequest(phone: phone)
        )
    }

    func logout() async {
        // 先复制 Optional token，避免 await 期间状态更新造成对属性的非预期读取。
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
        // fileprivate 使 APIClient 可访问此方法，但其他文件无法直接读取 token。
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
    // private 限制请求 DTO 只在本文件使用，避免网络实现细节泄漏到功能视图。
    let phone: String
    let code: String
    let clientType: String
    let deviceId: String
}

// 单行 struct 适合只有一个字段的小型请求体；与 FastAPI Pydantic request schema 对应。
private struct RefreshRequest: Encodable { let refreshToken: String }
private struct SMSCodeRequest: Encodable { let phone: String }
private struct SMSCodeResponse: Decodable { let expireSeconds: Int }

@MainActor
final class APIClient {
    // APIClient 是全部 HTTP 调用的统一入口，类似 Web 项目中的 axios client / request interceptor。
    // 该客户端与 SessionStore 均固定在主 Actor，避免 Swift 6 下会话状态跨线程读写。
    // URLSession 自身不会占用主线程等待网络返回。
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        // FastAPI datetime 以 ISO 8601 UTC 返回，兼容窗口内也需读取既有 MySQL 无时区 DATETIME。
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
            let localDateTimeFormatter = DateFormatter()
            // 历史 MySQL DATETIME 没有时区信息，按服务端约定将其解释为 UTC。
            localDateTimeFormatter.locale = Locale(identifier: "en_US_POSIX")
            localDateTimeFormatter.timeZone = TimeZone(secondsFromGMT: 0)
            for dateFormat in ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"] {
                localDateTimeFormatter.dateFormat = dateFormat
                // 分支条件：命中无时区的历史 datetime 格式时，以 UTC 返回给 SwiftUI。
                if let localDateTime = localDateTimeFormatter.date(from: value) {
                    return localDateTime
                }
            }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "不支持的日期格式：\(value)"
            )
        }
        return decoder
    }()

    func request<Value: Decodable>(path: String, tokenProvider: SessionStore? = nil) async throws -> Value {
        // Value 是泛型占位符；调用处声明 [Trip]、UserProfile 等类型即可推断 JSON data 的目标类型。
        let token = try await tokenProvider?.validAccessToken()
        return try await perform(path: path, method: "GET", body: nil, accessToken: token, tokenProvider: tokenProvider)
    }

    func request<Value: Decodable, Body: Encodable>(path: String, method: String, body: Body) async throws -> Value {
        // 此重载用于无需登录的请求，例如发送短信验证码。
        try await perform(path: path, method: method, body: try encode(body), accessToken: nil, tokenProvider: nil)
    }

    func request<Value: Decodable, Body: Encodable>(path: String, method: String, body: Body, tokenProvider: SessionStore) async throws -> Value {
        // 此重载要求 SessionStore，编译期明确提醒调用方该接口必须携带 JWT。
        let token = try await tokenProvider.validAccessToken()
        return try await perform(path: path, method: method, body: try encode(body), accessToken: token, tokenProvider: tokenProvider)
    }

    func requestWithoutResponse<Body: Encodable>(path: String, method: String, body: Body, accessToken: String) async throws {
        // 用 EmptyResponse 占位复用统一解析流程，适合 data 为 null 的退出登录接口。
        let _: EmptyResponse = try await perform(path: path, method: method, body: try encode(body), accessToken: accessToken, tokenProvider: nil)
    }

    private func encode<Body: Encodable>(_ body: Body) throws -> Data {
        let encoder = JSONEncoder()
        // FastAPI 的 datetime 字段采用 ISO 8601；避免 JSONEncoder 默认把 Date 编成 Unix 秒数。
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(body)
    }

    private func perform<Value: Decodable>(
        path: String,
        method: String,
        body: Data?,
        accessToken: String?,
        tokenProvider: SessionStore?,
        // 默认参数让首次调用省略 retried；401 刷新后递归重放时传 true，限制最多一次重试。
        retried: Bool = false
    ) async throws -> Value {
        // URLRequest 类似 axios 的单次请求配置；body 已在上层编码为 JSON Data。
        var request = URLRequest(url: APIConfiguration.baseURL.appending(path: path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let accessToken { request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization") }
        if let body { request.httpBody = body }

        // 元组解包同时取得响应 body 与元数据；URLSession 会在后台执行实际 I/O。
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
        // 先尝试项目统一 envelope；try? 失败返回 nil，而不是把错误继续抛给错误处理路径。
        if let envelope = try? decoder.decode(APIEnvelope<EmptyResponse>.self, from: data) {
            return envelope.message
        }
        // FastAPI 中间件的 429 响应使用 detail 字段，保留它才能让页面展示实际失败原因。
        if let error = try? decoder.decode(APIErrorResponse.self, from: data) {
            return error.detail ?? error.message ?? "请求失败，请稍后重试"
        }
        return "请求失败，请稍后重试"
    }
}

// 空结构体满足泛型 Decodable 约束，用于不包含 data 的成功响应。
private struct EmptyResponse: Decodable {}

private struct APIErrorResponse: Decodable {
    // FastAPI 中间件原生错误采用 detail，业务异常 envelope 则通常使用 message。
    let detail: String?
    let message: String?
}

enum APIError: LocalizedError {
    // enum 将有限的网络失败类型建模为穷举分支，switch 会要求后续新增类型时补全展示文案。
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
