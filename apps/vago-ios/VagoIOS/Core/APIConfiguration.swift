import Foundation

enum APIConfiguration {
    // enum 不含实例成员时可作为命名空间使用，避免为全局配置创建不必要的对象。
    /// 从 Info.plist 读取 API 根地址，等价于 Web 项目通过环境变量配置 baseURL。
    /// 真机不能访问自身的 127.0.0.1，需改为运行 FastAPI 电脑的局域网 IP。
    static var baseURL: URL {
        // Bundle.main 对应已安装 App 的资源包，Info.plist 会被编译进该包。
        let configuredURL = Bundle.main.object(forInfoDictionaryKey: "VAGO_API_BASE_URL") as? String
        let rawURL = configuredURL?.trimmingCharacters(in: .whitespacesAndNewlines)
        // Info.plist 未配置时才使用模拟器本地开发默认值。
        // 此处使用强制解包是因为默认地址为代码常量且已验证合法；配置值异常会在开发期尽早暴露。
        return URL(string: rawURL?.isEmpty == false ? rawURL! : "http://127.0.0.1:8000/api/v1")!
    }
}
