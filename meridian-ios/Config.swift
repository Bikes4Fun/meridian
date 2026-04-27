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

    /// Demo ngrok API (probed first when no saved base URL).
    static let demoNgrokApiBaseURL = "https://denary-unneglected-alease.ngrok-free.dev"
    /// Demo Railway API (second probe). Matches `src/shared/api_config.json` railway_api_url.
    static let demoRailwayApiBaseURL = "https://meridian-by-deanna.computerscience.build"

    private static let fallbackApiBaseURL = demoNgrokApiBaseURL

    /// Per-host timeout for `GET …/api/health` during startup discovery.
    static let apiHealthCheckTimeoutSeconds: TimeInterval = 4.0

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

    /// Tries demo ngrok then Railway; returns normalized base URL on first successful `/api/health`, else nil.
    static func discoverDemoBackendBaseURL() async -> String? {
        let timeout = apiHealthCheckTimeoutSeconds
        for base in [demoNgrokApiBaseURL, demoRailwayApiBaseURL].map({ normalizedBaseURL($0) }) {
            if await checkApiHealth(atBaseURL: base, timeout: timeout) {
                return base
            }
        }
        return nil
    }

    static func isDemoPresetApiBaseURL(_ raw: String) -> Bool {
        let n = normalizedBaseURL(raw)
        return n == normalizedBaseURL(demoNgrokApiBaseURL) || n == normalizedBaseURL(demoRailwayApiBaseURL)
    }

    static func isReleasedDemoRailwayURL(_ raw: String) -> Bool {
        normalizedBaseURL(raw) == normalizedBaseURL(demoRailwayApiBaseURL)
    }

    /// Always tries ngrok then Railway first. If both fail, clears a saved demo preset and returns nil so the UI prompts. If persisted is not a demo URL, returns it only when `/api/health` succeeds.
    static func resolveBackendBaseURL() async -> String? {
        if let discovered = await discoverDemoBackendBaseURL() {
            return discovered
        }
        let persisted = normalizedBaseURL(persistedApiBaseURLFieldText())
        if isDemoPresetApiBaseURL(persisted) {
            saveApiBaseURL("")
            return nil
        }
        if !persisted.isEmpty, await checkApiHealth(atBaseURL: persisted, timeout: apiHealthCheckTimeoutSeconds) {
            return persisted
        }
        return nil
    }

    /// True when `GET {base}/api/health` returns HTTP 200 within `timeout` seconds.
    static func checkApiHealth(atBaseURL base: String, timeout: TimeInterval) async -> Bool {
        let baseNorm = normalizedBaseURL(base)
        guard let url = URL(string: baseNorm + "/api/health") else { return false }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.timeoutInterval = timeout
        if let host = url.host, host.contains("ngrok") {
            req.setValue("true", forHTTPHeaderField: "ngrok-skip-browser-warning")
        }
        do {
            let (_, response) = try await URLSession.shared.data(for: req)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }
}
