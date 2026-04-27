/**
 * Meridian iOS – Alert TV. Start / cancel emergency alert.
 */
import UIKit

final class AlertViewController: UIViewController {
    private let scrollView = UIScrollView()
    private let contentStack = UIStackView()
    private let titleLabel = UILabel()
    private let activateEmergencyAlertButton = UIButton(type: .system)
    private let cancelEmergencyAlertButton = UIButton(type: .system)
    private let readinessCard = UIView()
    private let readinessTitleLabel = UILabel()
    private let readinessDetailLabel = UILabel()
    private let stoveCard = UIView()
    private let stoveTitleLabel = UILabel()
    private let stoveDetailLabel = UILabel()
    private let statusLabel = UILabel()
    private let progressIndicator = UIActivityIndicatorView(style: .medium)
    private let forceAnswerToggle = UISwitch()
    private let forceAnswerLabel = UILabel()
    private let callKioskCard = UIView()
    private let callKioskTitleLabel = UILabel()
    private let callKioskButton = UIButton(type: .system)
    private let forceCallKioskButton = UIButton(type: .system)
    private let callKioskStatusLabel = UILabel()
    private var isRequestInFlight = false {
        didSet { updateControlsForRequestState() }
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = MeridianPalette.background

        titleLabel.text = "Emergency Operations"
        titleLabel.font = .preferredFont(forTextStyle: .title2)
        titleLabel.textColor = MeridianPalette.primaryText

        activateEmergencyAlertButton.applyMeridianButtonStyle(.alert, title: "Activate Emergency Alert")
        activateEmergencyAlertButton.addTarget(self, action: #selector(activateAlert), for: .touchUpInside)

        cancelEmergencyAlertButton.applyMeridianButtonStyle(.bordered, title: "Cancel Emergency Alert")
        cancelEmergencyAlertButton.addTarget(self, action: #selector(cancelAlert), for: .touchUpInside)

        readinessCard.backgroundColor = MeridianPalette.surface
        readinessCard.layer.cornerRadius = 12
        readinessCard.layer.borderWidth = 1
        readinessCard.layer.borderColor = MeridianPalette.border.cgColor
        readinessCard.translatesAutoresizingMaskIntoConstraints = false

        readinessTitleLabel.text = "Safety Readiness"
        readinessTitleLabel.font = .preferredFont(forTextStyle: .headline)
        readinessTitleLabel.textColor = MeridianPalette.primaryText

        readinessDetailLabel.text = "ICE profile complete · Primary responder ready."
        readinessDetailLabel.font = .preferredFont(forTextStyle: .footnote)
        readinessDetailLabel.textColor = MeridianPalette.mutedText
        readinessDetailLabel.numberOfLines = 0

        let readinessStack = UIStackView(arrangedSubviews: [readinessTitleLabel, readinessDetailLabel])
        readinessStack.axis = .vertical
        readinessStack.spacing = 6
        readinessStack.translatesAutoresizingMaskIntoConstraints = false
        readinessCard.addSubview(readinessStack)
        NSLayoutConstraint.activate([
            readinessStack.topAnchor.constraint(equalTo: readinessCard.topAnchor, constant: 12),
            readinessStack.leadingAnchor.constraint(equalTo: readinessCard.leadingAnchor, constant: 12),
            readinessStack.trailingAnchor.constraint(equalTo: readinessCard.trailingAnchor, constant: -12),
            readinessStack.bottomAnchor.constraint(equalTo: readinessCard.bottomAnchor, constant: -12)
        ])

        stoveCard.backgroundColor = MeridianPalette.surface
        stoveCard.layer.cornerRadius = 12
        stoveCard.layer.borderWidth = 1
        stoveCard.layer.borderColor = MeridianPalette.border.cgColor
        stoveCard.translatesAutoresizingMaskIntoConstraints = false

        stoveTitleLabel.text = "Stove"
        stoveTitleLabel.font = .preferredFont(forTextStyle: .headline)
        stoveTitleLabel.textColor = MeridianPalette.primaryText

        stoveDetailLabel.text = [
            "Surface temperature",
            "142°F",
            "Status · Normal",
            "Updated · 10:42 AM"
        ].joined(separator: "\n")
        stoveDetailLabel.font = .preferredFont(forTextStyle: .footnote)
        stoveDetailLabel.textColor = MeridianPalette.primaryText
        stoveDetailLabel.numberOfLines = 0

        let stoveStack = UIStackView(arrangedSubviews: [stoveTitleLabel, stoveDetailLabel])
        stoveStack.axis = .vertical
        stoveStack.spacing = 8
        stoveStack.translatesAutoresizingMaskIntoConstraints = false
        stoveCard.addSubview(stoveStack)
        NSLayoutConstraint.activate([
            stoveStack.topAnchor.constraint(equalTo: stoveCard.topAnchor, constant: 12),
            stoveStack.leadingAnchor.constraint(equalTo: stoveCard.leadingAnchor, constant: 12),
            stoveStack.trailingAnchor.constraint(equalTo: stoveCard.trailingAnchor, constant: -12),
            stoveStack.bottomAnchor.constraint(equalTo: stoveCard.bottomAnchor, constant: -12)
        ])

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = MeridianPalette.mutedText
        statusLabel.font = .preferredFont(forTextStyle: .callout)
        statusLabel.text = ""

        contentStack.axis = .vertical
        contentStack.spacing = 12
        contentStack.translatesAutoresizingMaskIntoConstraints = false

        forceAnswerLabel.text = "Also force-answer the kiosk so I can speak with them"
        forceAnswerLabel.font = .preferredFont(forTextStyle: .footnote)
        forceAnswerLabel.textColor = MeridianPalette.primaryText
        forceAnswerLabel.numberOfLines = 0
        forceAnswerToggle.isOn = false
        let forceAnswerRow = UIStackView(arrangedSubviews: [forceAnswerToggle, forceAnswerLabel])
        forceAnswerRow.axis = .horizontal
        forceAnswerRow.alignment = .center
        forceAnswerRow.spacing = 12

        callKioskCard.backgroundColor = MeridianPalette.surface
        callKioskCard.layer.cornerRadius = 12
        callKioskCard.layer.borderWidth = 1
        callKioskCard.layer.borderColor = MeridianPalette.border.cgColor
        callKioskCard.translatesAutoresizingMaskIntoConstraints = false

        callKioskTitleLabel.text = "Call kiosk"
        callKioskTitleLabel.font = .preferredFont(forTextStyle: .headline)
        callKioskTitleLabel.textColor = MeridianPalette.primaryText

        callKioskButton.applyMeridianButtonStyle(.primary, title: "Call")
        callKioskButton.setImage(UIImage(systemName: "phone.fill"), for: .normal)
        callKioskButton.addTarget(self, action: #selector(callKioskTapped), for: .touchUpInside)
        forceCallKioskButton.applyMeridianButtonStyle(.bordered, title: "Force Call")
        forceCallKioskButton.setImage(UIImage(systemName: "phone.badge.plus"), for: .normal)
        forceCallKioskButton.addTarget(self, action: #selector(forceCallKioskTapped), for: .touchUpInside)
        callKioskStatusLabel.font = .preferredFont(forTextStyle: .caption1)
        callKioskStatusLabel.textColor = MeridianPalette.mutedText
        callKioskStatusLabel.textAlignment = .center
        callKioskStatusLabel.numberOfLines = 0
        callKioskStatusLabel.isHidden = true
        let callButtonRow = UIStackView(arrangedSubviews: [callKioskButton, forceCallKioskButton])
        callButtonRow.axis = .horizontal
        callButtonRow.spacing = 12
        callButtonRow.distribution = .fillEqually
        let callKioskInner = UIStackView(arrangedSubviews: [callKioskTitleLabel, callButtonRow, callKioskStatusLabel])
        callKioskInner.axis = .vertical
        callKioskInner.spacing = 10
        callKioskInner.translatesAutoresizingMaskIntoConstraints = false
        callKioskCard.addSubview(callKioskInner)
        NSLayoutConstraint.activate([
            callKioskInner.topAnchor.constraint(equalTo: callKioskCard.topAnchor, constant: 12),
            callKioskInner.leadingAnchor.constraint(equalTo: callKioskCard.leadingAnchor, constant: 12),
            callKioskInner.trailingAnchor.constraint(equalTo: callKioskCard.trailingAnchor, constant: -12),
            callKioskInner.bottomAnchor.constraint(equalTo: callKioskCard.bottomAnchor, constant: -12),
            callKioskButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            forceCallKioskButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight)
        ])

        [titleLabel, activateEmergencyAlertButton, forceAnswerRow, cancelEmergencyAlertButton, callKioskCard, readinessCard, stoveCard, progressIndicator, statusLabel].forEach {
            contentStack.addArrangedSubview($0)
        }

        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.alwaysBounceVertical = true
        scrollView.addSubview(contentStack)
        view.addSubview(scrollView)

        NSLayoutConstraint.activate([
            activateEmergencyAlertButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            cancelEmergencyAlertButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),

            scrollView.topAnchor.constraint(equalTo: view.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            contentStack.topAnchor.constraint(equalTo: scrollView.contentLayoutGuide.topAnchor, constant: 12),
            contentStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.screenPadding),
            contentStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -MeridianLayout.screenPadding),
            contentStack.bottomAnchor.constraint(equalTo: scrollView.contentLayoutGuide.bottomAnchor, constant: -12),
            contentStack.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor, constant: -(MeridianLayout.screenPadding * 2))
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

    @objc private func activateAlert() {
        if isRequestInFlight { return }
        performAlertUpdate(activated: true)
    }

    @objc private func cancelAlert() {
        if isRequestInFlight { return }
        performAlertUpdate(activated: false)
    }

    private func setStatus(_ text: String, color: UIColor = .secondaryLabel) {
        statusLabel.text = text
        statusLabel.textColor = color
    }

    private func performAlertUpdate(activated: Bool) {
        isRequestInFlight = true
        let shouldForceAnswer = activated && forceAnswerToggle.isOn
        setStatus(activated ? "Sending emergency alert..." : "Cancelling emergency alert...")
        Task {
            if activated && shouldForceAnswer {
                var kioskCallPrepFinished = false
                do {
                    await MainActor.run { self.setStatus("Arming kiosk to auto-answer…") }
                    try await APIService.shared.forceAnswerKiosk()
                    await MainActor.run { self.setStatus("Fetching kiosk number…") }
                    let number = try await APIService.shared.getKioskPhoneNumber()
                    kioskCallPrepFinished = true
                    await MainActor.run { self.setStatus("Activating emergency alert…") }
                    try await APIService.shared.setAlert(activated: true)
                    await MainActor.run {
                        self.isRequestInFlight = false
                        self.setStatus("Emergency alert sent. Opening kiosk call…", color: .systemGreen)
                        let cleaned = number.filter { $0.isNumber || $0 == "+" }
                        if let url = URL(string: "tel://\(cleaned)") {
                            UIApplication.shared.open(url)
                        }
                    }
                } catch {
                    let detail = Self.alertFlowUserMessage(for: error)
                    await MainActor.run {
                        self.isRequestInFlight = false
                        if !kioskCallPrepFinished {
                            self.setStatus(
                                "Emergency alert was not turned on.\n\n\(detail)\n\nYou can try again, or activate without the auto-answer option.",
                                color: .systemRed
                            )
                        } else {
                            self.setStatus(
                                "The kiosk may be ready to auto-answer, but the emergency alert could not be activated.\n\n\(detail)\n\nTry Call or Force Call below, or try activating again.",
                                color: .systemOrange
                            )
                        }
                    }
                }
                return
            }
            do {
                try await APIService.shared.setAlert(activated: activated)
                await MainActor.run {
                    self.isRequestInFlight = false
                    self.setStatus(activated ? "Emergency alert sent." : "Emergency alert cancelled.", color: .systemGreen)
                }
            } catch {
                let detail = Self.alertFlowUserMessage(for: error)
                await MainActor.run {
                    self.isRequestInFlight = false
                    self.setStatus(detail, color: .systemRed)
                }
            }
        }
    }

    private static func alertFlowUserMessage(for error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
    }

    private func updateControlsForRequestState() {
        activateEmergencyAlertButton.isEnabled = !isRequestInFlight
        cancelEmergencyAlertButton.isEnabled = !isRequestInFlight
        if isRequestInFlight {
            progressIndicator.startAnimating()
        } else {
            progressIndicator.stopAnimating()
        }
    }

    @objc private func callKioskTapped() {
        callKioskButton.isEnabled = false
        forceCallKioskButton.isEnabled = false
        callKioskStatusLabel.text = "Fetching number…"
        callKioskStatusLabel.textColor = MeridianPalette.mutedText
        callKioskStatusLabel.isHidden = false
        Task {
            do {
                let number = try await APIService.shared.getKioskPhoneNumber()
                await MainActor.run {
                    self.resetCallKioskButtons()
                    let cleaned = number.filter { $0.isNumber || $0 == "+" }
                    if let url = URL(string: "tel://\(cleaned)") {
                        UIApplication.shared.open(url)
                    }
                }
            } catch {
                await MainActor.run {
                    self.callKioskStatusLabel.text = error.localizedDescription
                    self.callKioskStatusLabel.textColor = MeridianPalette.alert
                    DispatchQueue.main.asyncAfter(deadline: .now() + 4) { [weak self] in
                        self?.resetCallKioskButtons()
                    }
                }
            }
        }
    }

    @objc private func forceCallKioskTapped() {
        callKioskButton.isEnabled = false
        forceCallKioskButton.isEnabled = false
        callKioskStatusLabel.text = "Arming kiosk…"
        callKioskStatusLabel.textColor = MeridianPalette.mutedText
        callKioskStatusLabel.isHidden = false
        Task {
            do {
                async let forceAnswer: Void = APIService.shared.forceAnswerKiosk()
                async let number: String = APIService.shared.getKioskPhoneNumber()
                let (_, kioskNumber) = try await (forceAnswer, number)
                await MainActor.run {
                    self.callKioskStatusLabel.text = "Kiosk will answer automatically when you call."
                    self.callKioskStatusLabel.textColor = MeridianPalette.primaryAction
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                        self?.resetCallKioskButtons()
                    }
                    let cleaned = kioskNumber.filter { $0.isNumber || $0 == "+" }
                    if let url = URL(string: "tel://\(cleaned)") {
                        UIApplication.shared.open(url)
                    }
                }
            } catch {
                await MainActor.run {
                    self.callKioskStatusLabel.text = error.localizedDescription
                    self.callKioskStatusLabel.textColor = MeridianPalette.alert
                    DispatchQueue.main.asyncAfter(deadline: .now() + 4) { [weak self] in
                        self?.resetCallKioskButtons()
                    }
                }
            }
        }
    }

    private func resetCallKioskButtons() {
        callKioskButton.isEnabled = true
        forceCallKioskButton.isEnabled = true
        callKioskStatusLabel.isHidden = true
    }
}
