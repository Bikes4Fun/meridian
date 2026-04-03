/**
 * Meridian iOS – Temporary: change API base URL without rebuilding (same Wi-Fi / LAN server).
 */
import UIKit

final class DeveloperViewController: UIViewController {
    private let urlField = UITextField()
    private let effectiveLabel = UILabel()
    private let bundledLabel = UILabel()
    private let statusLabel = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()
        applyMeridianScreenDefaults(title: "Developer")

        urlField.placeholder = "API base URL (e.g. http://192.168.1.10:8000)"
        urlField.borderStyle = .roundedRect
        urlField.autocapitalizationType = .none
        urlField.autocorrectionType = .no
        urlField.keyboardType = .URL
        urlField.textContentType = .URL

        effectiveLabel.numberOfLines = 0
        effectiveLabel.font = .preferredFont(forTextStyle: .subheadline)
        effectiveLabel.textColor = .secondaryLabel

        bundledLabel.numberOfLines = 0
        bundledLabel.font = .preferredFont(forTextStyle: .caption1)
        bundledLabel.textColor = .tertiaryLabel

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.font = .preferredFont(forTextStyle: .footnote)

        let saveButton = UIButton(type: .system)
        saveButton.applyMeridianButtonStyle(.primary, title: "Save & return to login")
        saveButton.addTarget(self, action: #selector(saveTapped), for: .touchUpInside)

        let clearButton = UIButton(type: .system)
        clearButton.applyMeridianButtonStyle(.bordered, title: "Use build default only")
        clearButton.addTarget(self, action: #selector(clearTapped), for: .touchUpInside)

        let stack = UIStackView(arrangedSubviews: [
            urlField, effectiveLabel, bundledLabel, saveButton, clearButton, statusLabel
        ])
        stack.axis = .vertical
        stack.spacing = 12
        stack.alignment = .fill
        stack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(stack)
        NSLayoutConstraint.activate([
            urlField.heightAnchor.constraint(equalToConstant: 44),
            saveButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            clearButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.screenPadding),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -MeridianLayout.screenPadding),
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16)
        ])
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        urlField.text = Config.resolvedApiBaseURL
        refreshLabels()
    }

    private func refreshLabels() {
        effectiveLabel.text = "Effective now: \(Config.resolvedApiBaseURL)"
        bundledLabel.text = "Build default (Info.plist MERIDIAN_API_URL): \(Config.launchBundledApiBaseURL)"
    }

    @objc private func saveTapped() {
        Config.saveApiBaseURL(urlField.text ?? "")
        APIService.shared.clearHttpCookies()
        refreshLabels()
        statusLabel.text = "Saved. Returning to login…"
        statusLabel.textColor = .secondaryLabel
        NotificationCenter.default.post(name: Config.apiBaseURLDidChangeNotification, object: nil)
    }

    @objc private func clearTapped() {
        Config.saveApiBaseURL("")
        urlField.text = Config.resolvedApiBaseURL
        APIService.shared.clearHttpCookies()
        refreshLabels()
        statusLabel.text = "Cleared override. Using build default."
        statusLabel.textColor = .secondaryLabel
        NotificationCenter.default.post(name: Config.apiBaseURLDidChangeNotification, object: nil)
    }
}
