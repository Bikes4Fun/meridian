/**
 * Meridian iOS – Chat contact list. Tap opens chat in WKWebView.
 */
import UIKit

final class ChatListViewController: UIViewController {
    private let tableView = UITableView(frame: .zero, style: .insetGrouped)
    private let statusLabel = UILabel()
    private var contacts: [Contact] = []
    private var session: SessionInfo?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = MeridianPalette.background

        tableView.dataSource = self
        tableView.delegate = self
        tableView.backgroundColor = .clear
        tableView.alwaysBounceVertical = true
        tableView.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(tableView)
        NSLayoutConstraint.activate([
            tableView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            tableView.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: MeridianLayout.cardPadding + 4),
            tableView.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -(MeridianLayout.cardPadding + 4)),
            tableView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -8)
        ])

        Task { await loadSessionAndContacts() }
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
        if session == nil { Task { await loadSessionAndContacts() } }
    }

    private func loadSessionAndContacts() async {
        do {
            let s = try await APIService.shared.getSession()
            await MainActor.run { session = s }
            let list = try await APIService.shared.getContacts(familyCircleId: s.familyCircleId)
            await MainActor.run {
                contacts = list
                tableView.reloadData()
            }
        } catch {
            await MainActor.run {
                contacts = []
                tableView.reloadData()
            }
        }
    }

    private func openChat(recipient: Contact, autoStartCall: Bool = false) {
        // guard session != nil, let sb = recipient.send birdUserId else { return } // TODO: remove all reference to send bird
        if autoStartCall, let targetUserId = recipient.userId, !targetUserId.isEmpty {
            Task {
                try? await APIService.shared.requestCall(toUserId: targetUserId)
            }
        }
        let chatVC = ChatWebViewController()
        chatVC.loadChat(
            // recipientSend birdUserId: sb, TODO: remove all reference to send bird
            recipientDisplayName: recipient.displayName,
            autoStartCall: autoStartCall
        )
        let nav = UINavigationController(rootViewController: chatVC)
        if traitCollection.horizontalSizeClass == .compact {
            nav.modalPresentationStyle = .fullScreen
        }
        present(nav, animated: true)
    }

}

extension ChatListViewController: UITableViewDataSource, UITableViewDelegate {
    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        contacts.count
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let id = "Contact"
        let cell = tableView.dequeueReusableCell(withIdentifier: id) ?? UITableViewCell(style: .subtitle, reuseIdentifier: id)
        let c = contacts[indexPath.row]
        cell.textLabel?.text = c.displayName
        cell.textLabel?.textColor = MeridianPalette.primaryText
        cell.detailTextLabel?.text = "Tap for call/chat actions"
        cell.detailTextLabel?.textColor = MeridianPalette.mutedText
        cell.accessoryType = .detailButton
        return cell
    }

    func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        let recipient = contacts[indexPath.row]
        let sheet = UIAlertController(title: recipient.displayName, message: nil, preferredStyle: .actionSheet)
        sheet.addAction(UIAlertAction(title: "Place Call", style: .default) { [weak self] _ in
            self?.openChat(recipient: recipient, autoStartCall: true)
        })
        sheet.addAction(UIAlertAction(title: "Open Chat", style: .default) { [weak self] _ in
            self?.openChat(recipient: recipient, autoStartCall: false)
        })
        sheet.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        if let popover = sheet.popoverPresentationController {
            popover.sourceView = tableView
            popover.sourceRect = tableView.rectForRow(at: indexPath)
        }
        present(sheet, animated: true)
    }
}
