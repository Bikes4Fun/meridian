/**
 * Meridian iOS – Check-in. GPS check-in. Shows recent family check-ins.
 */
import UIKit
import CoreLocation
import MapKit

final class CheckInViewController: UIViewController {
    private let familySummaryLabel = UILabel()
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
        view.backgroundColor = MeridianPalette.background

        familySummaryLabel.text = "Family map live · 0 active members"
        familySummaryLabel.font = .preferredFont(forTextStyle: .footnote)
        familySummaryLabel.textColor = MeridianPalette.mutedText
        familySummaryLabel.textAlignment = .center

        manualCheckInButton.applyMeridianButtonStyle(.primary, title: "Checkin")
        manualCheckInButton.addTarget(self, action: #selector(doCheckIn), for: .touchUpInside)

        refreshStatusButton.applyMeridianButtonStyle(.bordered, title: "Refresh")
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
        if #available(iOS 15.0, *) {
            familyStatusTableView.sectionHeaderTopPadding = 0
        }
        familyStatusTableView.alwaysBounceVertical = true
        familyStatusTableView.translatesAutoresizingMaskIntoConstraints = false

        familyMapView.layer.cornerRadius = 0
        familyMapView.layer.masksToBounds = false
        familyMapView.layer.borderWidth = 0
        familyMapView.showsCompass = false
        familyMapView.delegate = self

        emptyStateLabel.text = "No family check-ins yet."
        emptyStateLabel.textAlignment = .center
        emptyStateLabel.textColor = MeridianPalette.mutedText
        emptyStateLabel.font = .preferredFont(forTextStyle: .subheadline)
        emptyStateLabel.isHidden = true

        let buttonsRow = UIStackView(arrangedSubviews: [manualCheckInButton, refreshStatusButton])
        buttonsRow.axis = .horizontal
        buttonsRow.spacing = 8
        buttonsRow.distribution = .fillEqually
        buttonsRow.alignment = .fill

        let controlsStack = UIStackView(arrangedSubviews: [
            familySummaryLabel,
            buttonsRow,
            statusLabel
        ])
        controlsStack.axis = .vertical
        controlsStack.spacing = 6
        controlsStack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(controlsStack)
        view.addSubview(familyMapView)
        view.addSubview(familyStatusTableView)
        familyStatusTableView.addSubview(emptyStateLabel)
        emptyStateLabel.translatesAutoresizingMaskIntoConstraints = false
        familyMapView.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            manualCheckInButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),
            refreshStatusButton.heightAnchor.constraint(equalToConstant: MeridianLayout.buttonHeight),

            controlsStack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 6),
            controlsStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.cardPadding + 4),
            controlsStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -(MeridianLayout.cardPadding + 4)),

            familyMapView.topAnchor.constraint(equalTo: controlsStack.bottomAnchor, constant: 6),
            familyMapView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            familyMapView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            familyMapView.heightAnchor.constraint(equalToConstant: 310),

            familyStatusTableView.topAnchor.constraint(equalTo: familyMapView.bottomAnchor, constant: 2),
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
        navigationController?.setNavigationBarHidden(true, animated: false)
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        navigationController?.setNavigationBarHidden(false, animated: false)
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
                statusLabel.text = "Could not load family check-ins."
                statusLabel.textColor = .systemRed
                updateFamilyStatusUI()
            }
        }
    }

    private func updateFamilyStatusUI() {
        emptyStateLabel.isHidden = !checkins.isEmpty
        familySummaryLabel.text = "Family map live · \(checkins.count) active member\(checkins.count == 1 ? "" : "s")"
        familyStatusTableView.reloadData()
        updateFamilyMap()
    }

    private func updateFamilyMap() {
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
        Task {
            do {
                try await APIService.shared.checkIn(
                    familyCircleId: session.familyCircleId,
                    userId: session.userId,
                    latitude: loc.coordinate.latitude,
                    longitude: loc.coordinate.longitude,
                    notes: nil
                )
                await MainActor.run {
                    statusLabel.text = "✓ Check-in successful"
                    statusLabel.textColor = .systemGreen
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
        cell.textLabel?.font = .preferredFont(forTextStyle: .headline)
        cell.textLabel?.textColor = MeridianPalette.primaryText
        cell.detailTextLabel?.text = "\(locationText) • \(timestampText)"
        cell.detailTextLabel?.font = .preferredFont(forTextStyle: .footnote)
        cell.detailTextLabel?.textColor = MeridianPalette.mutedText
        cell.selectionStyle = .none
        cell.accessoryType = .disclosureIndicator
        return cell
    }
}

extension CheckInViewController: MKMapViewDelegate {
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
