/**
 * Meridian iOS – On next app open, remind the user that family requested their location (set when a location-refresh push is shown in foreground via willPresent).
 */
import UIKit

enum PendingLocationRequestPrompt {
    private static let defaultsKey = "pendingLocationRequestFamilyCircleId"

    /// Call from `willPresent` only. Records pending reminder; tap flow uses `didReceive` and does not duplicate this.
    static func recordIfLocationRefreshForeground(userInfo: [AnyHashable: Any]) {
        guard let action = userInfo["meridian_action"] as? String, action == "location_refresh_requested",
              let id = userInfo["family_circle_id"] as? String, !id.isEmpty else { return }
        UserDefaults.standard.set(id, forKey: defaultsKey)
    }

    private static func clearPending() {
        UserDefaults.standard.removeObject(forKey: defaultsKey)
    }

    private static var pendingFamilyCircleId: String? {
        UserDefaults.standard.string(forKey: defaultsKey)
    }

    static func presentIfNeeded(window: UIWindow?) {
        guard let id = pendingFamilyCircleId else { return }
        guard let root = window?.rootViewController else { return }
        Task {
            do {
                _ = try await APIService.shared.getSession()
            } catch {
                return
            }
            await MainActor.run {
                let host = topPresenter(from: root)
                guard host.presentedViewController == nil else { return }
                let alert = UIAlertController(
                    title: "Location requested",
                    message: "Your family asked for your location. You can send your current location now or dismiss this reminder.",
                    preferredStyle: .alert
                )
                alert.addAction(UIAlertAction(title: "Send", style: .default) { _ in
                    clearPending()
                    LocationRefreshHandler.shared.handleLocationRefreshRequest(familyCircleId: id)
                })
                alert.addAction(UIAlertAction(title: "Dismiss", style: .cancel) { _ in
                    clearPending()
                })
                host.present(alert, animated: true)
            }
        }
    }

    private static func topPresenter(from root: UIViewController) -> UIViewController {
        if let presented = root.presentedViewController {
            return topPresenter(from: presented)
        }
        return root
    }
}
