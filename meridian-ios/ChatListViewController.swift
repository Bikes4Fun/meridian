/**
 * Meridian iOS – Chat contact list. Tap opens chat in WKWebView.
 */
import UIKit

final class ChatListViewController: UIViewController {
    private let tableView = UITableView(frame: .zero, style: .insetGrouped)
    private var contacts: [Contact] = []
    private var session: SessionInfo?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        title = "Chat"

        tableView.dataSource = self
        tableView.delegate = self
        tableView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(tableView)
        NSLayoutConstraint.activate([
            tableView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            tableView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            tableView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            tableView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])

        Task { await loadSessionAndContacts() }
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

    private func openChat(recipient: Contact) {
        guard let s = session, let sb = recipient.sendbirdUserId else { return }
        let chatVC = ChatWebViewController()
        chatVC.loadChat(recipientSendbirdUserId: sb, recipientDisplayName: recipient.displayName)
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
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        openChat(recipient: contacts[indexPath.row])
    }
}
