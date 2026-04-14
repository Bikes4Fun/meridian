/**
 * DEBUG-only: accept mkcert / dev HTTPS on loopback and RFC1918 LAN without installing
 * mkcert's root CA in the Simulator trust store. Not compiled into Release.
 */
import Foundation
#if DEBUG
import WebKit

enum LocalDevNetwork {
    static func allowsInsecureDevTLS(forHost host: String) -> Bool {
        let h = host.lowercased()
        if h == "localhost" { return true }
        if h == "127.0.0.1" { return true }
        let parts = h.split(separator: ".").compactMap { Int($0) }
        guard parts.count == 4 else { return false }
        let a = parts[0], b = parts[1]
        if a == 10 { return true }
        if a == 172 && b >= 16 && b <= 31 { return true }
        if a == 192 && b == 168 { return true }
        return false
    }
}

final class LocalDevURLSessionDelegate: NSObject, URLSessionDelegate {
    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let trust = challenge.protectionSpace.serverTrust,
              LocalDevNetwork.allowsInsecureDevTLS(forHost: challenge.protectionSpace.host) else {
            completionHandler(.performDefaultHandling, nil)
            return
        }
        completionHandler(.useCredential, URLCredential(trust: trust))
    }
}

final class LocalDevWebViewNavigationDelegate: NSObject, WKNavigationDelegate {
    func webView(
        _ webView: WKWebView,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let trust = challenge.protectionSpace.serverTrust,
              LocalDevNetwork.allowsInsecureDevTLS(forHost: challenge.protectionSpace.host) else {
            completionHandler(.performDefaultHandling, nil)
            return
        }
        completionHandler(.useCredential, URLCredential(trust: trust))
    }
}
#endif
