import Foundation
import Security

enum KeychainStore {
    // 该枚举只提供静态方法，不会被实例化；与 FastAPI 的认证存储职责相对应。
    // service + account 共同构成 Keychain 的查询主键，类似一个仅系统可访问的命名空间。
    private static let service = "com.vago.ios.auth"
    private static let account = "token-pair"

    static func save(_ tokens: TokenPair) throws {
        // Keychain 只接收 Data，因此先将 Codable 模型编码为 JSON 二进制内容。
        let data = try JSONEncoder().encode(tokens)
        let query = baseQuery
        // 当前设计每台设备只保存一个 Vago 会话，先删除旧值再写入新的 token 对。
        SecItemDelete(query as CFDictionary)
        let attributes = query.merging([
            kSecValueData as String: data,
            // 解锁过一次后后台刷新也可读取；ThisDeviceOnly 禁止凭证随备份迁移到其他设备。
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]) { _, new in new }
        guard SecItemAdd(attributes as CFDictionary, nil) == errSecSuccess else {
            throw KeychainError.saveFailed
        }
    }

    static func load() throws -> TokenPair? {
        // var 用于后续追加读取选项；Swift 的 Dictionary 是值类型，修改不会影响 baseQuery。
        var query = baseQuery
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        // 分支条件：Keychain 中没有登录凭证时，视为未登录而非异常。
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = item as? Data else {
            throw KeychainError.readFailed
        }
        return try JSONDecoder().decode(TokenPair.self, from: data)
    }

    static func clear() {
        // 删除是幂等操作：即便凭证已不存在，退出登录流程也无需额外处理错误。
        SecItemDelete(baseQuery as CFDictionary)
    }

    private static var baseQuery: [String: Any] {
        // Security 框架以字典描述查询条件，而不是像 UserDefaults 一样直接按字符串读写。
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}

enum KeychainError: LocalizedError {
    // LocalizedError 让 error.localizedDescription 能直接返回面向用户的中文消息。
    case saveFailed
    case readFailed

    var errorDescription: String? {
        switch self {
        case .saveFailed: return "无法安全保存登录信息"
        case .readFailed: return "无法读取登录信息"
        }
    }
}
