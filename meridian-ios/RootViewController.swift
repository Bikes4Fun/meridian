/**
 * Meridian iOS – Root: show Login or Main tabs.
 */
import UIKit

final class RootViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        checkSessionAndShowAppropriateScreen()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        checkSessionAndShowAppropriateScreen()
    }

    private func checkSessionAndShowAppropriateScreen() {
        if children.isEmpty { showLogin() }
        Task {
            do {
                _ = try await APIService.shared.getSession()
                await MainActor.run {
                    showMain()
                    PendingLocationRequestPrompt.presentIfNeeded(window: (UIApplication.shared.delegate as? AppDelegate)?.window)
                }
            } catch {
                await MainActor.run { showLogin() }
            }
        }
    }

    private func showLogin() {
        if let _ = children.first as? LoginViewController { return }
        children.forEach { $0.removeFromParent(); $0.view.removeFromSuperview() }
        let login = LoginViewController()
        login.onLoginSuccess = { [weak self] in
            self?.showMain()
            PendingLocationRequestPrompt.presentIfNeeded(window: (UIApplication.shared.delegate as? AppDelegate)?.window)
        }
        addChild(login)
        view.addSubview(login.view)
        login.view.frame = view.bounds
        login.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        login.didMove(toParent: self)
    }

    private func showMain() {
        if let _ = children.first as? MainTabViewController { return }
        children.forEach { $0.removeFromParent(); $0.view.removeFromSuperview() }
        let main = MainTabViewController()
        addChild(main)
        view.addSubview(main.view)
        main.view.frame = view.bounds
        main.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        main.didMove(toParent: self)
    }
}
