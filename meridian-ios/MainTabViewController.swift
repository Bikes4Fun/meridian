/**
 * Meridian iOS – Main tab bar: Alert, Check-In, Chat.
 */
import UIKit
import WebKit

final class MainTabViewController: UITabBarController {
    private enum TabIndex: Int {
        case home = 0
        case alerts = 1
        case checkIn = 2
        case calls = 3
        case settings = 4
    }

    private var callWarmupWebView: WKWebView?
    private var hasStartedCallWarmup = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = MeridianPalette.background
        tabBar.tintColor = MeridianPalette.primaryAction
        tabBar.unselectedItemTintColor = MeridianPalette.mutedText
        tabBar.backgroundColor = .white

        let homeVC = HomeViewController()
        homeVC.onOpenAlerts = { [weak self] in self?.selectedIndex = TabIndex.alerts.rawValue }
        homeVC.onOpenCheckIn = { [weak self] in self?.selectedIndex = TabIndex.checkIn.rawValue }
        homeVC.onOpenCalls = { [weak self] in self?.selectedIndex = TabIndex.calls.rawValue }
        homeVC.onOpenSettings = { [weak self] in self?.selectedIndex = TabIndex.settings.rawValue }

        let settingsVC = SettingsViewController()
        settingsVC.onOpenDeveloperTools = { [weak self] in
            guard let nav = self?.selectedViewController as? UINavigationController else { return }
            nav.pushViewController(DeveloperViewController(), animated: true)
        }

        viewControllers = [
            wrapped(homeVC, title: "Home", image: UIImage(systemName: "house.fill")),
            wrapped(AlertViewController(), title: "Alert", image: UIImage(systemName: "exclamationmark.triangle.fill")),
            wrapped(CheckInViewController(), title: "Check-In", image: UIImage(systemName: "location.fill")),
            wrapped(ChatListViewController(), title: "Calls", image: UIImage(systemName: "video.fill")),
            wrapped(settingsVC, title: "Settings", image: UIImage(systemName: "gearshape.fill"))
        ]
        selectedIndex = TabIndex.home.rawValue
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        if let nav = selectedViewController as? UINavigationController {
            nav.navigationBar.prefersLargeTitles = false
        }
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        startCallWarmupIfNeeded()
    }

    private func wrapped(_ vc: UIViewController, title: String, image: UIImage?) -> UIViewController {
        vc.tabBarItem = UITabBarItem(title: title, image: image, tag: 0)
        return UINavigationController(rootViewController: vc)
    }

    private func startCallWarmupIfNeeded() {
        if hasStartedCallWarmup { return }
        hasStartedCallWarmup = true
        Task {
            do {
                let recipient = try await APIService.shared.getDefaultChatRecipient()
                let url = try await APIService.shared.getChatSessionURL(
                    recipientSendbirdUserId: recipient.sendbirdUserId,
                    recipientDisplayName: recipient.displayName
                )
                await MainActor.run {
                    let webView = WKWebView(frame: CGRect(x: -1000, y: -1000, width: 1, height: 1))
                    webView.isOpaque = false
                    webView.backgroundColor = .clear
                    view.addSubview(webView)
                    webView.load(URLRequest(url: url))
                    callWarmupWebView = webView
                }
            } catch {
                await MainActor.run {
                    hasStartedCallWarmup = false
                }
            }
        }
    }
}

final class HomeViewController: UIViewController {
    var onOpenAlerts: (() -> Void)?
    var onOpenCheckIn: (() -> Void)?
    var onOpenCalls: (() -> Void)?
    var onOpenSettings: (() -> Void)?

    private let scrollView = UIScrollView()
    private let contentStack = UIStackView()
    private let subheadingLabel = UILabel()
    private let emergencyCard = UIView()
    private let emergencyButton = UIButton(type: .system)
    private let forceAnswerButton = UIButton(type: .system)
    private let checkInCard = UIView()
    private let manualCheckInButton = UIButton(type: .system)
    private let callsCard = UIView()
    private let openCallsButton = UIButton(type: .system)
    private let settingsButton = UIButton(type: .system)

