/**
 * Meridian iOS – Login screen. Demo auth: user_id + family_circle_id.
 */
import UIKit

final class LoginViewController: UIViewController {
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
            userIdField, familyCircleField, loginButton, spinner, statusLabel
        ])
        stack.axis = .vertical
        stack.spacing = 12
        stack.alignment = .fill
        stack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(stack)
        NSLayoutConstraint.activate([
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
