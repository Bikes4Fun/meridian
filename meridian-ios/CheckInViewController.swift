/**
 * Meridian iOS – Check-in. GPS + optional notes. Shows recent family check-ins.
 */
import UIKit
import CoreLocation

final class CheckInViewController: UIViewController {
    private let notesField = UITextField()
    private let checkInButton = UIButton(type: .system)
    private let statusLabel = UILabel()
    private let checkinsLabel = UILabel()
    private var session: SessionInfo?
    private var pendingCheckInSession: SessionInfo?
    private var checkins: [CheckIn] = []

    private let locationManager = CLLocationManager()
    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .short
        f.timeStyle = .short
        return f
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        title = "Check-In"

        notesField.placeholder = "Notes (optional)"
        notesField.borderStyle = .roundedRect

        checkInButton.setTitle("Check In Now", for: .normal)
        checkInButton.addTarget(self, action: #selector(doCheckIn), for: .touchUpInside)

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = .secondaryLabel

        checkinsLabel.numberOfLines = 0
        checkinsLabel.textColor = .secondaryLabel
        checkinsLabel.font = .preferredFont(forTextStyle: .footnote)

        let formStack = UIStackView(arrangedSubviews: [checkinsLabel, notesField, checkInButton, statusLabel])
        formStack.axis = .vertical
        formStack.spacing = 16
        formStack.setCustomSpacing(24, after: checkinsLabel)
        formStack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(formStack)
        NSLayoutConstraint.activate([
            notesField.heightAnchor.constraint(equalToConstant: 44),
            checkInButton.heightAnchor.constraint(equalToConstant: 52),
            formStack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 24),
            formStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            formStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24)
        ])

        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters

        Task {
            do {
                session = try await APIService.shared.getSession()
                await loadCheckins()
            } catch {
                await MainActor.run { statusLabel.text = "Session lost: \(error.localizedDescription)" }
            }
        }
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if session == nil {
            Task {
                do {
                    session = try await APIService.shared.getSession()
                } catch {
                    await MainActor.run { statusLabel.text = "Session lost. Log in again." }
                }
            }
        } else {
            Task { await loadCheckins() }
        }
    }

    private func loadCheckins() async {
        guard let s = session else { return }
        do {
            let list = try await APIService.shared.getCheckins(familyCircleId: s.familyCircleId)
            await MainActor.run {
                checkins = list
                updateCheckinsLabel()
            }
        } catch {
            await MainActor.run {
                checkins = []
                checkinsLabel.text = "Recent: —"
            }
        }
    }

    private func updateCheckinsLabel() {
        if checkins.isEmpty {
            checkinsLabel.text = "Recent check-ins: none yet"
        } else {
            let lines = checkins.prefix(5).map { c in
                let loc = c.locationName ?? "Unknown"
                let time = Self.dateFormatter.string(from: c.timestamp)
                return "• \(c.contactName): \(loc) (\(time))"
            }
            checkinsLabel.text = "Recent check-ins:\n" + lines.joined(separator: "\n")
        }
    }

    @objc private func doCheckIn() {
        guard let s = session else {
            statusLabel.text = "Session lost. Log in again."
            statusLabel.textColor = .systemRed
            return
        }

        statusLabel.text = "Getting location…"
        statusLabel.textColor = .secondaryLabel
        checkInButton.isEnabled = false
        pendingCheckInSession = s

        switch locationManager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            locationManager.requestLocation()
        case .notDetermined:
            locationManager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            pendingCheckInSession = nil
            statusLabel.text = "Location access denied. Enable it in Settings."
            statusLabel.textColor = .systemRed
            checkInButton.isEnabled = true
        @unknown default:
            pendingCheckInSession = nil
            statusLabel.text = "Location unavailable"
            statusLabel.textColor = .systemRed
            checkInButton.isEnabled = true
        }
    }

    private func performCheckIn(loc: CLLocation, session: SessionInfo) {
        let notes = notesField.text?.trimmingCharacters(in: .whitespacesAndNewlines)
        let n: String? = (notes?.isEmpty ?? true) ? nil : notes

        Task {
            do {
                try await APIService.shared.checkIn(
                    familyCircleId: session.familyCircleId,
                    userId: session.userId,
                    latitude: loc.coordinate.latitude,
                    longitude: loc.coordinate.longitude,
                    notes: n
                )
                await MainActor.run {
                    statusLabel.text = "✓ Check-in successful"
                    statusLabel.textColor = .systemGreen
                    notesField.text = ""
                    checkInButton.isEnabled = true
                    Task { await loadCheckins() }
                }
            } catch {
                await MainActor.run {
                    statusLabel.text = error.localizedDescription
                    statusLabel.textColor = .systemRed
                    checkInButton.isEnabled = true
                }
            }
        }
    }
}

extension CheckInViewController: CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard pendingCheckInSession != nil else { return }
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            manager.requestLocation()
        case .denied, .restricted:
            pendingCheckInSession = nil
            statusLabel.text = "Location access denied. Enable it in Settings."
            statusLabel.textColor = .systemRed
            checkInButton.isEnabled = true
        default:
            break
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last, let s = pendingCheckInSession else { return }
        pendingCheckInSession = nil
        performCheckIn(loc: loc, session: s)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        pendingCheckInSession = nil
        statusLabel.text = "Location unavailable: \(error.localizedDescription)"
        statusLabel.textColor = .systemRed
        checkInButton.isEnabled = true
    }
}
