import SwiftUI

enum AppAppearance: String, CaseIterable, Identifiable {
    case system
    case light
    case dark

    var id: String { rawValue }

    var title: String {
        switch self {
        case .system: "跟随系统"
        case .light: "日间模式"
        case .dark: "夜间模式"
        }
    }

    var colorScheme: ColorScheme? {
        switch self {
        case .system: nil
        case .light: .light
        case .dark: .dark
        }
    }
}

enum AppTheme: String, CaseIterable, Identifiable {
    case indigo
    case ocean
    case forest
    case sunset

    var id: String { rawValue }

    var title: String {
        switch self {
        case .indigo: "经典靛蓝"
        case .ocean: "海洋青蓝"
        case .forest: "森林绿"
        case .sunset: "日落暖橘"
        }
    }

    var accent: Color {
        switch self {
        case .indigo: .indigo
        case .ocean: Color(red: 0.00, green: 0.41, blue: 0.55)
        case .forest: Color(red: 0.13, green: 0.43, blue: 0.32)
        case .sunset: Color(red: 0.72, green: 0.29, blue: 0.23)
        }
    }

    var route: Color { accent }

    var checkin: Color {
        switch self {
        case .indigo: Color(red: 0.91, green: 0.36, blue: 0.48)
        case .ocean: Color(red: 0.05, green: 0.54, blue: 0.51)
        case .forest: Color(red: 0.66, green: 0.37, blue: 0.18)
        case .sunset: Color(red: 0.54, green: 0.31, blue: 0.59)
        }
    }

    func background(for scheme: ColorScheme) -> Color {
        if scheme == .dark {
            switch self {
            case .indigo: Color(red: 0.08, green: 0.08, blue: 0.13)
            case .ocean: Color(red: 0.05, green: 0.11, blue: 0.13)
            case .forest: Color(red: 0.07, green: 0.11, blue: 0.09)
            case .sunset: Color(red: 0.13, green: 0.08, blue: 0.08)
            }
        } else {
            switch self {
            case .indigo: Color(red: 0.97, green: 0.97, blue: 1.00)
            case .ocean: Color(red: 0.94, green: 0.98, blue: 0.99)
            case .forest: Color(red: 0.95, green: 0.98, blue: 0.95)
            case .sunset: Color(red: 1.00, green: 0.97, blue: 0.95)
            }
        }
    }

    func surface(for scheme: ColorScheme) -> Color {
        guard scheme == .dark else { return .white }
        return switch self {
        case .indigo: Color(red: 0.16, green: 0.16, blue: 0.22)
        case .ocean: Color(red: 0.11, green: 0.19, blue: 0.21)
        case .forest: Color(red: 0.13, green: 0.19, blue: 0.15)
        case .sunset: Color(red: 0.21, green: 0.14, blue: 0.14)
        }
    }
}

private struct AppThemeKey: EnvironmentKey {
    static let defaultValue: AppTheme = .indigo
}

extension EnvironmentValues {
    var appTheme: AppTheme {
        get { self[AppThemeKey.self] }
        set { self[AppThemeKey.self] = newValue }
    }
}

private struct ThemeScrollBackground: ViewModifier {
    @Environment(\.appTheme) private var theme
    @Environment(\.colorScheme) private var colorScheme

    func body(content: Content) -> some View {
        content
            .scrollContentBackground(.hidden)
            .background(theme.background(for: colorScheme))
    }
}

extension View {
    func themedScrollBackground() -> some View {
        modifier(ThemeScrollBackground())
    }
}
