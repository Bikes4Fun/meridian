/**
 * Meridian iOS – Check-in. GPS + optional notes. Shows recent family check-ins.
 */
import UIKit
import CoreLocation
import MapKit

final class CheckInViewController: UIViewController {
    private let notesField = UITextField()
    private let manualCheckInButton = UIButton(type: .system)
    private let refreshStatusButton = UIButton(type: .system)
    private let statusLabel = UILabel()
    private let familyMapView = MKMapView()
    private let familyStatusTableView = UITableView(frame: .zero, style: .insetGrouped)
    private let emptyStateLabel = UILabel()
    private var session: SessionInfo?
    private var pendingCheckInSession: SessionInfo?
    private var checkins: [CheckIn] = []
    private var locationTimeoutWorkItem: DispatchWorkItem?

    private let locationManager = CLLocationManager()
    private let locationTimeoutSeconds: TimeInterval = 10
    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .short
        f.timeStyle = .short
        return f
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        applyMeridianScreenDefaults(title: "Check-In")

        notesField.placeholder = "Notes (optional)"
        notesField.borderStyle = .roundedRect

        manualCheckInButton.applyMeridianButtonStyle(.primary, title: "Manual Check-In Now")
        manualCheckInButton.addTarget(self, action: #selector(doCheckIn), for: .touchUpInside)

        refreshStatusButton.applyMeridianButtonStyle(.bordered, title: "Refresh Family Status")
        refreshStatusButton.addTarget(self, action: #selector(refreshFamilyStatusTapped), for: .touchUpInside)

        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.textColor = MeridianPalette.mutedText
        statusLabel.font = .preferredFont(forTextStyle: .footnote)

        familyStatusTableView.dataSource = self
        familyStatusTableView.delegate = self
        familyStatusTableView.rowHeight = UITableView.automaticDimension
        familyStatusTableView.estimatedRowHeight = 64
        familyStatusTableView.backgroundColor = .clear
        familyStatusTableView.alwaysBounceVertical = true

        familyMapView.layer.cornerRadius = 10
        familyMapView.layer.masksToBounds = true
        familyMapView.layer.borderWidth = 1
        familyMapView.layer.borderColor = MeridianPalette.border.cgColor
        familyMapView.showsCompass = false

        emptyStateLabel.text = "No family check-ins yet."
        emptyStateLabel.textAlignment = .center
        emptyStateLabel.textColor = MeridianPalette.mutedText
        emptyStateLabel.font = .preferredFont(forTextStyle: .subheadline)
        emptyStateLabel.isHidden = true

        let mapTitleLabel = UILabel()
        mapTitleLabel.text = "Family Map"
        mapTitleLabel.font = .preferredFont(forTextStyle: .subheadline)
        mapTitleLabel.textColor = MeridianPalette.primaryText

        let sectionTitleLabel = UILabel()
        sectionTitleLabel.text = "Family Status"
        sectionTitleLabel.font = .preferredFont(forTextStyle: .subheadline)
        sectionTitleLabel.textColor = MeridianPalette.primaryText

        let controlsStack = UIStackView(arrangedSubviews: [
            manualCheckInButton,
            notesField,
            refreshStatusButton,
            statusLabel
        ])
        controlsStack.axis = .vertical
        controlsStack.spacing = 8
        controlsStack.setCustomSpacing(12, after: refreshStatusButton)
        controlsStack.setCustomSpacing(6, after: sectionTitleLabel)
        controlsStack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(controlsStack)
        view.addSubview(mapTitleLabel)
        view.addSubview(familyMapView)
        view.addSubview(sectionTitleLabel)
        view.addSubview(familyStatusTableView)
        familyStatusTableView.addSubview(emptyStateLabel)
        emptyStateLabel.translatesAutoresizingMaskIntoConstraints = false
        mapTitleLabel.translatesAutoresizingMaskIntoConstraints = false
        familyMapView.translatesAutoresizingMaskIntoConstraints = false
        sectionTitleLabel.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            notesField.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            manualCheckInButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            refreshStatusButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            controlsStack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: MeridianLayout.sectionSpacing),
            controlsStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.cardPadding + 4),
            controlsStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -(MeridianLayout.cardPadding + 4)),

            mapTitleLabel.topAnchor.constraint(equalTo: controlsStack.bottomAnchor, constant: 8),
            mapTitleLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.cardPadding + 4),
            mapTitleLabel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -(MeridianLayout.cardPadding + 4)),

            familyMapView.topAnchor.constraint(equalTo: mapTitleLabel.bottomAnchor, constant: 6),
            familyMapView.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.cardPadding + 4),
            familyMapView.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -(MeridianLayout.cardPadding + 4)),
            familyMapView.heightAnchor.constraint(equalToConstant: 220),

            sectionTitleLabel.topAnchor.constraint(equalTo: familyMapView.bottomAnchor, constant: 8),
            sectionTitleLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.cardPadding + 4),
            sectionTitleLabel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -(MeridianLayout.cardPadding + 4)),

            familyStatusTableView.topAnchor.constraint(equalTo: sectionTitleLabel.bottomAnchor, constant: 6),
            familyStatusTableView.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.cardPadding + 4),
            familyStatusTableView.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -(MeridianLayout.cardPadding + 4)),
            familyStatusTableView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -8),

            emptyStateLabel.centerXAnchor.constraint(equalTo: familyStatusTableView.centerXAnchor),
            emptyStateLabel.centerYAnchor.constraint(equalTo: familyStatusTableView.centerYAnchor)
        ])
        refreshStatusButton.layer.borderWidth = 0.5
        refreshStatusButton.layer.borderColor = MeridianPalette.border.cgColor

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

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        enforceMeridianCompactNavigationBar()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if session == nil {
            Task {
                do {
                    session = try await APIService.shared.getSession()
                    await loadCheckins()
                } catch {
                    await MainActor.run { statusLabel.text = "Session lost. Log in again." }
                }
            }
        } else {
            Task { await loadCheckins() }
        }
    }

    private func loadCheckins() async {
        let s: SessionInfo
        if let existingSession = session {
            s = existingSession
        } else {
            do {
                let fetchedSession = try await APIService.shared.getSession()
                await MainActor.run { self.session = fetchedSession }
                s = fetchedSession
            } catch {
                await MainActor.run {
                    self.statusLabel.text = "Session lost. Log in again."
                    self.statusLabel.textColor = .systemRed
                }
                return
            }
        }
        do {
            let list = try await APIService.shared.getCheckins(familyCircleId: s.familyCircleId)
            await MainActor.run {
                checkins = list
                updateFamilyStatusUI()
            }
        } catch {
            await MainActor.run {
                checkins = []
                updateFamilyStatusUI()
            }
        }
    }

    private func updateFamilyStatusUI() {
        emptyStateLabel.isHidden = !checkins.isEmpty
        familyStatusTableView.reloadData()
        updateFamilyMap()
    }

    private func updateFamilyMap() {
        familyMapView.removeAnnotations(familyMapView.annotations)
        let validCheckins = checkins.filter { $0.latitude != nil && $0.longitude != nil }
        for checkIn in validCheckins {
            guard let lat = checkIn.latitude, let lon = checkIn.longitude else { continue }
            let pin = MKPointAnnotation()
            pin.coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lon)
            pin.title = checkIn.contactName
            pin.subtitle = checkIn.locationName ?? "Unknown location"
            familyMapView.addAnnotation(pin)
        }
        guard !validCheckins.isEmpty else { return }
        if validCheckins.count == 1, let first = validCheckins.first,
           let lat = first.latitude, let lon = first.longitude {
            let center = CLLocationCoordinate2D(latitude: lat, longitude: lon)
            let region = MKCoordinateRegion(center: center, span: MKCoordinateSpan(latitudeDelta: 0.04, longitudeDelta: 0.04))
            familyMapView.setRegion(region, animated: true)
            return
        }
        familyMapView.showAnnotations(familyMapView.annotations, animated: true)
    }

    @objc private func doCheckIn() {
        guard let s = session else {
            statusLabel.text = "Session lost. Log in again."
            statusLabel.textColor = .systemRed
            return
        }

        statusLabel.text = "Getting location…"
        statusLabel.textColor = .secondaryLabel
        manualCheckInButton.isEnabled = false
        pendingCheckInSession = s

        let workItem = DispatchWorkItem { [weak self] in
            Task { @MainActor in
                guard let self = self, self.pendingCheckInSession != nil else { return }
                self.pendingCheckInSession = nil
                self.statusLabel.text = "Location request timed out. Set a simulated location in Xcode (Debug → Simulate Location) or try on a device."
                self.statusLabel.textColor = .systemRed
                self.manualCheckInButton.isEnabled = true
            }
        }
        locationTimeoutWorkItem?.cancel()
        locationTimeoutWorkItem = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + locationTimeoutSeconds, execute: workItem)

        switch locationManager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            locationManager.requestLocation()
        case .notDetermined:
            locationManager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            locationTimeoutWorkItem?.cancel()
            locationTimeoutWorkItem = nil
            pendingCheckInSession = nil
            statusLabel.text = "Location access denied. Enable it in Settings."
            statusLabel.textColor = .systemRed
            manualCheckInButton.isEnabled = true
        @unknown default:
            locationTimeoutWorkItem?.cancel()
            locationTimeoutWorkItem = nil
            pendingCheckInSession = nil
            statusLabel.text = "Location unavailable"
            statusLabel.textColor = .systemRed
            manualCheckInButton.isEnabled = true
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
                    manualCheckInButton.isEnabled = true
                    Task { await loadCheckins() }
                }
            } catch {
                await MainActor.run {
                    statusLabel.text = error.localizedDescription
                    statusLabel.textColor = .systemRed
                    manualCheckInButton.isEnabled = true
                }
            }
        }
    }

    @objc private func refreshFamilyStatusTapped() {
        Task { await loadCheckins() }
    }
}

