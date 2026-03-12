"""Open URLs in a webview. Kiosk uses this for chatapp (opened via session-url)."""


def open_chat_window(url):
    """Open URL in webview (pywebview). Falls back to webbrowser if pywebview unavailable."""
    if not url:
        return
    try:
        import webview

        webview.create_window("Family Chat", url, width=800, height=600)
        webview.start()
    except ImportError:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        import webbrowser

        webbrowser.open(url)
