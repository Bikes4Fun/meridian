/**
 * Meridian iOS – Chat in WKWebView. Loads server chat URL (Sendbird).
 */
import UIKit
import WebKit

final class ChatWebViewController: UIViewController {
    private let webView: WKWebView
    private let closeButton = UIBarButtonItem(systemItem: .done)

    override init(nibName nibNameOrNil: String?, bundle nibBundleOrNil: Bundle?) {
        let config = WKWebViewConfiguration()
        let script = WKUserScript(
            source: """
            (function() {
                var meta = document.querySelector('meta[name=viewport]');
                var content = (meta && meta.getAttribute('content')) || '';
                if (content.indexOf('viewport-fit=cover') === -1) {
                    content += (content ? ',' : '') + 'viewport-fit=cover';
                    if (meta) meta.setAttribute('content', content);
                    else {
                        meta = document.createElement('meta');
                        meta.name = 'viewport';
                        meta.content = content;
                        document.head.appendChild(meta);
                    }
                }
                var s = document.createElement('style');
                s.textContent = 'body{padding-bottom:max(env(safe-area-inset-bottom),60px)!important}html{min-height:100%}';
                document.head.appendChild(s);
            })();
            """,
            injectionTime: .atDocumentEnd,
            forMainFrameOnly: true
        )
        config.userContentController.addUserScript(script)
        webView = WKWebView(frame: .zero, configuration: config)
        super.init(nibName: nibNameOrNil, bundle: nibBundleOrNil)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        navigationItem.rightBarButtonItem = closeButton
        closeButton.target = self
        closeButton.action = #selector(closeTapped)

        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
    }

    func loadChat(recipientSendbirdUserId: String, recipientDisplayName: String, familyCircleId: String) {
        Task {
            do {
                let url = try await APIService.shared.getChatSessionURL(
                    familyCircleId: familyCircleId,
                    recipientSendbirdUserId: recipientSendbirdUserId,
                    recipientDisplayName: recipientDisplayName
                )
                await MainActor.run {
                    webView.load(URLRequest(url: url))
                }
            } catch {
                await MainActor.run {
                    let alert = UIAlertController(
                        title: "Chat Error",
                        message: error.localizedDescription,
                        preferredStyle: .alert
                    )
                    alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self] _ in
                        self?.dismiss(animated: true)
                    })
                    present(alert, animated: true)
                }
            }
        }
    }

    @objc private func closeTapped() {
        dismiss(animated: true)
    }
}
