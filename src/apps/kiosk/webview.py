"""Open URLs in a webview. Kiosk uses this for chatapp (opened via session-url)."""

import subprocess
import sys


def open_chat_window(url):
    """Open URL in pywebview. Uses subprocess to avoid blocking the main kiosk window."""
    if not url:
        return
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys, webview; webview.create_window('Family Chat', sys.argv[1], width=800, height=600); webview.start()",
                url,
            ]
        )
    except Exception:
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
