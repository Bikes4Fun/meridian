/**
 * Meridian iOS – Main tab bar: Alert, Check-In, Chat.
 */
import UIKit

final class MainTabViewController: UITabBarController {
    override func viewDidLoad() {
        super.viewDidLoad()
        viewControllers = [
            wrapped(AlertViewController(), title: "Alert", image: UIImage(systemName: "exclamationmark.triangle.fill")),
            wrapped(CheckInViewController(), title: "Check-In", image: UIImage(systemName: "location.fill")),
            wrapped(ChatListViewController(), title: "Chat", image: UIImage(systemName: "message.fill")),
            wrapped(DeveloperViewController(), title: "Developer", image: UIImage(systemName: "hammer.fill"))
        ]
    }

    private func wrapped(_ vc: UIViewController, title: String, image: UIImage?) -> UIViewController {
        vc.tabBarItem = UITabBarItem(title: title, image: image, tag: 0)
        return UINavigationController(rootViewController: vc)
    }
}
