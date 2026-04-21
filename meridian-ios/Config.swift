/**
 * Meridian iOS – API configuration.
 *
 * Precedence for `resolvedApiBaseURL`:
 *  1. UserDefaults (Developer tab / login) — non-empty saved override
 *  2. Info.plist `MERIDIAN_API_URL` only (Xcode → target → Build Settings → `MERIDIAN_API_URL` / `INFOPLIST_KEY_MERIDIAN_API_URL`)
 */
import Foundation

enum Config {
    private static let savedApiBaseURLKey = "meridian_api_base_url"
    private static let fallbackApiBaseURL = "https://denary-unneglected-alease.ngrok-free.dev"

    static let apiBaseURLDidChangeNotification = Notification.Name("meridianApiBaseURLDidChange")

    static func normalizedBaseURL(_ raw: String) -> String {
        var s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        while s.hasSuffix("/") {
            s.removeLast()
        }
        return s
    }

    /// True if the string is a usable http(s) API base URL (avoids empty / malformed URLs).
    static func isValidHttpBaseURL(_ urlString: String) -> Bool {
        guard !urlString.isEmpty,
              let u = URL(string: urlString),
              let scheme = u.scheme,
              scheme == "http" || scheme == "https",
              u.host != nil, !(u.host?.isEmpty ?? true) else {
            return false
        }
        return true
    }

    /// Value baked into the app at build time (Info.plist `MERIDIAN_API_URL` only).
    static var launchBundledApiBaseURL: String {
        let fromPlist = (Bundle.main.object(forInfoDictionaryKey: "MERIDIAN_API_URL") as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "/$", with: "", options: .regularExpression) ?? ""
        let normalized = normalizedBaseURL(fromPlist)
        if !normalized.isEmpty { return normalized }
        return fallbackApiBaseURL
    }

    /// Effective API base URL (no trailing slash).
    static var resolvedApiBaseURL: String {
        if let s = UserDefaults.standard.string(forKey: savedApiBaseURLKey) {
            let t = normalizedBaseURL(s)
            if !t.isEmpty { return t }
        }
        return launchBundledApiBaseURL
    }

    static func saveApiBaseURL(_ raw: String) {
        let t = normalizedBaseURL(raw)
        if t.isEmpty {
            UserDefaults.standard.removeObject(forKey: savedApiBaseURLKey)
        } else {
            UserDefaults.standard.set(t, forKey: savedApiBaseURLKey)
        }
    }

    static var apiBaseURL: String { resolvedApiBaseURL }

    static func persistedApiBaseURLFieldText() -> String {
        UserDefaults.standard.string(forKey: savedApiBaseURLKey) ?? ""
    }
}
