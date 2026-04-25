/**
 * Meridian iOS – Root: show Login or Main tabs.
 */
import UIKit

final class RootViewController: UIViewController {
    private let warmBackground = UIColor(red: 0.98, green: 0.97, blue: 0.95, alpha: 1)

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = warmBackground
        overrideUserInterfaceStyle = .light
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(apiBaseURLDidChange),
            name: Config.apiBaseURLDidChangeNotification,
            object: nil
        )
        checkSessionAndShowAppropriateScreen()
    }

    @objc private func apiBaseURLDidChange() {
        showLogin()
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
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
        login.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(login.view)
        NSLayoutConstraint.activate([
            login.view.topAnchor.constraint(equalTo: view.topAnchor),
            login.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            login.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            login.view.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        login.didMove(toParent: self)
    }

    private func showMain() {
        if let _ = children.first as? MainTabViewController { return }
        children.forEach { $0.removeFromParent(); $0.view.removeFromSuperview() }
        let main = MainTabViewController()
        addChild(main)
        main.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(main.view)
        NSLayoutConstraint.activate([
            main.view.topAnchor.constraint(equalTo: view.topAnchor),
            main.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            main.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            main.view.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        main.didMove(toParent: self)
    }
}
