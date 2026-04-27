/**
 * Meridian iOS – API client. Login, alert, check-in.
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

struct CheckIn {
    let contactName: String
    let locationName: String?
    let timestamp: Date
    let latitude: Double?
    let longitude: Double?
    let userId: String?
    let photoURL: String?
}

struct TodayEventSummary {
    let title: String
    let startTimeText: String?
}

struct MedicationHomeSnapshot {
    struct TimedRow {
        let slot: String
        let name: String
        let taken: Bool
        let groupTime: String?
    }

    struct PrnRow {
        let name: String
        let dosesToday: Int
        let maxDaily: Int?
        let lastTaken: String?
    }

    let timed: [TimedRow]
    let prn: [PrnRow]
}

/// One row in the Home “What’s next today” timeline (kiosk-style merged meds + calendar).
struct HomeTodayTimelineEntry {
    enum RowKind: Equatable {
        case medication
        case appointment
        case prn
    }

    let timeDisplay: String
    let title: String
    let done: Bool
    let kind: RowKind
    /// Minutes from midnight (sort key); used for “Up next” vs current time.
    let sortMinutes: Int

    /// First item that still needs attention (future pending med/appt, or PRN), matching kiosk `build_up_next_html`.
    func blocksUpNext(nowMinutes: Int) -> Bool {
        switch kind {
        case .prn:
            return true
        case .medication:
            if sortMinutes < nowMinutes { return false }
            return !done
        case .appointment:
            if sortMinutes < nowMinutes { return false }
            return true
        }
    }
}

final class APIService {
    static let shared = APIService()
    private var baseURL: String { Config.resolvedApiBaseURL }
    private let session: URLSession
    #if DEBUG
    private let tlsSessionDelegate = LocalDevURLSessionDelegate()
    #endif

    private init() {
        let config = URLSessionConfiguration.default
        config.httpCookieStorage = HTTPCookieStorage.shared
        config.httpShouldSetCookies = true
        config.httpCookieAcceptPolicy = .always
        #if DEBUG
        self.session = URLSession(configuration: config, delegate: tlsSessionDelegate, delegateQueue: nil)
        #else
        self.session = URLSession(configuration: config)
        #endif
    }

    /// Call after changing API base URL so session cookies do not target the old host.
    func clearHttpCookies() {
        HTTPCookieStorage.shared.cookies?.forEach { HTTPCookieStorage.shared.deleteCookie($0) }
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

    private func serverErrorMessage(from data: Data, fallback: String) -> String {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let msg = json["error"] as? String,
              !msg.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return fallback
        }
        return msg
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
        let (data, res) = try await request("/api/emergency/alert", method: "POST", body: ["activated": activated])
        if res.statusCode == 401 { throw APIError.unauthorized }
        if res.statusCode != 200 {
            throw APIError.serverError(
                serverErrorMessage(from: data, fallback: "Alert request failed")
            )
        }
    }

    func getEmergencyAlertStatus() async throws -> Bool {
        let (data, res) = try await request("/api/emergency/alert/status")
        if res.statusCode == 401 { throw APIError.unauthorized }
        if res.statusCode != 200 {
            throw APIError.serverError(
                serverErrorMessage(from: data, fallback: "Alert status failed")
            )
        }
        guard
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let dataObj = json["data"] as? [String: Any],
            let active = dataObj["activated"] as? Bool
        else {
            throw APIError.invalidResponse
        }
        return active
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
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let naiveFormats = [
            "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
            "yyyy-MM-dd'T'HH:mm:ss.SSS",
            "yyyy-MM-dd'T'HH:mm:ss"
        ]
        return arr.compactMap { row -> CheckIn? in
            guard let name = row["contact_name"] as? String else { return nil }
            let loc = row["location_name"] as? String
            let lat = row["latitude"] as? Double
            let lon = row["longitude"] as? Double
            let uid = row["user_id"] as? String
            let photoURL = row["photo_url"] as? String
            let tsStr = row["timestamp"] as? String
            let ts: Date
            if let s = tsStr {
                if let parsed = isoFormatter.date(from: s) {
                    ts = parsed
                } else {
                    let formatter = DateFormatter()
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    formatter.timeZone = TimeZone(secondsFromGMT: 0)
                    var parsed: Date?
                    for fmt in naiveFormats {
                        formatter.dateFormat = fmt
                        if let p = formatter.date(from: s) {
                            parsed = p
                            break
                        }
                    }
                    ts = parsed ?? Date.distantPast
                }
            } else {
                ts = Date.distantPast
            }
            return CheckIn(
                contactName: name,
                locationName: (loc?.isEmpty == true) ? nil : loc,
                timestamp: ts,
                latitude: lat,
                longitude: lon,
                userId: uid,
                photoURL: photoURL
            )
        }
    }

    func getTodayEventSummary(familyCircleId: String) async throws -> TodayEventSummary? {
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        dateFormatter.timeZone = TimeZone.current
        let today = dateFormatter.string(from: Date())

        var comp = URLComponents(string: baseURL + "/api/family_circles/\(familyCircleId)/calendar/events")
        comp?.queryItems = [URLQueryItem(name: "date", value: today)]
        guard let u = comp?.url else { throw APIError.invalidResponse }

        var req = URLRequest(url: u)
        req.httpMethod = "GET"
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, res) = try await session.data(for: req)
        guard let http = res as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.serverError("Today events failed")
        }
        guard
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let events = json["data"] as? [[String: Any]],
            let first = events.first
        else {
            return nil
        }

        let title = ((first["display"] as? String) ?? (first["title"] as? String) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if title.isEmpty { return nil }

        var startTimeText: String?
        if let start = first["start_time"] as? String, start.count >= 16 {
            let raw = String(start.dropFirst(11).prefix(5))
            startTimeText = raw
        }
        return TodayEventSummary(title: title, startTimeText: startTimeText)
    }

    func getMedicationHomeSnapshot(familyCircleId: String) async throws -> MedicationHomeSnapshot {
        let path = "/api/family_circles/\(familyCircleId)/medications"
        let (data, res) = try await request(path)
        if res.statusCode == 401 { throw APIError.unauthorized }
        if res.statusCode != 200 {
            throw APIError.serverError(
                serverErrorMessage(from: data, fallback: "Medications failed")
            )
        }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dataObj = json["data"] as? [String: Any] else {
            throw APIError.invalidResponse
        }
        let timedArr = dataObj["timed_medications"] as? [[String: Any]] ?? []
        let prnArr = dataObj["prn_medications"] as? [[String: Any]] ?? []
        let timedParsed: [MedicationHomeSnapshot.TimedRow] = timedArr.compactMap { row in
            guard let name = row["name"] as? String, let slot = row["time"] as? String else { return nil }
            let status = (row["status"] as? String) ?? "not_done"
            let gt = row["group_time"] as? String
            return MedicationHomeSnapshot.TimedRow(
                slot: slot,
                name: name,
                taken: status == "done",
                groupTime: (gt?.isEmpty == false) ? gt : nil
            )
        }
        let timed = Self.sortTimedMedicationRows(timedParsed)
        let prn: [MedicationHomeSnapshot.PrnRow] = prnArr.compactMap { row in
            guard let name = row["name"] as? String else { return nil }
            let doses: Int
            if let d = row["doses_today"] as? Int {
                doses = d
            } else if let n = row["doses_today"] as? NSNumber {
                doses = n.intValue
            } else {
                doses = 0
            }
            let maxDaily: Int?
            if let m = row["max_daily"] as? Int {
                maxDaily = m
            } else if let n = row["max_daily"] as? NSNumber {
                maxDaily = n.intValue
            } else {
                maxDaily = nil
            }
            let last = row["last_taken"] as? String
            return MedicationHomeSnapshot.PrnRow(
                name: name,
                dosesToday: doses,
                maxDaily: maxDaily,
                lastTaken: last
            )
        }
        return MedicationHomeSnapshot(timed: timed, prn: prn)
    }

    static func buildHomeTodayTimeline(
        medicationSnapshot: MedicationHomeSnapshot?,
        appointment: TodayEventSummary?
    ) -> [HomeTodayTimelineEntry] {
        var sortable: [(min: Int, tier: Int, seq: Int, entry: HomeTodayTimelineEntry)] = []
        var seq = 0
        if let snap = medicationSnapshot {
            for t in snap.timed {
                let minVal = medicationRowSortTuple(t).0
                let timeDisp: String
                if let gt = t.groupTime?.trimmingCharacters(in: .whitespacesAndNewlines), !gt.isEmpty {
                    timeDisp = gt
                } else {
                    timeDisp = t.slot
                }
                seq += 1
                let entry = HomeTodayTimelineEntry(
                    timeDisplay: timeDisp,
                    title: t.name,
                    done: t.taken,
                    kind: .medication,
                    sortMinutes: minVal
                )
                sortable.append((minVal, timelineKindTier(.medication), seq, entry))
            }
            for (i, p) in snap.prn.enumerated() {
                var tail = "\(p.dosesToday)"
                if let m = p.maxDaily { tail += "/\(m)" }
                tail += " today"
                if let lt = p.lastTaken?.trimmingCharacters(in: .whitespacesAndNewlines), !lt.isEmpty {
                    tail += " · Last \(lt)"
                }
                seq += 1
                let prnMin = 24 * 60 + 10 + i
                let entry = HomeTodayTimelineEntry(
                    timeDisplay: "As needed",
                    title: "\(p.name) · \(tail)",
                    done: false,
                    kind: .prn,
                    sortMinutes: prnMin
                )
                sortable.append((prnMin, timelineKindTier(.prn), seq, entry))
            }
        }
        if let ap = appointment {
            let tit = ap.title.trimmingCharacters(in: .whitespacesAndNewlines)
            if !tit.isEmpty {
                let minVal: Int
                if let st = ap.startTimeText, let m = minutesSinceMidnight(fromClock: st) {
                    minVal = m
                } else {
                    minVal = 14 * 60
                }
                seq += 1
                let timeDisp: String
                if let st = ap.startTimeText?.trimmingCharacters(in: .whitespacesAndNewlines), !st.isEmpty {
                    timeDisp = st
                } else {
                    timeDisp = "—"
                }
                let entry = HomeTodayTimelineEntry(
                    timeDisplay: timeDisp,
                    title: tit,
                    done: false,
                    kind: .appointment,
                    sortMinutes: minVal
                )
                sortable.append((minVal, timelineKindTier(.appointment), seq, entry))
            }
        }
        sortable.sort {
            if $0.min != $1.min { return $0.min < $1.min }
            if $0.tier != $1.tier { return $0.tier < $1.tier }
            return $0.seq < $1.seq
        }
        return sortable.map { $0.entry }
    }

    private static func timelineKindTier(_ k: HomeTodayTimelineEntry.RowKind) -> Int {
        switch k {
        case .medication: return 0
        case .appointment: return 1
        case .prn: return 2
        }
    }

    private static func sortTimedMedicationRows(_ rows: [MedicationHomeSnapshot.TimedRow]) -> [MedicationHomeSnapshot.TimedRow] {
        rows.sorted { medicationRowSortTuple($0) < medicationRowSortTuple($1) }
    }

    private static func medicationRowSortTuple(_ row: MedicationHomeSnapshot.TimedRow) -> (Int, String) {
        let slotKey = row.slot.lowercased()
        if let gt = row.groupTime?.trimmingCharacters(in: .whitespacesAndNewlines), !gt.isEmpty,
           let mins = minutesSinceMidnight(fromClock: gt) {
            return (mins, row.slot)
        }
        return (slotNameFallbackMinutes(slotKey), row.slot)
    }

    private static func minutesSinceMidnight(fromClock s: String) -> Int? {
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return nil }
        let loc = Locale(identifier: "en_US_POSIX")
        for fmt in ["HH:mm", "H:mm", "h:mm a", "hh:mm a"] {
            let f = DateFormatter()
            f.locale = loc
            f.dateFormat = fmt
            if let d = f.date(from: t) {
                let c = Calendar.current
                return c.component(.hour, from: d) * 60 + c.component(.minute, from: d)
            }
        }
        return nil
    }

    private static func slotNameFallbackMinutes(_ slot: String) -> Int {
        if slot.contains("morning") || slot.contains("breakfast") { return 8 * 60 }
        if slot.contains("noon") || slot.contains("lunch") { return 12 * 60 }
        if slot.contains("afternoon") { return 14 * 60 }
        if slot.contains("evening") || slot.contains("dinner") { return 18 * 60 }
        if slot.contains("bed") || slot.contains("night") { return 21 * 60 }
        return 24 * 60
    }

    // MARK: - Kiosk call

    func getKioskPhoneNumber() async throws -> String {
        return "+14359008919"
    }

    func forceAnswerKiosk() async throws {
        let (data, res) = try await request("/api/calls/force-answer", method: "POST", body: [:])
        if res.statusCode != 201 {
            let hint404 = "404 means this host has no POST /api/calls/force-answer (wrong API URL or old deploy)."
            let fallback = res.statusCode == 404
                ? "Force-answer failed (\(res.statusCode)). \(hint404)"
                : "Force-answer failed (\(res.statusCode))"
            let msg = serverErrorMessage(from: data, fallback: fallback)
            throw APIError.serverError(msg)
        }
    }

    // MARK: - Device token (push)

    func registerDeviceToken(token: String, platform: String = "ios") async throws {
        let (_, res) = try await request("/api/device-token", method: "POST", body: [
            "token": token,
            "platform": platform
        ])
        if res.statusCode != 200 {
            throw APIError.serverError("Device token registration failed")
        }
    }

}
