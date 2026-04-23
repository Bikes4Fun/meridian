/**
 * Meridian iOS – Main tab bar: Home, Emergency, Check-In, Settings.
 */
import UIKit
import MapKit

final class MainTabViewController: UITabBarController {
    private let warmBackground = UIColor(red: 0.98, green: 0.97, blue: 0.95, alpha: 1)

    private enum TabIndex: Int {
        case home = 0
        case alerts = 1
        case checkIn = 2
        case settings = 3
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = warmBackground
        overrideUserInterfaceStyle = .light
        tabBar.tintColor = MeridianPalette.primaryAction
        tabBar.unselectedItemTintColor = MeridianPalette.mutedText
        tabBar.backgroundColor = .white
        tabBar.isTranslucent = false
        let tabAppearance = UITabBarAppearance()
        tabAppearance.configureWithOpaqueBackground()
        tabAppearance.backgroundColor = .white
        tabBar.standardAppearance = tabAppearance
        if #available(iOS 15.0, *) {
            tabBar.scrollEdgeAppearance = tabAppearance
        }

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

    private func wrapped(_ vc: UIViewController, title: String, image: UIImage?) -> UIViewController {
        vc.tabBarItem = UITabBarItem(title: title, image: image, tag: 0)
        let nav = UINavigationController(rootViewController: vc)
        nav.view.backgroundColor = warmBackground
        return nav
    }
}

final class HomeViewController: UIViewController {
    private let scrollView = UIScrollView()
    private let contentStack = UIStackView()
    private let serverPromptCard = UIView()
    private let serverPromptTitleLabel = UILabel()
    private let serverPromptExplainLabel = UILabel()
    private let serverUrlFieldHome = UITextField()
    private let saveServerButton = UIButton(type: .system)
    private let serverPromptStatusLabel = UILabel()
    private let emergencyCard = UIView()
    private let emergencyStatusLabel = UILabel()
    private let scheduleCard = UIView()
    private let scheduleHeroDateLabel = UILabel()
    private let upNextContainer = UIView()
    private let upNextKickerLabel = UILabel()
    private let upNextIconView = UIImageView()
    private let upNextTitleLabel = UILabel()
    private let upNextMetaLabel = UILabel()
    private let scheduleHeadingLabel = UILabel()
    private let timelineStack = UIStackView()
    private let scheduleFootnoteLabel = UILabel()
    private let checkInsCard = UIView()
    private let recentCheckInsLabel = UILabel()

    private var hasCompletedHomeRefresh = false

