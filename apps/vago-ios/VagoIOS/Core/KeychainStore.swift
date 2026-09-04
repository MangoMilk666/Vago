import Foundation
import Security

enum KeychainStore {
    // service + account 共同构成 Keychain 的查询主键，类似一个仅系统可访问的命名空间。
    private static let service = "com.vago.ios.auth"
    private static let account = "token-pair"

    static func save(_ tokens: TokenPair) throws {
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
    case saveFailed
    case readFailed

    var errorDescription: String? {
        switch self {
        case .saveFailed: return "无法安全保存登录信息"
        case .readFailed: return "无法读取登录信息"
        }
    }
}