    override func viewDidLoad() {
        super.viewDidLoad()
        applyMeridianScreenDefaults(title: "Home")

        subheadingLabel.text = "Notifications, today tasks, and family map."
        subheadingLabel.font = .preferredFont(forTextStyle: .callout)
        subheadingLabel.textColor = MeridianPalette.mutedText
        subheadingLabel.numberOfLines = 0

        configureCard(emergencyCard)
        configureCard(checkInCard)
        configureCard(callsCard)

        emergencyButton.applyMeridianButtonStyle(.primary, title: "Open Alerts & Notifications")
        emergencyButton.addTarget(self, action: #selector(openAlerts), for: .touchUpInside)

        forceAnswerButton.applyMeridianButtonStyle(.secondary, title: "Open Emergency Console")
        forceAnswerButton.addTarget(self, action: #selector(openAlerts), for: .touchUpInside)

        manualCheckInButton.applyMeridianButtonStyle(.primary, title: "Today: meds & appointments")
        manualCheckInButton.addTarget(self, action: #selector(openCheckIn), for: .touchUpInside)

        openCallsButton.applyMeridianButtonStyle(.primary, title: "Open Family Map")
        openCallsButton.addTarget(self, action: #selector(openCheckIn), for: .touchUpInside)

        settingsButton.applyMeridianButtonStyle(.secondary, title: "Open Settings")
        settingsButton.addTarget(self, action: #selector(openSettings), for: .touchUpInside)

        contentStack.axis = .vertical
        contentStack.spacing = MeridianLayout.sectionSpacing
        contentStack.translatesAutoresizingMaskIntoConstraints = false

        let emergencyStack = UIStackView(arrangedSubviews: [sectionTitle("Notifications"), emergencyButton, forceAnswerButton])
        emergencyStack.axis = .vertical
        emergencyStack.spacing = 10
        emergencyCard.addSubview(emergencyStack)
        emergencyStack.translatesAutoresizingMaskIntoConstraints = false

        let checkInStack = UIStackView(arrangedSubviews: [sectionTitle("Today"), manualCheckInButton])
        checkInStack.axis = .vertical
        checkInStack.spacing = 10
        checkInCard.addSubview(checkInStack)
        checkInStack.translatesAutoresizingMaskIntoConstraints = false

        let callsStack = UIStackView(arrangedSubviews: [sectionTitle("Family Map"), openCallsButton, settingsButton])
        callsStack.axis = .vertical
        callsStack.spacing = 10
        callsCard.addSubview(callsStack)
        callsStack.translatesAutoresizingMaskIntoConstraints = false

        [emergencyStack, checkInStack, callsStack].forEach { stack in
            NSLayoutConstraint.activate([
                stack.topAnchor.constraint(equalTo: stack.superview!.topAnchor, constant: MeridianLayout.cardPadding),
                stack.leadingAnchor.constraint(equalTo: stack.superview!.leadingAnchor, constant: MeridianLayout.cardPadding),
                stack.trailingAnchor.constraint(equalTo: stack.superview!.trailingAnchor, constant: -MeridianLayout.cardPadding),
                stack.bottomAnchor.constraint(equalTo: stack.superview!.bottomAnchor, constant: -MeridianLayout.cardPadding)
            ])
        }

        contentStack.addArrangedSubview(subheadingLabel)
        contentStack.addArrangedSubview(emergencyCard)
        contentStack.addArrangedSubview(checkInCard)
        contentStack.addArrangedSubview(callsCard)

        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.contentInsetAdjustmentBehavior = .never
        scrollView.addSubview(contentStack)
        view.addSubview(scrollView)

        NSLayoutConstraint.activate([
            emergencyButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            forceAnswerButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            manualCheckInButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            openCallsButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            settingsButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),

            scrollView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            contentStack.topAnchor.constraint(equalTo: scrollView.contentLayoutGuide.topAnchor, constant: 0),
            contentStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.screenPadding),
            contentStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -MeridianLayout.screenPadding),
            contentStack.bottomAnchor.constraint(equalTo: scrollView.contentLayoutGuide.bottomAnchor, constant: -MeridianLayout.sectionSpacing),
            contentStack.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor, constant: -(MeridianLayout.screenPadding * 2))
        ])
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        enforceMeridianCompactNavigationBar()
    }

    private func configureCard(_ card: UIView) {
        card.backgroundColor = MeridianPalette.surface
        card.layer.cornerRadius = 12
        card.layer.borderWidth = 1
        card.layer.borderColor = MeridianPalette.border.cgColor
    }

    private func sectionTitle(_ text: String) -> UILabel {
        let label = UILabel()
        label.text = text
        label.font = .preferredFont(forTextStyle: .subheadline)
        label.textColor = MeridianPalette.primaryText
        return label
    }

    @objc private func openAlerts() {
        onOpenAlerts?()
    }

    @objc private func openCheckIn() {
        onOpenCheckIn?()
    }

    @objc private func openCalls() {
        onOpenCalls?()
    }

    @objc private func openSettings() {
        onOpenSettings?()
    }
}

final class SettingsViewController: UIViewController {
    var onOpenDeveloperTools: (() -> Void)?

    private let scrollView = UIScrollView()
    private let contentStack = UIStackView()
    private let accountButton = UIButton(type: .system)
    private let notificationButton = UIButton(type: .system)
    private let sensorConfigurationButton = UIButton(type: .system)
    private let appearanceButton = UIButton(type: .system)
    private let developerToolsButton = UIButton(type: .system)