    private static let homeRecentTimeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .short
        f.timeStyle = .short
        return f
    }()

    private static let scheduleHeroDateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "EEEE, MMMM d, yyyy"
        f.locale = Locale.current
        return f
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = MeridianPalette.background

        configureCard(serverPromptCard)
        configureCard(emergencyCard)
        configureCard(scheduleCard)
        configureCard(checkInsCard)
        scheduleCard.backgroundColor = MeridianPalette.surfaceSchedule

        upNextContainer.backgroundColor = MeridianPalette.upNextFill
        upNextContainer.layer.cornerRadius = 10
        upNextContainer.layer.borderWidth = 1
        upNextContainer.layer.borderColor = MeridianPalette.upNextBorder.cgColor

        upNextKickerLabel.text = "Up next"
        upNextKickerLabel.font = .preferredFont(forTextStyle: .subheadline)
        upNextKickerLabel.textColor = MeridianPalette.mutedText

        upNextIconView.translatesAutoresizingMaskIntoConstraints = false
        upNextIconView.contentMode = .scaleAspectFit
        upNextIconView.preferredSymbolConfiguration = UIImage.SymbolConfiguration(pointSize: 34, weight: .semibold)
        upNextIconView.tintColor = MeridianPalette.primaryAction
        upNextIconView.setContentHuggingPriority(.required, for: .horizontal)

        let upNextTitleDesc = UIFontDescriptor.preferredFontDescriptor(withTextStyle: .title1)
        upNextTitleLabel.font = UIFont(
            descriptor: upNextTitleDesc.withSymbolicTraits(.traitBold) ?? upNextTitleDesc,
            size: 0
        )
        upNextTitleLabel.textColor = MeridianPalette.primaryText
        upNextTitleLabel.numberOfLines = 0
        upNextTitleLabel.adjustsFontForContentSizeCategory = true

        upNextMetaLabel.font = .preferredFont(forTextStyle: .subheadline)
        upNextMetaLabel.textColor = MeridianPalette.mutedText
        upNextMetaLabel.numberOfLines = 0

        let upNextTitleRow = UIStackView(arrangedSubviews: [upNextIconView, upNextTitleLabel])
        upNextTitleRow.axis = .horizontal
        upNextTitleRow.alignment = .center
        upNextTitleRow.spacing = 10

        let upNextInner = UIStackView(arrangedSubviews: [upNextKickerLabel, upNextTitleRow, upNextMetaLabel])
        upNextInner.axis = .vertical
        upNextInner.spacing = 6
        upNextInner.translatesAutoresizingMaskIntoConstraints = false
        upNextContainer.addSubview(upNextInner)
        NSLayoutConstraint.activate([
            upNextInner.topAnchor.constraint(equalTo: upNextContainer.topAnchor, constant: 12),
            upNextInner.leadingAnchor.constraint(equalTo: upNextContainer.leadingAnchor, constant: 12),
            upNextInner.trailingAnchor.constraint(equalTo: upNextContainer.trailingAnchor, constant: -12),
            upNextInner.bottomAnchor.constraint(equalTo: upNextContainer.bottomAnchor, constant: -12),
            upNextIconView.widthAnchor.constraint(equalToConstant: 40),
            upNextIconView.heightAnchor.constraint(equalToConstant: 40)
        ])

        serverPromptTitleLabel.text = "Server URL"
        serverPromptTitleLabel.font = .preferredFont(forTextStyle: .subheadline)
        serverPromptTitleLabel.textColor = MeridianPalette.primaryText

        serverPromptExplainLabel.numberOfLines = 0
        serverPromptExplainLabel.font = .preferredFont(forTextStyle: .footnote)
        serverPromptExplainLabel.textColor = MeridianPalette.mutedText
        serverPromptExplainLabel.text = "If the app cannot reach the Meridian API, enter your base URL (https://…), then save. Demo ngrok and Railway are tried automatically when nothing is saved."

        serverUrlFieldHome.placeholder = "https://your-api-url"
        serverUrlFieldHome.borderStyle = .roundedRect
        serverUrlFieldHome.autocapitalizationType = .none
        serverUrlFieldHome.autocorrectionType = .no
        serverUrlFieldHome.keyboardType = .URL
        serverUrlFieldHome.textContentType = .URL
        serverUrlFieldHome.font = .preferredFont(forTextStyle: .body)

        saveServerButton.applyMeridianButtonStyle(.primary, title: "Save & retry")
        saveServerButton.addTarget(self, action: #selector(saveServerUrlTapped), for: .touchUpInside)

        serverPromptStatusLabel.numberOfLines = 0
        serverPromptStatusLabel.font = .preferredFont(forTextStyle: .caption1)
        serverPromptStatusLabel.textColor = .secondaryLabel
        serverPromptStatusLabel.textAlignment = .center

        let serverPromptInner = UIStackView(arrangedSubviews: [
            serverPromptTitleLabel,
            serverPromptExplainLabel,
            serverUrlFieldHome,
            saveServerButton,
            serverPromptStatusLabel
        ])
        serverPromptInner.axis = .vertical
        serverPromptInner.spacing = 10
        serverPromptInner.translatesAutoresizingMaskIntoConstraints = false
        serverPromptCard.addSubview(serverPromptInner)
        NSLayoutConstraint.activate([
            serverPromptInner.topAnchor.constraint(equalTo: serverPromptCard.topAnchor, constant: MeridianLayout.cardPadding),
            serverPromptInner.leadingAnchor.constraint(equalTo: serverPromptCard.leadingAnchor, constant: MeridianLayout.cardPadding),
            serverPromptInner.trailingAnchor.constraint(equalTo: serverPromptCard.trailingAnchor, constant: -MeridianLayout.cardPadding),
            serverPromptInner.bottomAnchor.constraint(equalTo: serverPromptCard.bottomAnchor, constant: -MeridianLayout.cardPadding),
            serverUrlFieldHome.heightAnchor.constraint(equalToConstant: 44),
            saveServerButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight)
        ])
        serverPromptCard.isHidden = true

        emergencyStatusLabel.numberOfLines = 0
        emergencyStatusLabel.font = .preferredFont(forTextStyle: .body)
        emergencyStatusLabel.textColor = MeridianPalette.primaryText
        emergencyStatusLabel.text = "No active emergency alerts."

        scheduleHeroDateLabel.font = .preferredFont(forTextStyle: .footnote)
        scheduleHeroDateLabel.textColor = MeridianPalette.mutedText
        scheduleHeroDateLabel.text = Self.scheduleHeroDateFormatter.string(from: Date())

        scheduleHeadingLabel.text = "What's next today"
        scheduleHeadingLabel.font = .preferredFont(forTextStyle: .headline)
        scheduleHeadingLabel.textColor = MeridianPalette.primaryText

        timelineStack.axis = .vertical
        timelineStack.spacing = 0
        timelineStack.alignment = .fill

        scheduleFootnoteLabel.numberOfLines = 0
        scheduleFootnoteLabel.font = .preferredFont(forTextStyle: .caption2)
        scheduleFootnoteLabel.textColor = MeridianPalette.mutedText
        scheduleFootnoteLabel.text = "Medications could not be loaded."
        scheduleFootnoteLabel.isHidden = true

        recentCheckInsLabel.numberOfLines = 0
        recentCheckInsLabel.font = .preferredFont(forTextStyle: .footnote)
        recentCheckInsLabel.textColor = MeridianPalette.primaryText
        recentCheckInsLabel.text = "Loading recent check-ins…"

        contentStack.axis = .vertical
        contentStack.spacing = MeridianLayout.sectionSpacing
        contentStack.translatesAutoresizingMaskIntoConstraints = false

        let emergencyStack = UIStackView(arrangedSubviews: [sectionTitle("Emergency status"), emergencyStatusLabel])
        emergencyStack.axis = .vertical
        emergencyStack.spacing = 8
        emergencyCard.addSubview(emergencyStack)
        emergencyStack.translatesAutoresizingMaskIntoConstraints = false

        let scheduleInner = UIStackView(arrangedSubviews: [
            scheduleHeroDateLabel,
            upNextContainer,
            scheduleHeadingLabel,
            timelineStack,
            scheduleFootnoteLabel
        ])
        scheduleInner.axis = .vertical
        scheduleInner.spacing = 8
        scheduleInner.setCustomSpacing(4, after: scheduleHeroDateLabel)
        scheduleInner.setCustomSpacing(10, after: upNextContainer)
        scheduleInner.setCustomSpacing(10, after: scheduleHeadingLabel)
        scheduleCard.addSubview(scheduleInner)
        scheduleInner.translatesAutoresizingMaskIntoConstraints = false

        let checkInsStack = UIStackView(arrangedSubviews: [
            sectionTitle("Family check-ins"),
            recentCheckInsLabel
        ])
        checkInsStack.axis = .vertical
        checkInsStack.spacing = 8
        checkInsCard.addSubview(checkInsStack)
        checkInsStack.translatesAutoresizingMaskIntoConstraints = false

        [emergencyStack, scheduleInner, checkInsStack].forEach { stack in
            NSLayoutConstraint.activate([
                stack.topAnchor.constraint(equalTo: stack.superview!.topAnchor, constant: MeridianLayout.cardPadding),
                stack.leadingAnchor.constraint(equalTo: stack.superview!.leadingAnchor, constant: MeridianLayout.cardPadding),
                stack.trailingAnchor.constraint(equalTo: stack.superview!.trailingAnchor, constant: -MeridianLayout.cardPadding),
                stack.bottomAnchor.constraint(equalTo: stack.superview!.bottomAnchor, constant: -MeridianLayout.cardPadding)
            ])
        }

        contentStack.addArrangedSubview(serverPromptCard)
        contentStack.addArrangedSubview(scheduleCard)
        contentStack.addArrangedSubview(checkInsCard)
        contentStack.addArrangedSubview(emergencyCard)

        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.contentInsetAdjustmentBehavior = .automatic
        scrollView.addSubview(contentStack)
        view.addSubview(scrollView)

        NSLayoutConstraint.activate([
            scrollView.topAnchor.constraint(equalTo: view.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            contentStack.topAnchor.constraint(equalTo: scrollView.contentLayoutGuide.topAnchor, constant: 0),
            contentStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.screenPadding),
            contentStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -MeridianLayout.screenPadding),
            contentStack.bottomAnchor.constraint(equalTo: scrollView.contentLayoutGuide.bottomAnchor, constant: -MeridianLayout.sectionSpacing),
            contentStack.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor, constant: -(MeridianLayout.screenPadding * 2))
        ])

        rebuildTimeline(entries: [], medsFetchFailed: false, sessionFailed: false)

        Task {
            await ensureMeridianServerForHome()
            await refreshHomeData()
        }
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        navigationController?.setNavigationBarHidden(true, animated: false)
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        navigationController?.setNavigationBarHidden(false, animated: false)
    }

    private func ensureMeridianServerForHome() async {
        if let chosen = await Config.resolveBackendBaseURL() {
            await MainActor.run {
                Config.saveApiBaseURL(chosen)
                serverPromptCard.isHidden = true
            }
        } else {
            await MainActor.run {
                let left = Config.persistedApiBaseURLFieldText().trimmingCharacters(in: .whitespacesAndNewlines)
                serverUrlFieldHome.text = left
                serverPromptStatusLabel.text = "Meridian server unreachable (tried ngrok, then Railway). Enter a URL or check the network."
                serverPromptStatusLabel.textColor = .systemOrange
                serverPromptCard.isHidden = false
            }
        }
    }

    @objc private func saveServerUrlTapped() {
        let raw = serverUrlFieldHome.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let normalized = Config.normalizedBaseURL(raw)
        guard Config.isValidHttpBaseURL(normalized) else {
            serverPromptStatusLabel.text = "Enter a valid http(s) base URL."
            serverPromptStatusLabel.textColor = .systemRed
            return
        }
        saveServerButton.isEnabled = false
        serverPromptStatusLabel.text = "Checking server…"
        serverPromptStatusLabel.textColor = .secondaryLabel
        Task {
            let ok = await Config.checkApiHealth(atBaseURL: normalized, timeout: Config.apiHealthCheckTimeoutSeconds)
            await MainActor.run { [weak self] in
                guard let self else { return }
                saveServerButton.isEnabled = true
                if ok {
                    Config.saveApiBaseURL(normalized)
                    APIService.shared.clearHttpCookies()
                    serverPromptCard.isHidden = true
                    serverPromptStatusLabel.text = ""
                    Task { await refreshHomeData() }
                } else {
                    serverPromptStatusLabel.text = "Could not reach /api/health on that host."
                    serverPromptStatusLabel.textColor = .systemOrange
                }
            }
        }
    }

    private func refreshHomeData() async {
        do {
            let s = try await APIService.shared.getSession()

            async let alertActive = APIService.shared.getEmergencyAlertStatus()
            async let today = APIService.shared.getTodayEventSummary(familyCircleId: s.familyCircleId)
            async let recentCheckins = APIService.shared.getCheckins(familyCircleId: s.familyCircleId)
            async let meds = APIService.shared.getMedicationHomeSnapshot(familyCircleId: s.familyCircleId)

            let isActive = (try? await alertActive) ?? false
            let todaySummaryResult = try? await today
            let todaySummary = todaySummaryResult ?? nil
            let checkinsResult = try? await recentCheckins
            let medsSnap = try? await meds

            await MainActor.run {
                hasCompletedHomeRefresh = true
                emergencyStatusLabel.text = isActive ? "Active emergency alert in progress." : "No active emergency alerts."
                emergencyStatusLabel.textColor = isActive ? MeridianPalette.alert : MeridianPalette.primaryText

                scheduleHeroDateLabel.text = Self.scheduleHeroDateFormatter.string(from: Date())
                let entries = APIService.buildHomeTodayTimeline(
                    medicationSnapshot: medsSnap,
                    appointment: todaySummary
                )
                rebuildTimeline(entries: entries, medsFetchFailed: medsSnap == nil, sessionFailed: false)

                recentCheckInsLabel.text = Self.formatRecentCheckIns(checkinsResult ?? [])
            }
        } catch {
            await MainActor.run {
                hasCompletedHomeRefresh = true
                emergencyStatusLabel.text = "Could not load emergency alerts."
                emergencyStatusLabel.textColor = MeridianPalette.primaryText
                scheduleHeroDateLabel.text = Self.scheduleHeroDateFormatter.string(from: Date())
                rebuildTimeline(entries: [], medsFetchFailed: false, sessionFailed: true)
                recentCheckInsLabel.text = "Could not load check-ins."
            }
        }
    }

    private func rebuildTimeline(entries: [HomeTodayTimelineEntry], medsFetchFailed: Bool, sessionFailed: Bool) {
        let nowM = Self.minutesSinceMidnightNow()
        configureUpNext(entries: entries, medsFetchFailed: medsFetchFailed, sessionFailed: sessionFailed, nowMinutes: nowM)

        timelineStack.arrangedSubviews.forEach { $0.removeFromSuperview() }
        scheduleFootnoteLabel.isHidden = !(medsFetchFailed && !entries.isEmpty)
        if sessionFailed {
            let err = UILabel()
            err.text = "Could not load today's schedule."
            err.font = .preferredFont(forTextStyle: .footnote)
            err.textColor = MeridianPalette.mutedText
            err.numberOfLines = 0
            timelineStack.addArrangedSubview(err)
            return
        }
        if entries.isEmpty {
            let empty = UILabel()
            empty.font = .preferredFont(forTextStyle: .footnote)
            empty.textColor = MeridianPalette.mutedText
            empty.numberOfLines = 0
            if !hasCompletedHomeRefresh {
                empty.text = "Loading…"
            } else if medsFetchFailed {
                empty.text = "Medications unavailable."
            } else {
                empty.text = "Nothing scheduled today."
            }
            timelineStack.addArrangedSubview(empty)
            return
        }

        let upIdx = entries.firstIndex { $0.blocksUpNext(nowMinutes: nowM) }
        let timelineEntries: [HomeTodayTimelineEntry]
        if let i = upIdx {
            timelineEntries = entries.enumerated().filter { $0.offset != i }.map { $0.element }
        } else {
            timelineEntries = entries
        }

        if timelineEntries.isEmpty {
            let rest = UILabel()
            rest.font = .preferredFont(forTextStyle: .footnote)
            rest.textColor = MeridianPalette.mutedText
            rest.numberOfLines = 0
            rest.text = "No other items on today's list."
            timelineStack.addArrangedSubview(rest)
            return
        }

        for e in timelineEntries {
            timelineStack.addArrangedSubview(makeTimelineRow(for: e))
        }
    }

    private func configureUpNext(
        entries: [HomeTodayTimelineEntry],
        medsFetchFailed: Bool,
        sessionFailed: Bool,
        nowMinutes: Int
    ) {
        if sessionFailed {
            upNextIconView.image = UIImage(systemName: "exclamationmark.triangle")
            upNextIconView.tintColor = MeridianPalette.mutedText
            upNextTitleLabel.text = "Couldn't load schedule"
            upNextMetaLabel.text = ""
            return
        }
        if !hasCompletedHomeRefresh && entries.isEmpty {
            upNextIconView.image = UIImage(systemName: "clock")
            upNextIconView.tintColor = MeridianPalette.mutedText
            upNextTitleLabel.text = "Loading…"
            upNextMetaLabel.text = ""
            return
        }
        if entries.isEmpty {
            upNextIconView.image = UIImage(systemName: "checkmark.circle")
            upNextIconView.tintColor = MeridianPalette.primaryAction
            if medsFetchFailed {
                upNextTitleLabel.text = "Medications unavailable"
                upNextMetaLabel.text = "Check the connection or try again later."
            } else {
                upNextTitleLabel.text = "All done for today"
                upNextMetaLabel.text = "Nothing else on the calendar."
            }
            return
        }
        guard let idx = entries.firstIndex(where: { $0.blocksUpNext(nowMinutes: nowMinutes) }) else {
            upNextIconView.image = UIImage(systemName: "checkmark.circle")
            upNextIconView.tintColor = MeridianPalette.primaryAction
            upNextTitleLabel.text = "All done for today"
            upNextMetaLabel.text = "No upcoming doses or visits from here on."
            return
        }
        let e = entries[idx]
        switch e.kind {
        case .medication, .prn:
            upNextIconView.image = UIImage(systemName: "pills.fill")
            upNextIconView.tintColor = MeridianPalette.primaryAction
        case .appointment:
            upNextIconView.image = UIImage(systemName: "calendar")
            upNextIconView.tintColor = MeridianPalette.timelineEventBar
        }
        upNextTitleLabel.text = e.title
        upNextMetaLabel.text = Self.upNextMetaLine(entry: e, nowMinutes: nowMinutes)
    }

    private static func minutesSinceMidnightNow() -> Int {
        let c = Calendar.current
        let now = Date()
        return c.component(.hour, from: now) * 60 + c.component(.minute, from: now)
    }

    private static func upNextMetaLine(entry: HomeTodayTimelineEntry, nowMinutes: Int) -> String {
        switch entry.kind {
        case .prn:
            return "Log when needed"
        case .medication, .appointment:
            let diff = entry.sortMinutes - nowMinutes
            let t = entry.timeDisplay
            if diff > 0 {
                if diff < 60 { return "\(t) · in \(diff) min" }
                let h = diff / 60
                let m = diff % 60
                if m > 0 { return "\(t) · in \(h)h \(m)m" }
                return "\(t) · in \(h)h"
            }
            if diff == 0 { return "\(t) · starting now" }
            return t
        }
    }

    private func makeTimelineRow(for entry: HomeTodayTimelineEntry) -> UIView {
        let bar = UIView()
        bar.translatesAutoresizingMaskIntoConstraints = false
        bar.layer.cornerRadius = 2
        bar.clipsToBounds = true
        switch entry.kind {
        case .medication:
            bar.backgroundColor = MeridianPalette.timelineMedBar
        case .appointment:
            bar.backgroundColor = MeridianPalette.timelineEventBar
        case .prn:
            bar.backgroundColor = MeridianPalette.timelinePrnBar
        }
        NSLayoutConstraint.activate([
            bar.widthAnchor.constraint(equalToConstant: 4),
            bar.heightAnchor.constraint(greaterThanOrEqualToConstant: 36)
        ])

        let timeLabel = UILabel()
        timeLabel.text = entry.timeDisplay
        timeLabel.font = .preferredFont(forTextStyle: .caption1)
        timeLabel.textColor = MeridianPalette.mutedText

        let titleLabel = UILabel()
        titleLabel.text = entry.title
        titleLabel.font = .preferredFont(forTextStyle: .subheadline)
        titleLabel.textColor = entry.done ? MeridianPalette.mutedText : MeridianPalette.primaryText
        titleLabel.numberOfLines = 0

        let textColumn = UIStackView(arrangedSubviews: [timeLabel, titleLabel])
        textColumn.axis = .vertical
        textColumn.spacing = 2
        textColumn.alignment = .leading

        let statusLabel = UILabel()
        statusLabel.font = .preferredFont(forTextStyle: .caption2)
        statusLabel.textColor = MeridianPalette.mutedText
        statusLabel.textAlignment = .right
        statusLabel.setContentHuggingPriority(.required, for: .horizontal)
        switch entry.kind {
        case .medication:
            statusLabel.text = entry.done ? "Taken" : "Pending"
        case .appointment:
            statusLabel.text = "Appt"
        case .prn:
            statusLabel.text = "PRN"
        }

        let trailingStack = UIStackView()
        trailingStack.axis = .vertical
        trailingStack.spacing = 6
        trailingStack.alignment = .trailing
        trailingStack.addArrangedSubview(statusLabel)

        switch entry.kind {
        case .medication, .prn:
            let action = UIButton(type: .system)
            var cfg = UIButton.Configuration.bordered()
            cfg.buttonSize = .small
            cfg.title = entry.kind == .prn ? "Log" : "Take"
            cfg.baseForegroundColor = MeridianPalette.primaryAction
            action.configuration = cfg
            action.addAction(UIAction { _ in }, for: .touchUpInside)
            if entry.kind == .medication {
                action.isEnabled = !entry.done
            }
            trailingStack.addArrangedSubview(action)
        case .appointment:
            break
        }

        let row = UIStackView(arrangedSubviews: [bar, textColumn, trailingStack])
        row.axis = .horizontal
        row.alignment = .center
        row.spacing = 10
        row.layoutMargins = UIEdgeInsets(top: 10, left: 0, bottom: 10, right: 0)
        row.isLayoutMarginsRelativeArrangement = true
        return row
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

    private static func formatRecentCheckIns(_ checkins: [CheckIn]) -> String {
        let top = Array(checkins.prefix(4))
        guard !top.isEmpty else {
            return "No check-ins yet. Use the Check-In tab to share your location."
        }
        return top.map { c in
            let loc = c.locationName ?? "Location unknown"
            let t = homeRecentTimeFormatter.string(from: c.timestamp)
            return "• \(c.contactName) · \(loc) · \(t)"
        }.joined(separator: "\n")
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
        developerToolsButton.addTarget(self, action: #selector(developerToolsTapped), for: .touchUpInside)

        [accountButton, notificationButton, sensorConfigurationButton, appearanceButton, developerToolsButton].forEach {
            contentStack.addArrangedSubview($0)
        }

        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.contentInsetAdjustmentBehavior = .automatic
        scrollView.addSubview(contentStack)
        view.addSubview(scrollView)

        NSLayoutConstraint.activate([
            accountButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            notificationButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            sensorConfigurationButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            appearanceButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            developerToolsButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),

            scrollView.topAnchor.constraint(equalTo: view.topAnchor),
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

    @objc private func developerToolsTapped() {
        onOpenDeveloperTools?()
    }
}

enum MeridianPalette {
    static let background = UIColor(hex: "#F7F9FA")
    static let surface = UIColor(hex: "#FFFFFF")
    static let surfaceSchedule = UIColor(hex: "#EFF5F8")
    static let primaryText = UIColor(hex: "#2C3E50")
    static let mutedText = UIColor(hex: "#5E6B78")
    static let primaryAction = UIColor(hex: "#2E7D9B")
    static let border = UIColor(hex: "#D8E0E8")
    static let alert = UIColor(hex: "#E67E73")
    static let timelineMedBar = UIColor(hex: "#2E7D9B")
    static let timelineEventBar = UIColor(hex: "#8E9AAF")
    static let timelinePrnBar = UIColor(hex: "#B8A06E")
    static let upNextFill = UIColor(red: 0.93, green: 0.96, blue: 0.99, alpha: 1)
    static let upNextBorder = UIColor(hex: "#C5D4E0")
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
