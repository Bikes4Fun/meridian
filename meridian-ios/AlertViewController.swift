/**
 * Meridian iOS – Alert TV. Start / cancel emergency alert.
 */
import UIKit

final class AlertViewController: UIViewController {
    private let activateEmergencyAlertButton = UIButton(type: .system)
    private let cancelEmergencyAlertButton = UIButton(type: .system)
    private let forceAnswerCallButton = UIButton(type: .system)
    private let sensorCheckButton = UIButton(type: .system)
    private let statusLabel = UILabel()
    private let progressIndicator = UIActivityIndicatorView(style: .medium)
    private var isRequestInFlight = false {
        didSet { updateControlsForRequestState() }
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = MeridianPalette.background

        activateEmergencyAlertButton.applyMeridianButtonStyle(.alert, title: "Activate Emergency Alert")
        activateEmergencyAlertButton.addTarget(self, action: #selector(activateAlert), for: .touchUpInside)

        cancelEmergencyAlertButton.applyMeridianButtonStyle(.bordered, title: "Cancel Emergency Alert")
        cancelEmergencyAlertButton.addTarget(self, action: #selector(cancelAlert), for: .touchUpInside)

        forceAnswerCallButton.applyMeridianButtonStyle(.secondary, title: "Force Call Kiosk")
        forceAnswerCallButton.addTarget(self, action: #selector(forceAnswerCallTapped), for: .touchUpInside)

        sensorCheckButton.applyMeridianButtonStyle(.bordered, title: "Sensor Check (Coming Soon)")
        sensorCheckButton.addTarget(self, action: #selector(sensorCheckTapped), for: .touchUpInside)

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = MeridianPalette.mutedText
        statusLabel.font = .preferredFont(forTextStyle: .callout)
        statusLabel.text = ""

        let stack = UIStackView(arrangedSubviews: [
            activateEmergencyAlertButton, cancelEmergencyAlertButton, forceAnswerCallButton, sensorCheckButton, progressIndicator, statusLabel
        ])
        stack.axis = .vertical
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(stack)
        NSLayoutConstraint.activate([
            activateEmergencyAlertButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            cancelEmergencyAlertButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            forceAnswerCallButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            sensorCheckButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.screenPadding),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -MeridianLayout.screenPadding)
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

    @objc private func forceAnswerCallTapped() {
        if isRequestInFlight { return }
        isRequestInFlight = true
        setStatus("Requesting kiosk force call...")
        Task {
            do {
                try await APIService.shared.requestCallToDefaultRecipient()
                await MainActor.run {
                    self.isRequestInFlight = false
                    self.setStatus("Kiosk force call requested.", color: .systemGreen)
                }
            } catch {
                await MainActor.run {
                    self.isRequestInFlight = false
                    self.setStatus("Force call failed. Please try again.", color: .systemRed)
                }
            }
        }
    }

    @objc private func sensorCheckTapped() {
        setStatus("Sensor check controls are staged here for future implementation.")
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
                    self.setStatus(activated ? "Alert failed. Please try again." : "Cancel failed. Please try again.", color: .systemRed)
                }
            }
        }
    }

    private func updateControlsForRequestState() {
        activateEmergencyAlertButton.isEnabled = !isRequestInFlight
        cancelEmergencyAlertButton.isEnabled = !isRequestInFlight
        forceAnswerCallButton.isEnabled = !isRequestInFlight
        sensorCheckButton.isEnabled = !isRequestInFlight
        if isRequestInFlight {
            progressIndicator.startAnimating()
        } else {
            progressIndicator.stopAnimating()
        }
    }
}
