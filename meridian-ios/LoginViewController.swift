/**
 * Meridian iOS – Login screen. Demo auth: user_id + family_circle_id.
 */
import UIKit

final class LoginViewController: UIViewController {
    private let serverUrlField = UITextField()
    private let serverDefaultHintLabel = UILabel()
    private let serverInputSection = UIStackView()
    private let userIdField = UITextField()
    private let familyCircleField = UITextField()
    private let loginButton = UIButton(type: .system)
    private let statusLabel = UILabel()
    private let spinner = UIActivityIndicatorView(style: .medium)

    /// Avoids running auto backend selection more than once for this screen instance.
    private var didAttemptAutoBackendSelection = false

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
        let persistedTrim = Config.persistedApiBaseURLFieldText().trimmingCharacters(in: .whitespacesAndNewlines)
        if persistedTrim.isEmpty {
            serverUrlField.text = ""
        } else {
            serverUrlField.text = persistedTrim
        }

        serverDefaultHintLabel.numberOfLines = 0
        serverDefaultHintLabel.font = .preferredFont(forTextStyle: .caption1)
        serverDefaultHintLabel.textColor = .secondaryLabel
        serverDefaultHintLabel.text = "Default API: \(Config.launchBundledApiBaseURL)"

        serverInputSection.axis = .vertical
        serverInputSection.spacing = 6
        serverInputSection.isHidden = true
        [serverFieldLabel, serverUrlField, serverDefaultHintLabel].forEach { serverInputSection.addArrangedSubview($0) }

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
            serverInputSection,
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
        stack.setCustomSpacing(6, after: serverInputSection)
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

        statusLabel.text = "Checking Meridian server…"
        loginButton.isEnabled = false
        spinner.startAnimating()
        Task { [weak self] in
            await self?.runAutoBackendSelection(persistedBeforeResolve: persistedTrim)
        }
    }

    private func runAutoBackendSelection(persistedBeforeResolve: String) async {
        guard !didAttemptAutoBackendSelection else { return }
        didAttemptAutoBackendSelection = true

        let beforeNorm = Config.normalizedBaseURL(persistedBeforeResolve)
        let chosen = await Config.resolveBackendBaseURL()
        let ngrokReachable = await Config.checkApiHealth(
            atBaseURL: Config.normalizedBaseURL(Config.demoNgrokApiBaseURL),
            timeout: Config.apiHealthCheckTimeoutSeconds)

        await MainActor.run { [weak self] in
            guard let self else { return }
            spinner.stopAnimating()
            loginButton.isEnabled = true
            if let chosen {
                Config.saveApiBaseURL(chosen)
                serverUrlField.text = chosen
                serverInputSection.isHidden = true
                if Config.isReleasedDemoRailwayURL(chosen), !ngrokReachable {
                    statusLabel.text = "Connected to Meridian. Demo ngrok did not respond; using Railway."
                } else {
                    statusLabel.text = "Connected to Meridian."
                }
                statusLabel.textColor = .secondaryLabel
                print("[Meridian] API base URL (resolved): \(chosen)")
                if Config.normalizedBaseURL(chosen) != beforeNorm {
                    NotificationCenter.default.post(name: Config.apiBaseURLDidChangeNotification, object: nil)
                }
            } else {
                serverInputSection.isHidden = false
                serverUrlField.text = Config.persistedApiBaseURLFieldText()
                serverDefaultHintLabel.text = "Enter your API URL. Demo ngrok and Railway were unreachable."
                statusLabel.text = "Could not reach demo servers. Enter a URL above."
                statusLabel.textColor = .systemOrange
                print("[Meridian] API base URL (resolve failed): ngrok and Railway unreachable; saved URL not verified")
            }
        }
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
                    print("[Meridian] API base URL (after login): \(Config.resolvedApiBaseURL)")
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
