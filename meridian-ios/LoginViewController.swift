/**
 * Meridian iOS – Login screen. Demo auth: user_id + family_circle_id.
 */
import UIKit

final class LoginViewController: UIViewController {
    private let serverUrlField = UITextField()
    private let serverDefaultHintLabel = UILabel()
    private let userIdField = UITextField()
    private let familyCircleField = UITextField()
    private let loginButton = UIButton(type: .system)
    private let statusLabel = UILabel()
    private let spinner = UIActivityIndicatorView(style: .medium)

    var onLoginSuccess: (() -> Void)?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        title = "Meridian"

        serverUrlField.placeholder = "Server URL (e.g. http://192.168.1.10:8000)"
        serverUrlField.borderStyle = .roundedRect
        serverUrlField.autocapitalizationType = .none
        serverUrlField.autocorrectionType = .no
        serverUrlField.keyboardType = .URL
        serverUrlField.textContentType = .URL
        let persisted = Config.persistedApiBaseURLFieldText()
        serverUrlField.text = persisted.isEmpty ? nil : persisted

        serverDefaultHintLabel.numberOfLines = 0
        serverDefaultHintLabel.font = .preferredFont(forTextStyle: .caption1)
        serverDefaultHintLabel.textColor = .secondaryLabel
        serverDefaultHintLabel.text = "Default API: \(Config.launchBundledApiBaseURL)"

        userIdField.placeholder = "User ID (e.g. fm_001)"
        userIdField.borderStyle = .roundedRect
        userIdField.autocapitalizationType = .none
        userIdField.autocorrectionType = .no

        familyCircleField.placeholder = "Family Circle ID (e.g. F00000)"
        familyCircleField.borderStyle = .roundedRect
        familyCircleField.autocapitalizationType = .none
        familyCircleField.autocorrectionType = .no

        // Demo: prefill Deanna's info
        userIdField.text = "fm_002"
        familyCircleField.text = "F00000"

        loginButton.setTitle("Log In", for: .normal)
        loginButton.addTarget(self, action: #selector(doLogin), for: .touchUpInside)

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = .secondaryLabel
        statusLabel.font = .preferredFont(forTextStyle: .footnote)

        spinner.hidesWhenStopped = true

        let stack = UIStackView(arrangedSubviews: [
            serverUrlField, serverDefaultHintLabel, userIdField, familyCircleField, loginButton, spinner, statusLabel
        ])
        stack.axis = .vertical
        stack.spacing = 12
        stack.alignment = .fill
        stack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(stack)
        NSLayoutConstraint.activate([
            serverUrlField.heightAnchor.constraint(equalToConstant: 44),
            userIdField.heightAnchor.constraint(equalToConstant: 44),
            familyCircleField.heightAnchor.constraint(equalToConstant: 44),
            loginButton.heightAnchor.constraint(equalToConstant: 44),
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24)
        ])
    }

    @objc private func doLogin() {
        let uid = userIdField.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let fid = familyCircleField.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !uid.isEmpty, !fid.isEmpty else {
            statusLabel.text = "Enter user ID and family circle ID"
            statusLabel.textColor = .systemRed
            return
        }

        let trimmedServer = serverUrlField.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        Config.saveApiBaseURL(trimmedServer)
        let base = Config.resolvedApiBaseURL
        guard Config.isValidHttpBaseURL(base) else {
            statusLabel.text = "Missing or invalid server URL. Set MERIDIAN_API_URL in Xcode (build) or enter an override above."
            statusLabel.textColor = .systemRed
            return
        }

        loginButton.isEnabled = false
        spinner.startAnimating()
        statusLabel.text = "Logging in…"
        statusLabel.textColor = .secondaryLabel

        Task {
            do {
                try await APIService.shared.login(userId: uid, familyCircleId: fid)
                await MainActor.run {
                    spinner.stopAnimating()
                    loginButton.isEnabled = true
                    statusLabel.text = "Success"
                    statusLabel.textColor = .systemGreen
                    (UIApplication.shared.delegate as? AppDelegate)?.tryRegisterDeviceToken()
                    onLoginSuccess?()
                }
            } catch {
                await MainActor.run {
                    spinner.stopAnimating()
                    loginButton.isEnabled = true
                    statusLabel.text = error.localizedDescription
                    statusLabel.textColor = .systemRed
                }
            }
        }
    }
}
