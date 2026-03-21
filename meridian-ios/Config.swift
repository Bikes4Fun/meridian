/**
 * Meridian iOS – API configuration.
 * Change API_BASE_URL for local vs Railway/production.
 * All iOS/Swift code is isolated in meridian-ios/; no repo coupling.
 */
import Foundation

enum Config {
    /// API base URL (no trailing slash). Local: http://127.0.0.1:8000 ; Railway: your deployed URL.
    static var apiBaseURL: String {
        (Bundle.main.object(forInfoDictionaryKey: "MERIDIAN_API_URL") as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "/$", with: "", options: .regularExpression)
            ?? "http://127.0.0.1:8000"
    }
}
