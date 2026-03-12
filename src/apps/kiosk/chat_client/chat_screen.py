"""
Chat screen: open chat in an in-app window (pywebview). Session set via entry URL (localhost-only). See apps/chat/README.md.
"""


def open_chat_window(url):
    """Open chat in an in-app window (pywebview). Falls back to webbrowser if pywebview unavailable."""
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
