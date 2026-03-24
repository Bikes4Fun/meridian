/**
 * Meridian iOS – App entry point. Registers for push, uploads device token, handles location-refresh pushes.
 */
import UIKit
import UserNotifications

@main
final class AppDelegate: UIResponder, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = RootViewController()
        window?.makeKeyAndVisible()

        UNUserNotificationCenter.current().delegate = self
        requestNotificationPermission { _ in
            application.registerForRemoteNotifications()
        }
        return true
    }

    private var deviceToken: String?

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        self.deviceToken = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        tryRegisterDeviceToken()
    }

    /// Call after login success so token is registered when it arrived before session existed.
    func tryRegisterDeviceToken() {
        guard let token = deviceToken else { return }
        Task {
            do {
                _ = try await APIService.shared.getSession()
                try await APIService.shared.registerDeviceToken(token: token, platform: "ios")
            } catch {
                // Not logged in – will retry after next login
            }
        }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        // Simulator or missing entitlements – expected in dev
    }

    private func requestNotificationPermission(completion: @escaping (Bool) -> Void) {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, _ in
            DispatchQueue.main.async { completion(granted) }
        }
    }
}

extension AppDelegate {
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .badge])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        let userInfo = response.notification.request.content.userInfo
        if let action = userInfo["meridian_action"] as? String, action == "location_refresh_requested",
           let familyCircleId = userInfo["family_circle_id"] as? String {
            LocationRefreshHandler.shared.handleLocationRefreshRequest(familyCircleId: familyCircleId)
        }
        completionHandler()
    }
}