    override func viewDidLoad() {
        super.viewDidLoad()
        applyMeridianScreenDefaults(title: "Settings")

        contentStack.axis = .vertical
        contentStack.spacing = 12
        contentStack.translatesAutoresizingMaskIntoConstraints = false

        let header = UILabel()
        header.text = "App Settings"
        header.font = .preferredFont(forTextStyle: .title3)
        header.textColor = MeridianPalette.primaryText
        contentStack.addArrangedSubview(header)

        configureListButton(accountButton, title: "Family Profile & Permissions")
        configureListButton(notificationButton, title: "Notification Preferences")
        configureListButton(sensorConfigurationButton, title: "Sensor Configuration")
        configureListButton(appearanceButton, title: "Display & Accessibility")
        configureListButton(developerToolsButton, title: "Developer Tools")
        developerToolsButton.addTarget(self, action: #selector(openDeveloperTools), for: .touchUpInside)

        [accountButton, notificationButton, sensorConfigurationButton, appearanceButton, developerToolsButton].forEach {
            contentStack.addArrangedSubview($0)
        }

        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.addSubview(contentStack)
        view.addSubview(scrollView)

        NSLayoutConstraint.activate([
            accountButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            notificationButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            sensorConfigurationButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            appearanceButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            developerToolsButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),

            scrollView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            contentStack.topAnchor.constraint(equalTo: scrollView.contentLayoutGuide.topAnchor, constant: 12),
            contentStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 16),
            contentStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -16),
            contentStack.bottomAnchor.constraint(equalTo: scrollView.contentLayoutGuide.bottomAnchor, constant: -12),
            contentStack.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor, constant: -32)
        ])
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        enforceMeridianCompactNavigationBar()
    }

    private func configureListButton(_ button: UIButton, title: String) {
        button.applyMeridianButtonStyle(.bordered, title: title)
        button.contentHorizontalAlignment = .leading
        button.layer.borderColor = MeridianPalette.border.cgColor
        button.layer.borderWidth = 1
    }

    @objc private func openDeveloperTools() {
        onOpenDeveloperTools?()
    }
}

enum MeridianPalette {
    static let background = UIColor(hex: "#F7F9FA")
    static let surface = UIColor(hex: "#FFFFFF")
    static let primaryText = UIColor(hex: "#2C3E50")
    static let mutedText = UIColor(hex: "#5E6B78")
    static let primaryAction = UIColor(hex: "#2E7D9B")
    static let border = UIColor(hex: "#D8E0E8")
    static let alert = UIColor(hex: "#E67E73")
}

enum MeridianLayout {
    static let screenPadding: CGFloat = 16
    static let cardPadding: CGFloat = 8
    static let sectionSpacing: CGFloat = 10
    static let buttonHeight: CGFloat = 44
    static let buttonInsets = NSDirectionalEdgeInsets(top: 6, leading: 12, bottom: 6, trailing: 12)
}

enum MeridianButtonStyle {
    case primary
    case secondary
    case bordered
    case alert
}

extension UIButton {
    func applyMeridianButtonStyle(_ style: MeridianButtonStyle, title: String) {
        switch style {
        case .primary:
            configuration = .filled()
            configuration?.baseBackgroundColor = MeridianPalette.primaryAction
            configuration?.baseForegroundColor = .white
        case .secondary:
            configuration = .tinted()
            configuration?.baseBackgroundColor = MeridianPalette.surface
            configuration?.baseForegroundColor = MeridianPalette.primaryAction
        case .bordered:
            configuration = .bordered()
            configuration?.baseBackgroundColor = MeridianPalette.surface
            configuration?.baseForegroundColor = MeridianPalette.primaryAction
        case .alert:
            configuration = .filled()
            configuration?.baseBackgroundColor = MeridianPalette.alert
            configuration?.baseForegroundColor = .white
        }
        configuration?.title = title
        configuration?.cornerStyle = .medium
        configuration?.contentInsets = MeridianLayout.buttonInsets
        titleLabel?.font = .preferredFont(forTextStyle: .body)
    }
}

extension UIViewController {
    func applyMeridianScreenDefaults(title: String) {
        view.backgroundColor = MeridianPalette.background
        self.title = title
        enforceMeridianCompactNavigationBar()
    }

    func enforceMeridianCompactNavigationBar() {
        navigationItem.largeTitleDisplayMode = .never
        navigationController?.navigationBar.prefersLargeTitles = false
    }
}

private extension UIColor {
    convenience init(hex: String) {
        let cleaned = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: cleaned).scanHexInt64(&int)
        let r = CGFloat((int >> 16) & 0xFF) / 255
        let g = CGFloat((int >> 8) & 0xFF) / 255
        let b = CGFloat(int & 0xFF) / 255
        self.init(red: r, green: g, blue: b, alpha: 1.0)
    }
}
