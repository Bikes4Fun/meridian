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
        applyMeridianScreenDefaults(title: "Meridian")

        let titleLabel = UILabel()
        titleLabel.text = "Meridian"
        titleLabel.font = .systemFont(ofSize: 30, weight: .bold)
        titleLabel.textColor = MeridianPalette.primaryText
        titleLabel.textAlignment = .center

        let subtitleLabel = UILabel()
        subtitleLabel.text = "Family care, connected"
        subtitleLabel.font = .preferredFont(forTextStyle: .subheadline)
        subtitleLabel.textColor = MeridianPalette.mutedText
        subtitleLabel.textAlignment = .center

        let serverFieldLabel = UILabel()
        serverFieldLabel.text = "Server URL"
        serverFieldLabel.font = .preferredFont(forTextStyle: .caption1)
        serverFieldLabel.textColor = MeridianPalette.mutedText

        let userFieldLabel = UILabel()
        userFieldLabel.text = "User ID"
        userFieldLabel.font = .preferredFont(forTextStyle: .caption1)
        userFieldLabel.textColor = MeridianPalette.mutedText

        let familyFieldLabel = UILabel()
        familyFieldLabel.text = "Family Circle ID"
        familyFieldLabel.font = .preferredFont(forTextStyle: .caption1)
        familyFieldLabel.textColor = MeridianPalette.mutedText

        serverUrlField.placeholder = "https://your-api-url"
        serverUrlField.borderStyle = .roundedRect
        serverUrlField.autocapitalizationType = .none
        serverUrlField.autocorrectionType = .no
        serverUrlField.keyboardType = .URL
        serverUrlField.textContentType = .URL
        let persisted = Config.persistedApiBaseURLFieldText()
        serverUrlField.text = persisted.isEmpty ? Config.launchBundledApiBaseURL : persisted

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

        loginButton.applyMeridianButtonStyle(.primary, title: "Log In")
        loginButton.addTarget(self, action: #selector(doLogin), for: .touchUpInside)

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = .secondaryLabel
        statusLabel.font = .preferredFont(forTextStyle: .footnote)

        spinner.hidesWhenStopped = true

        let stack = UIStackView(arrangedSubviews: [
            titleLabel,
            subtitleLabel,
            serverFieldLabel,
            serverUrlField,
            serverDefaultHintLabel,
            userFieldLabel,
            userIdField,
            familyFieldLabel,
            familyCircleField,
            loginButton,
            spinner,
            statusLabel
        ])
        stack.axis = .vertical
        stack.spacing = 12
        stack.alignment = .fill
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.setCustomSpacing(6, after: titleLabel)
        stack.setCustomSpacing(16, after: subtitleLabel)
        stack.setCustomSpacing(6, after: serverFieldLabel)
        stack.setCustomSpacing(6, after: userFieldLabel)
        stack.setCustomSpacing(6, after: familyFieldLabel)

        view.addSubview(stack)
        NSLayoutConstraint.activate([
            serverUrlField.heightAnchor.constraint(equalToConstant: 44),
            userIdField.heightAnchor.constraint(equalToConstant: 44),
            familyCircleField.heightAnchor.constraint(equalToConstant: 44),
            loginButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: MeridianLayout.sectionSpacing),
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.screenPadding),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -MeridianLayout.screenPadding),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -MeridianLayout.sectionSpacing)
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
