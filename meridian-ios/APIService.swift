/**
 * Meridian iOS – API client. Login, alert, check-in, contacts, chat URL.
 * Uses URLSession with cookie storage for session auth.
 */
import Foundation
import CoreLocation

enum APIError: LocalizedError {
    case invalidResponse
    case serverError(String)
    case unauthorized

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Invalid response"
        case .serverError(let msg): return msg
        case .unauthorized: return "Not logged in"
        }
    }
}

struct SessionInfo {
    let userId: String
    let familyCircleId: String
}

struct Contact {
    let id: String
    let displayName: String
    let sendbirdUserId: String?
    let userId: String?
}

struct CheckIn {
    let contactName: String
    let locationName: String?
    let timestamp: Date
}

final class APIService {
    static let shared = APIService()
    private let baseURL: String
    private let session: URLSession

    init(baseURL: String = Config.apiBaseURL) {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.default
        config.httpCookieStorage = HTTPCookieStorage.shared
        config.httpShouldSetCookies = true
        config.httpCookieAcceptPolicy = .always
        self.session = URLSession(configuration: config)
    }

    private func url(_ path: String) -> URL? {
        let s = path.hasPrefix("/") ? path : "/" + path
        return URL(string: baseURL + s)
    }

    private func request(_ path: String, method: String = "GET", body: [String: Any]? = nil) async throws -> (Data, HTTPURLResponse) {
        guard let u = url(path) else { throw APIError.invalidResponse }
        var req = URLRequest(url: u)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        if let b = body {
            req.httpBody = try JSONSerialization.data(withJSONObject: b)
        }
        let (data, res) = try await session.data(for: req)
        guard let http = res as? HTTPURLResponse else { throw APIError.invalidResponse }
        return (data, http)
    }

    // MARK: - Login

    func login(userId: String, familyCircleId: String) async throws {
        let (_, res) = try await request("/api/login", method: "POST", body: [
            "user_id": userId,
            "family_circle_id": familyCircleId
        ])
        if res.statusCode != 200 { throw APIError.unauthorized }
    }

    func getSession() async throws -> SessionInfo {
        let (data, res) = try await request("/api/session")
        if res.statusCode == 401 { throw APIError.unauthorized }
        if res.statusCode != 200 {
            throw APIError.serverError("Session check failed")
        }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let uid = json["user_id"] as? String,
              let fid = json["family_circle_id"] as? String else {
            throw APIError.invalidResponse
        }
        return SessionInfo(userId: uid, familyCircleId: fid)
    }

    // MARK: - Alert

    func setAlert(activated: Bool) async throws {
        let (_, res) = try await request("/api/emergency/alert", method: "POST", body: ["activated": activated])
        if res.statusCode != 200 {
            throw APIError.serverError("Alert request failed")
        }
    }

    // MARK: - Check-in

    func checkIn(familyCircleId: String, userId: String, latitude: Double, longitude: Double, notes: String?) async throws {
        let path = "/api/family_circles/\(familyCircleId)/create_checkin"
        var body: [String: Any] = [
            "user_id": userId,
            "latitude": latitude,
            "longitude": longitude
        ]
        if let n = notes, !n.isEmpty { body["notes"] = n }
        let (_, res) = try await request(path, method: "POST", body: body)
        if res.statusCode != 201 && res.statusCode != 200 {
            throw APIError.serverError("Check-in failed")
        }
    }

    func getCheckins(familyCircleId: String) async throws -> [CheckIn] {
        let path = "/api/family_circles/\(familyCircleId)/get_checkins"
        let (data, res) = try await request(path)
        if res.statusCode != 200 { throw APIError.serverError("Failed to load check-ins") }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let arr = json["data"] as? [[String: Any]] else {
            throw APIError.invalidResponse
        }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return arr.compactMap { row -> CheckIn? in
            guard let name = row["contact_name"] as? String else { return nil }
            let loc = row["location_name"] as? String
            let tsStr = row["timestamp"] as? String
            let ts = tsStr.flatMap { formatter.date(from: $0) } ?? Date.distantPast
            return CheckIn(contactName: name, locationName: (loc?.isEmpty == true) ? nil : loc, timestamp: ts)
        }
    }

    // MARK: - Contacts (for chat)

    func getContacts(familyCircleId: String) async throws -> [Contact] {
        let path = "/api/family_circles/\(familyCircleId)/contacts"
        let (data, res) = try await request(path)
        if res.statusCode != 200 { throw APIError.serverError("Contacts failed") }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let arr = json["data"] as? [[String: Any]] else {
            throw APIError.invalidResponse
        }
        return arr.compactMap { row in
            guard let id = row["id"] as? String,
                  let name = row["display_name"] as? String else { return nil }
            let sb = row["sendbird_user_id"] as? String
            let uid = row["user_id"] as? String
            return Contact(id: id, displayName: name, sendbirdUserId: sb, userId: uid)
        }.filter { $0.sendbirdUserId != nil && !($0.sendbirdUserId?.isEmpty ?? true) }
    }

    // MARK: - Chat URL

    func getChatSessionURL(familyCircleId: String, recipientSendbirdUserId: String, recipientDisplayName: String) async throws -> URL {
        var comp = URLComponents(string: baseURL + "/api/chat/chat-session-url")
        comp?.queryItems = [
            URLQueryItem(name: "recipient_sendbird_user_id", value: recipientSendbirdUserId),
            URLQueryItem(name: "recipient_display_name", value: recipientDisplayName)
        ]
        guard let u = comp?.url else { throw APIError.invalidResponse }
        var req = URLRequest(url: u)
        req.httpMethod = "GET"
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, res) = try await session.data(for: req)
        guard let http = res as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.serverError("Chat URL failed")
        }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let urlStr = json["url"] as? String,
              let url = URL(string: urlStr) else {
            throw APIError.invalidResponse
        }
        return url
    }
}
