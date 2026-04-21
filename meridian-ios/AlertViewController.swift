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
    private let statusLabel = UILabel()
    private let progressIndicator = UIActivityIndicatorView(style: .medium)
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

        readinessDetailLabel.text = "ICE profile: Complete • Stove sensor: Online • Primary responder: Ready"
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

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = MeridianPalette.mutedText
        statusLabel.font = .preferredFont(forTextStyle: .callout)
        statusLabel.text = ""

        contentStack.axis = .vertical
        contentStack.spacing = 12
        contentStack.translatesAutoresizingMaskIntoConstraints = false

        [titleLabel, activateEmergencyAlertButton, cancelEmergencyAlertButton, readinessCard, progressIndicator, statusLabel].forEach {
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
        setStatus(activated ? "Sending emergency alert..." : "Cancelling emergency alert...")
        Task {
            do {
                try await APIService.shared.setAlert(activated: activated)
                await MainActor.run {
                    self.isRequestInFlight = false
                    self.setStatus(activated ? "Emergency alert sent." : "Emergency alert cancelled.", color: .systemGreen)
                }
            } catch {
                await MainActor.run {
                    self.isRequestInFlight = false
                    self.setStatus(error.localizedDescription, color: .systemRed)
                }
            }
        }
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
}
