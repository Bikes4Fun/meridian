/**
 * Meridian iOS – Handle "Where is everyone?" push. Request location and POST check-in.
 */
import Foundation
import CoreLocation

final class LocationRefreshHandler: NSObject {
    static let shared = LocationRefreshHandler()
    private let locationManager = CLLocationManager()
    private var pendingFamilyCircleId: String?
    private var pendingSession: SessionInfo?

    override init() {
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
    }

    /// Called when push with meridian_action: "location_refresh_requested" is received/tapped.
    func handleLocationRefreshRequest(familyCircleId: String) {
        Task {
            do {
                let session = try await APIService.shared.getSession()
                await MainActor.run {
                    switch locationManager.authorizationStatus {
                    case .authorizedWhenInUse, .authorizedAlways:
                        startLocationRequest(familyCircleId: familyCircleId, session: session)
                    default:
                        requestLocationPermissionAndRetry(familyCircleId: familyCircleId, session: session)
                    }
                }
            } catch {
                // Session invalid (e.g. logged out) – cannot check in
                return
            }
        }
    }

    private func requestLocationPermissionAndRetry(familyCircleId: String, session: SessionInfo) {
        switch locationManager.authorizationStatus {
        case .notDetermined:
            pendingFamilyCircleId = familyCircleId
            pendingSession = session
            locationManager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            pendingFamilyCircleId = nil
            pendingSession = nil
        @unknown default:
            pendingFamilyCircleId = nil
            pendingSession = nil
        }
    }

    private func startLocationRequest(familyCircleId: String, session: SessionInfo) {
        pendingFamilyCircleId = familyCircleId
        pendingSession = session
        locationManager.requestLocation()
    }
}

extension LocationRefreshHandler: CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard let fcId = pendingFamilyCircleId, let s = pendingSession else { return }
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            manager.requestLocation()
        default:
            pendingFamilyCircleId = nil
            pendingSession = nil
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last, let fcId = pendingFamilyCircleId, let s = pendingSession else { return }
        pendingFamilyCircleId = nil
        pendingSession = nil

        Task {
            do {
                try await APIService.shared.checkIn(
                    familyCircleId: fcId,
                    userId: s.userId,
                    latitude: loc.coordinate.latitude,
                    longitude: loc.coordinate.longitude,
                    notes: "Push request"
                )
            } catch {
                // Silent fail – user can manually check in if needed
            }
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        pendingFamilyCircleId = nil
        pendingSession = nil
    }
}
