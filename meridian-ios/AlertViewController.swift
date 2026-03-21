/**
 * Meridian iOS – Alert TV. Start / cancel emergency alert.
 */
import UIKit

final class AlertViewController: UIViewController {
    private let alertButton = UIButton(type: .system)
    private let cancelButton = UIButton(type: .system)
    private let statusLabel = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        title = "Alert"

        alertButton.setTitle("Alert Mode", for: .normal)
        alertButton.backgroundColor = .systemRed
        alertButton.setTitleColor(.white, for: .normal)
        alertButton.layer.cornerRadius = 8
        alertButton.addTarget(self, action: #selector(activateAlert), for: .touchUpInside)

        cancelButton.setTitle("Cancel Alert", for: .normal)
        cancelButton.backgroundColor = .systemGray
        cancelButton.setTitleColor(.white, for: .normal)
        cancelButton.layer.cornerRadius = 8
        cancelButton.addTarget(self, action: #selector(cancelAlert), for: .touchUpInside)

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = .secondaryLabel

        let stack = UIStackView(arrangedSubviews: [
            alertButton, cancelButton, statusLabel
        ])
        stack.axis = .vertical
        stack.spacing = 16
        stack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(stack)
        NSLayoutConstraint.activate([
            alertButton.heightAnchor.constraint(equalToConstant: 52),
            cancelButton.heightAnchor.constraint(equalToConstant: 52),
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24)
        ])
    }

    @objc private func activateAlert() {
        setStatus("Activating…")
        Task {
            do {
                try await APIService.shared.setAlert(activated: true)
                await MainActor.run { setStatus("Alert activated. TV should switch to emergency.", color: .systemGreen) }
            } catch {
                await MainActor.run { setStatus(error.localizedDescription, color: .systemRed) }
            }
        }
    }

    @objc private func cancelAlert() {
        setStatus("Cancelling…")
        Task {
            do {
                try await APIService.shared.setAlert(activated: false)
                await MainActor.run { setStatus("Alert cancelled.", color: .systemGreen) }
            } catch {
                await MainActor.run { setStatus(error.localizedDescription, color: .systemRed) }
            }
        }
    }

    private func setStatus(_ text: String, color: UIColor = .secondaryLabel) {
        statusLabel.text = text
        statusLabel.textColor = color
    }
}
