import Foundation

enum APIConfiguration {
    /// 从 Info.plist 读取 API 根地址，等价于 Web 项目通过环境变量配置 baseURL。
    /// 真机不能访问自身的 127.0.0.1，需改为运行 FastAPI 电脑的局域网 IP。
    static var baseURL: URL {
        let configuredURL = Bundle.main.object(forInfoDictionaryKey: "VAGO_API_BASE_URL") as? String
        let rawURL = configuredURL?.trimmingCharacters(in: .whitespacesAndNewlines)
        // Info.plist 未配置时才使用模拟器本地开发默认值。
        return URL(string: rawURL?.isEmpty == false ? rawURL! : "http://127.0.0.1:8000/api/v1")!
    }
}
