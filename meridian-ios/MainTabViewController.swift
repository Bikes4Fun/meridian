/**
 * Meridian iOS – Main tab bar: Alert, Check-In, Chat.
 */
import UIKit
import WebKit
import MapKit

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

        let settingsVC = SettingsViewController()
        settingsVC.onOpenDeveloperTools = { [weak self] in
            guard let nav = self?.selectedViewController as? UINavigationController else { return }
            nav.pushViewController(DeveloperViewController(), animated: true)
        }

        viewControllers = [
            wrapped(homeVC, title: "Home", image: UIImage(systemName: "house.fill")),
            wrapped(AlertViewController(), title: "Emergency", image: UIImage(systemName: "exclamationmark.triangle.fill")),
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
    private let scrollView = UIScrollView()
    private let contentStack = UIStackView()
    private let emergencyCard = UIView()
    private let emergencyStatusLabel = UILabel()
    private let checkInCard = UIView()
    private let todaySummaryLabel = UILabel()
    private let mapCard = UIView()
    private let familyMapView = MKMapView()
    private let mapStatusLabel = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = MeridianPalette.background

        configureCard(emergencyCard)
        configureCard(checkInCard)
        configureCard(mapCard)

        emergencyStatusLabel.numberOfLines = 0
        emergencyStatusLabel.font = .preferredFont(forTextStyle: .body)
        emergencyStatusLabel.textColor = MeridianPalette.primaryText
        emergencyStatusLabel.text = "No active emergency alerts."

        todaySummaryLabel.numberOfLines = 0
        todaySummaryLabel.font = .preferredFont(forTextStyle: .body)
        todaySummaryLabel.textColor = MeridianPalette.primaryText
        todaySummaryLabel.text = "No upcoming items today."

        familyMapView.layer.cornerRadius = 10
        familyMapView.layer.masksToBounds = true
        familyMapView.layer.borderWidth = 1
        familyMapView.layer.borderColor = MeridianPalette.border.cgColor
        familyMapView.showsCompass = false
        familyMapView.delegate = self
        familyMapView.translatesAutoresizingMaskIntoConstraints = false

        mapStatusLabel.numberOfLines = 1
        mapStatusLabel.font = .preferredFont(forTextStyle: .footnote)
        mapStatusLabel.textColor = MeridianPalette.mutedText
        mapStatusLabel.text = "No location updates yet."

        contentStack.axis = .vertical
        contentStack.spacing = MeridianLayout.sectionSpacing
        contentStack.translatesAutoresizingMaskIntoConstraints = false

        let emergencyStack = UIStackView(arrangedSubviews: [sectionTitle("Emergency Alerts"), emergencyStatusLabel])
        emergencyStack.axis = .vertical
        emergencyStack.spacing = 8
        emergencyCard.addSubview(emergencyStack)
        emergencyStack.translatesAutoresizingMaskIntoConstraints = false

        let todayStack = UIStackView(arrangedSubviews: [sectionTitle("Today"), todaySummaryLabel])
        todayStack.axis = .vertical
        todayStack.spacing = 8
        checkInCard.addSubview(todayStack)
        todayStack.translatesAutoresizingMaskIntoConstraints = false

        let mapHeader = sectionTitle("Family Map")
        let mapStack = UIStackView(arrangedSubviews: [mapHeader, familyMapView, mapStatusLabel])
        mapStack.axis = .vertical
        mapStack.spacing = 8
        mapCard.addSubview(mapStack)
        mapStack.translatesAutoresizingMaskIntoConstraints = false

        [emergencyStack, todayStack, mapStack].forEach { stack in
            NSLayoutConstraint.activate([
                stack.topAnchor.constraint(equalTo: stack.superview!.topAnchor, constant: MeridianLayout.cardPadding),
                stack.leadingAnchor.constraint(equalTo: stack.superview!.leadingAnchor, constant: MeridianLayout.cardPadding),
                stack.trailingAnchor.constraint(equalTo: stack.superview!.trailingAnchor, constant: -MeridianLayout.cardPadding),
                stack.bottomAnchor.constraint(equalTo: stack.superview!.bottomAnchor, constant: -MeridianLayout.cardPadding)
            ])
        }

        contentStack.addArrangedSubview(emergencyCard)
        contentStack.addArrangedSubview(checkInCard)
        contentStack.addArrangedSubview(mapCard)

        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.contentInsetAdjustmentBehavior = .never
        scrollView.addSubview(contentStack)
        view.addSubview(scrollView)

        NSLayoutConstraint.activate([
            familyMapView.heightAnchor.constraint(equalToConstant: 220),

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

        Task { await refreshHomeData() }
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        navigationController?.setNavigationBarHidden(true, animated: false)
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        navigationController?.setNavigationBarHidden(false, animated: false)
    }

    private func refreshHomeData() async {
        do {
            let s = try await APIService.shared.getSession()

            async let alertActive = APIService.shared.getEmergencyAlertStatus()
            async let today = APIService.shared.getTodayEventSummary(familyCircleId: s.familyCircleId)
            async let checkins = APIService.shared.getCheckins(familyCircleId: s.familyCircleId)

            let isActive = (try? await alertActive) ?? false
            let todaySummaryResult = try? await today
            let todaySummary = todaySummaryResult ?? nil
            let familyCheckins = (try? await checkins) ?? []

            await MainActor.run {
                emergencyStatusLabel.text = isActive ? "Active emergency alert in progress." : "No active emergency alerts."
                emergencyStatusLabel.textColor = isActive ? MeridianPalette.alert : MeridianPalette.primaryText

                if let item = todaySummary {
                    if let start = item.startTimeText, !start.isEmpty {
                        todaySummaryLabel.text = "\(start) • \(item.title)"
                    } else {
                        todaySummaryLabel.text = item.title
                    }
                } else {
                    todaySummaryLabel.text = "No upcoming items today."
                }
                updateHomeMap(with: familyCheckins)
            }
        } catch {
            await MainActor.run {
                emergencyStatusLabel.text = "Could not load emergency alerts."
                emergencyStatusLabel.textColor = MeridianPalette.primaryText
                todaySummaryLabel.text = "Could not load today items."
                mapStatusLabel.text = "Could not load family locations."
            }
        }
    }

    private func updateHomeMap(with checkins: [CheckIn]) {
        familyMapView.removeAnnotations(familyMapView.annotations)
        let validCheckins = checkins.filter { $0.latitude != nil && $0.longitude != nil }
        for checkIn in validCheckins {
            guard let lat = checkIn.latitude, let lon = checkIn.longitude else { continue }
            let annotation = FamilyLocationAnnotation(
                coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                title: checkIn.contactName,
                subtitle: checkIn.locationName ?? "Unknown location",
                photoURLString: checkIn.photoURL
            )
            familyMapView.addAnnotation(annotation)
        }

        if validCheckins.isEmpty {
            mapStatusLabel.text = "No location updates yet."
            return
        }

        mapStatusLabel.text = "Latest update: \(validCheckins.first?.contactName ?? "Family member")"
        if validCheckins.count == 1, let first = validCheckins.first,
           let lat = first.latitude, let lon = first.longitude {
            let center = CLLocationCoordinate2D(latitude: lat, longitude: lon)
            let region = MKCoordinateRegion(center: center, span: MKCoordinateSpan(latitudeDelta: 0.04, longitudeDelta: 0.04))
            familyMapView.setRegion(region, animated: false)
            return
        }
        familyMapView.showAnnotations(familyMapView.annotations, animated: false)
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

}

extension HomeViewController: MKMapViewDelegate {
    func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
        if annotation is MKUserLocation { return nil }
        guard let familyAnnotation = annotation as? FamilyLocationAnnotation else { return nil }
        let identifier = "FamilyLocationAvatar"
        let view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier) as? FamilyLocationAnnotationView
            ?? FamilyLocationAnnotationView(annotation: annotation, reuseIdentifier: identifier)
        view.annotation = annotation
        view.configure(with: familyAnnotation)
        return view
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
        view.backgroundColor = MeridianPalette.background

        contentStack.axis = .vertical
        contentStack.spacing = 12
        contentStack.translatesAutoresizingMaskIntoConstraints = false

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
        navigationController?.setNavigationBarHidden(true, animated: false)
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        navigationController?.setNavigationBarHidden(false, animated: false)
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

final class FamilyLocationAnnotation: NSObject, MKAnnotation {
    let coordinate: CLLocationCoordinate2D
    let title: String?
    let subtitle: String?
    let photoURLString: String?

    init(coordinate: CLLocationCoordinate2D, title: String?, subtitle: String?, photoURLString: String?) {
        self.coordinate = coordinate
        self.title = title
        self.subtitle = subtitle
        self.photoURLString = photoURLString
        super.init()
    }
}

final class FamilyLocationAnnotationView: MKAnnotationView {
    private static let imageCache = NSCache<NSString, UIImage>()
    private let avatarImageView = UIImageView()
    private var currentPhotoURLString: String?

    override init(annotation: MKAnnotation?, reuseIdentifier: String?) {
        super.init(annotation: annotation, reuseIdentifier: reuseIdentifier)
        canShowCallout = true
        centerOffset = CGPoint(x: 0, y: -18)
        frame = CGRect(x: 0, y: 0, width: 44, height: 44)

        avatarImageView.frame = bounds
        avatarImageView.contentMode = .scaleAspectFill
        avatarImageView.clipsToBounds = true
        avatarImageView.layer.cornerRadius = 22
        avatarImageView.layer.borderWidth = 2
        avatarImageView.layer.borderColor = UIColor.white.cgColor
        addSubview(avatarImageView)

        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOpacity = 0.22
        layer.shadowRadius = 4
        layer.shadowOffset = CGSize(width: 0, height: 2)
    }

    required init?(coder: NSCoder) {
        return nil
    }

    override func prepareForReuse() {
        super.prepareForReuse()
        currentPhotoURLString = nil
        avatarImageView.image = nil
    }

    func configure(with annotation: FamilyLocationAnnotation) {
        let fallback = avatarPlaceholderImage(for: annotation.title ?? "?")
        avatarImageView.image = fallback

        guard let urlString = annotation.photoURLString, !urlString.isEmpty else { return }
        currentPhotoURLString = urlString

        if let cached = Self.imageCache.object(forKey: urlString as NSString) {
            avatarImageView.image = cached
            return
        }

        guard let url = URL(string: urlString) else { return }
        let request = URLRequest(url: url, cachePolicy: .returnCacheDataElseLoad, timeoutInterval: 12)
        URLSession.shared.dataTask(with: request) { [weak self] data, _, _ in
            guard let self = self else { return }
            guard self.currentPhotoURLString == urlString else { return }
            guard let data = data, let image = UIImage(data: data) else { return }
            Self.imageCache.setObject(image, forKey: urlString as NSString)
            DispatchQueue.main.async {
                if self.currentPhotoURLString == urlString {
                    self.avatarImageView.image = image
                }
            }
        }.resume()
    }

    private func avatarPlaceholderImage(for name: String) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: CGSize(width: 44, height: 44))
        let initial = String(name.trimmingCharacters(in: .whitespacesAndNewlines).prefix(1)).uppercased()
        return renderer.image { context in
            let rect = CGRect(x: 0, y: 0, width: 44, height: 44)
            MeridianPalette.primaryAction.setFill()
            context.cgContext.fillEllipse(in: rect)
            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 19, weight: .semibold),
                .foregroundColor: UIColor.white
            ]
            let text = initial.isEmpty ? "?" : initial
            let size = text.size(withAttributes: attrs)
            let drawRect = CGRect(x: (44 - size.width) / 2, y: (44 - size.height) / 2, width: size.width, height: size.height)
            text.draw(in: drawRect, withAttributes: attrs)
        }
    }
}
