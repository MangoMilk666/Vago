import Foundation
import UIKit

@MainActor
final class SessionStore: ObservableObject {
    // @MainActor 将整个对象隔离到主线程；UI 状态修改不必额外 DispatchQueue.main.async。
    // ObservableObject 发布的属性变化会驱动依赖它的 SwiftUI 视图更新。
    // 三种state：加载中/已登出/已登录
    enum State { case launching, signedOut, signedIn }

    // @Published 是 Combine 的发布属性；
    // private(set) 允许页面读取，但只允许 Store 自己改变状态。外部可以读取这个属性，但是只有当前类型内部可以修改它。
    // 相当于Java 可get不可set
    // @Published: 当 state 被修改时，对外发布“这个值变了”的通知，让正在观察 SessionStore 的 UI 有机会自动更新。
    @Published private(set) var state: State = .launching
    @Published private(set) var profile: UserProfile?
    
    // token 不发布到 UI，避免令牌变化无意义地触发视图重绘。
    private(set) var tokens: TokenPair?
    private let client = APIClient()
    
    // Task?: 可能保存着一个“未来会异步产生 String，也可能抛出 Error”的任务
    // 并发请求同时收到 401 时共用同一个 refresh Task，避免令牌轮换后互相覆盖。
    private var refreshTask: Task<String, Error>?

    func restoreSession() async {
        // async 函数可在 await 处挂起，网络请求期间不会阻塞主线程和首屏动画。
        do {
            // 如果 KeychainStore.load() != nil -> 把它解包后赋值给 tokens; else return
            guard let tokens = try KeychainStore.load() else {
                state = .signedOut
                return
            }
            self.tokens = tokens
            // 不仅信任本地 Keychain：启动时请求 profile，确认 token 仍被服务端接受。
            profile = try await client.request(path: "users/profile", tokenProvider: self)
            SessionProfileCache.save(profile)
            state = .signedIn
        } catch {
            // 分支条件：临时网络不可达时保留 Keychain 凭证，并用最近资料恢复只读离线界面；
            // 服务端真正拒绝令牌时才清除登录态，不能把断网误判为退出。
            // Self: 表示当前这个类型本身（current type）。因为isTemporaryNetworkError是static
            // 所以调用可以用className.staticFunc()或者Self.staticFunc()
            if Self.isTemporaryNetworkError(error) {
                if let cachedProfile = SessionProfileCache.load() {
                    profile = cachedProfile
                    state = .signedIn
                } else {
                    // 首次离线启动、缺少展示资料时，只能停留登录页，但仍保留凭证，待网络恢复后继续验证。
                    state = .signedOut
                }
            } else {
                KeychainStore.clear()
                tokens = nil
                profile = nil
                state = .signedOut
            }
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
        SessionProfileCache.save(response.userInfo)
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
        SessionProfileCache.clear()
        state = .signedOut
    }

    fileprivate func validAccessToken() async throws -> String {
        // fileprivate 使 APIClient 可访问此方法，但其他文件无法直接读取 token。
        guard let tokens else { throw APIError.unauthorized }
        return tokens.accessToken
    }
    
    /// 安全地刷新 access token，并保证并发请求共用同一个刷新任务
    // fileprivate: 函数只能在当前 Swift 文件内部访问。
    fileprivate func refreshAccessToken() async throws -> String {
        // 没 token → 直接 unauthorized
        guard let tokens else { throw APIError.unauthorized }
        
        // 已经有人正在 refresh → 不再发新请求 → 等已有 refreshTask 的结果
        if let refreshTask {
            return try await refreshTask.value
        }
        
        // 没人在 refresh → 创建一个新的 Task,在 MainActor 上运行 → 请求新 token → 保存新 token → 返回新的 accessToken
        // 换取新 token 对，随后立即覆盖 Keychain 中的旧值。
        // in: 前面是闭包的“参数/类型声明”，后面开始是闭包 body。这个闭包没有参数，可能抛异常，最终返回 String。
        let task = Task { @MainActor [client] () throws -> String in
            let refreshed: TokenPair = try await client.request(
                path: "auth/token/refresh",
                method: "POST",
                body: RefreshRequest(refreshToken: tokens.refreshToken)
            )
            try KeychainStore.save(refreshed)
            self.tokens = refreshed
            return refreshed.accessToken
        }
        refreshTask = task
        // 不管最后成功还是失败 → refreshTask 清回 nil
        // 防止 refreshTask 永远保留着一个失败的 Task。
        defer { refreshTask = nil }
        return try await task.value
    }

    private static func isTemporaryNetworkError(_ error: Error) -> Bool {
        // as?: 尝试安全转换。如果 error 能转成 URLError，就把它赋值给 urlError；否则赋值为nil
        // 类似java instanceof
        guard let urlError = error as? URLError else { return false }
        
        // 这些错误表示当前无法验证服务端会话，不代表 JWT 已失效。
        // urlError.code为enum，有若干caseName的枚举值
        // 当编译器已经知道枚举类型时，可以省略枚举类型名，只写 .caseName
        switch urlError.code {
        case .notConnectedToInternet, .networkConnectionLost, .timedOut,
                .cannotConnectToHost, .cannotFindHost, .dnsLookupFailed:
            return true
        default:
            return false
        }
    }
}

/// 仅缓存已登录账号的最小展示资料，支持断网时恢复本地待传足迹；不保存任何 token。
private enum SessionProfileCache {
    private static let storageKey = "vago.session.cached-profile"

