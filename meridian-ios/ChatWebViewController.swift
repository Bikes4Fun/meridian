/**
 * Meridian iOS – Chat in WKWebView. Loads server chat URL (Send bird).
 * Dynamically sized for all phone devices (iPhone SE through Max) with safe area and keyboard handling.
 */
import UIKit
import WebKit

final class ChatWebViewController: UIViewController {
    private let webView: WKWebView
    private let closeButton = UIBarButtonItem(systemItem: .done)
    private var keyboardObservers: [Any] = []
    private var shouldAutoStartCall = false

    private static let mobileStyleScript = """
    (function() {
        var inject = function() {
            var id = 'meridian-mobile-overrides';
            if (document.getElementById(id)) return;
            var s = document.createElement('style');
            s.id = id;
            s.textContent = 'html{min-height:100%;-webkit-text-size-adjust:100%}body{min-height:100vh;min-height:-webkit-fill-available;padding-bottom:max(80px,env(safe-area-inset-bottom))!important;box-sizing:border-box;display:flex!important;flex-direction:column!important}#chatHeader{font-size:clamp(1.1rem,4.5vw,1.5rem)!important;margin:0 0 4px 0!important}#messages{flex:1!important;min-height:120px!important}#sendRow{padding-bottom:max(16px,env(safe-area-inset-bottom))!important}*{box-sizing:border-box}';
            (document.head||document.documentElement).appendChild(s);
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
        else inject();
        setTimeout(inject, 500);
    })();
    """

    override init(nibName nibNameOrNil: String?, bundle nibBundleOrNil: Bundle?) {
        let config = WKWebViewConfiguration()
        let script = WKUserScript(
            source: """
            (function() {
                var meta = document.querySelector('meta[name=viewport]');
                var content = (meta && meta.getAttribute('content')) || '';
                if (content.indexOf('viewport-fit=cover') === -1) {
                    content += (content ? ',' : '') + 'viewport-fit=cover,width=device-width,initial-scale=1';
                    if (meta) meta.setAttribute('content', content);
                    else {
                        meta = document.createElement('meta');
                        meta.name = 'viewport';
                        meta.content = content;
                        document.head.appendChild(meta);
                    }
                }
                var s = document.createElement('style');
                s.textContent = 'html{min-height:100%;-webkit-text-size-adjust:100%}body{min-height:100vh;min-height:-webkit-fill-available;padding-bottom:max(80px,env(safe-area-inset-bottom))!important;box-sizing:border-box}*{box-sizing:inherit}';
                document.head.appendChild(s);
            })();
            """ + "\n" + ChatWebViewController.mobileStyleScript,
            injectionTime: .atDocumentEnd,
            forMainFrameOnly: true
        )
        config.userContentController.addUserScript(script)
        webView = WKWebView(frame: .zero, configuration: config)
        super.init(nibName: nibNameOrNil, bundle: nibBundleOrNil)
        webView.configuration.userContentController.add(self, name: "meridianLogger")
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    deinit {
        webView.configuration.userContentController.removeScriptMessageHandler(forName: "meridianLogger")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        navigationItem.rightBarButtonItem = closeButton
        closeButton.target = self
        closeButton.action = #selector(closeTapped)

        webView.navigationDelegate = self
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.scrollView.contentInsetAdjustmentBehavior = .automatic
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        setupKeyboardObservers()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        keyboardObservers.forEach { NotificationCenter.default.removeObserver($0) }
        keyboardObservers = []
    }

    private func setupKeyboardObservers() {
        let show = NotificationCenter.default.addObserver(
            forName: UIResponder.keyboardWillShowNotification,
            object: nil, queue: .main
        ) { [weak self] n in
            self?.keyboardWillChange(n)
        }
        let hide = NotificationCenter.default.addObserver(
            forName: UIResponder.keyboardWillHideNotification,
            object: nil, queue: .main
        ) { [weak self] n in
            self?.keyboardWillChange(n)
        }
        keyboardObservers = [show, hide]
    }

    private func keyboardWillChange(_ notification: Notification) {
        guard let userInfo = notification.userInfo,
              let frame = userInfo[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect,
              let duration = userInfo[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double else { return }
        let isShowing = notification.name == UIResponder.keyboardWillShowNotification
        let inset = isShowing ? frame.height : 0
        UIView.animate(withDuration: duration) { [weak self] in
            self?.webView.scrollView.contentInset = UIEdgeInsets(top: 0, left: 0, bottom: inset, right: 0)
            self?.webView.scrollView.verticalScrollIndicatorInsets = UIEdgeInsets(top: 0, left: 0, bottom: inset, right: 0)
        }
    }

    func loadChat(recipientSendbirdUserId: String, recipientDisplayName: String, autoStartCall: Bool = false) {
        shouldAutoStartCall = autoStartCall
        Task {
            do {
                let url = try await APIService.shared.getChatSessionURL(
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

extension ChatWebViewController: WKNavigationDelegate {
    func webView(
        _ webView: WKWebView,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        #if DEBUG
        if challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
           let trust = challenge.protectionSpace.serverTrust,
           LocalDevNetwork.allowsInsecureDevTLS(forHost: challenge.protectionSpace.host) {
            completionHandler(.useCredential, URLCredential(trust: trust))
            return
        }
        #endif
        completionHandler(.performDefaultHandling, nil)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.evaluateJavaScript(ChatWebViewController.mobileStyleScript)
        guard shouldAutoStartCall else { return }
        webView.evaluateJavaScript(
            """
            (function() {
                if (window.__meridianAutoCallStarted) return;
                window.__meridianAutoCallStarted = true;
                var tries = 0;
                var maxTries = 30;
                var timer = setInterval(function() {
                    tries += 1;
                    var row = document.getElementById('callRow');
                    var btn = document.getElementById('startVideoCallBtn');
                    if (!btn) {
                        if (tries >= maxTries) clearInterval(timer);
                        return;
                    }
                    var visible = true;
                    if (row) {
                        visible = row.style.display === 'flex' || row.style.display === 'block' || getComputedStyle(row).display !== 'none';
                    }
                    if (visible && !btn.disabled) {
                        btn.click();
                        clearInterval(timer);
                        return;
                    }
                    if (tries >= maxTries) clearInterval(timer);
                }, 500);
            })();
            """
        )
    }
}

extension ChatWebViewController: WKScriptMessageHandler {
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "meridianLogger" else { return }
        if let payload = message.body as? [String: Any],
           let data = try? JSONSerialization.data(withJSONObject: payload, options: []),
           let json = String(data: data, encoding: .utf8) {
            print("[MeridianCall] \(json)")
            return
        }
        print("[MeridianCall] \(message.body)")
    }
}