extension CheckInViewController: CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard pendingCheckInSession != nil else { return }
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            manager.requestLocation()
        case .denied, .restricted:
            locationTimeoutWorkItem?.cancel()
            locationTimeoutWorkItem = nil
            pendingCheckInSession = nil
            statusLabel.text = "Location access denied. Enable it in Settings."
            statusLabel.textColor = .systemRed
            manualCheckInButton.isEnabled = true
        default:
            break
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last, let s = pendingCheckInSession else { return }
        locationTimeoutWorkItem?.cancel()
        locationTimeoutWorkItem = nil
        pendingCheckInSession = nil
        performCheckIn(loc: loc, session: s)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        locationTimeoutWorkItem?.cancel()
        locationTimeoutWorkItem = nil
        pendingCheckInSession = nil
        statusLabel.text = "Location unavailable: \(error.localizedDescription)"
        statusLabel.textColor = .systemRed
        manualCheckInButton.isEnabled = true
    }
}

extension CheckInViewController: UITableViewDataSource, UITableViewDelegate {
    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        checkins.count
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let identifier = "FamilyStatusCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier) ??
            UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

        let checkIn = checkins[indexPath.row]
        let locationText = checkIn.locationName ?? "Unknown location"
        let timestampText = Self.dateFormatter.string(from: checkIn.timestamp)
        cell.textLabel?.text = checkIn.contactName
        cell.textLabel?.textColor = MeridianPalette.primaryText
        cell.detailTextLabel?.text = "\(locationText) • \(timestampText)"
        cell.detailTextLabel?.textColor = MeridianPalette.mutedText
        cell.selectionStyle = .none
        return cell
    }
}