    /// 用户资料存入UserDefaults
    static func save(_ profile: UserProfile?) {
        // 1.检查传进来的 profile 不是 nil，并把它解包成一个非 Optional 的局部变量 profile
        // 完整写法为 guard let profile = profile -> 因为左右变量同名，Swift 允许简写。
        // 2. try?：尝试执行一个可能抛异常的表达式；成功就返回结果，失败返回nil
        // 3. guard let两个表达式，相当于&&/and条件判断
        guard let profile, let data = try? JSONEncoder().encode(profile) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }
    
    /// 从UserDefaults取出用户profile信息
    static func load() -> UserProfile? {
        // kv对查找，得到json数据
        guard let data = UserDefaults.standard.data(forKey: storageKey) else { return nil }
        // 反序列化
        // UserProfile.self: 表示 UserProfile 这个类型本身，作为一个值传进去。
        // .self 的作用就是“把类型本身作为一个值引用出来”。相当于java className.class
        return try? JSONDecoder().decode(UserProfile.self, from: data)
    }
    
    /// 清除用户profile信息
    static func clear() {
        UserDefaults.standard.removeObject(forKey: storageKey)
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
            let fractionalISO8601 = ISO8601DateFormatter()
            fractionalISO8601.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let timestamp = fractionalISO8601.date(from: value) {
                return timestamp
            }
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

        // 用系统共享的 URLSession 发送 request，异步等待网络请求完成；成功后同时拿到响应 body 和响应元数据。
        // URLSession: Swift / iOS 里系统自带的 HTTP 网络客户端。
        // URLSession.shared: 系统提供的一个共享 URLSession 实例。
        // 把响应内容完整读进内存,返回tuple; 元组解包同时取得响应 body 与元数据；URLSession 会在后台执行实际 I/O。
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        
        // 分支条件：access token 首次失效时刷新一次并重放原请求，防止循环刷新。
        if httpResponse.statusCode == 401, let tokenProvider, !retried {
            let refreshedToken = try await tokenProvider.refreshAccessToken()
            return try await perform(path: path, method: method, body: body, accessToken: refreshedToken, tokenProvider: tokenProvider, retried: true)
        }
        
        // ~=: httpResponse.statusCode 是否匹配 200..<300 这个范围
        // 等价于 (200..<300).contains(httpResponse.statusCode)
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
