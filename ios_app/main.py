"""
Minimal Meridian iOS app: Start Alert, End Alert. POSTs to kiosk API.

API URL resolution: 1) MERIDIAN_API_URL env, 2) --local flag, 3) Railway (api_config), 4) local network URLs.
Run locally: python main.py -- --local  (use http://127.0.0.1:8000)
"""
import json
import logging
import os
import sys
import urllib.request

if "--local" in sys.argv:
    os.environ.setdefault("MERIDIAN_API_URL", "http://127.0.0.1:8000")

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger(__name__)
import ssl
import threading

from kivy.clock import Clock

API_USER_ID = os.getenv("MERIDIAN_API_USER_ID", "fm_005")


def _ssl_context():
    """SSL context for HTTPS. On iOS, try certifi's CA bundle if available; else use unverified (common kivy-ios limitation)."""
    if os.getenv("KIVY_BUILD") == "ios":
        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
    return ssl.create_default_context()
API_FAMILY_CIRCLE_ID = os.getenv("MERIDIAN_API_FAMILY_CIRCLE_ID", "F00000")


def _load_api_config():
    """Load api_config.json from src/shared, script dir, or cwd (YourApp after chdir)."""
    bases = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "shared"),
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
    ]
    for base in bases:
        path = os.path.join(base, "api_config.json")
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
    return {}


def _probe_health(url, timeout=3.0):
    """Return True if /api/health responds 200."""
    try:
        req = urllib.request.Request(url.rstrip("/") + "/api/health")
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            return resp.status == 200
    except Exception:
        return False


def _resolve_api_url():
    """Resolve API URL: env, Railway, local_network_urls, localhost. On iOS, Railway used even if health probe fails (simulator quirk)."""
    env_url = (os.getenv("MERIDIAN_API_URL") or "").strip()
    if env_url:
        return env_url.rstrip("/")
    cfg = _load_api_config()
    railway_url = (cfg.get("railway_api_url") or os.getenv("RAILWAY_API_URL") or "").strip()
    if railway_url:
        if _probe_health(railway_url):
            return railway_url.rstrip("/")
        if os.getenv("KIVY_BUILD") == "ios":
            return railway_url.rstrip("/")
        logger.info("Railway unreachable, trying local fallbacks")
    for url in (cfg.get("local_network_urls") or []):
        u = (url or "").strip()
        if u and _probe_health(u, timeout=2.0):
            return u.rstrip("/")
    fallback = (cfg.get("fallback_api_url") or "http://127.0.0.1:8000").strip()
    return fallback.rstrip("/")


API_URL = _resolve_api_url()
logger.info("Using API: %s", API_URL)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.metrics import dp


def _post_alert(activated, on_result):
    def _worker():
        url = API_URL.rstrip("/") + "/api/emergency/alert"
        logger.info("API POST %s activated=%s", url, activated)
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({"activated": activated}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-User-Id": API_USER_ID,
                    "X-Family-Circle-Id": API_FAMILY_CIRCLE_ID,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5, context=_ssl_context()) as resp:
                body = resp.read().decode()
                data = json.loads(body)
                msg = f"Success: {data}"
                logger.info("API response: %s", body)
        except Exception as e:
            msg = f"Error: {e}"
            logger.info("API error: %s", e)
        Clock.schedule_once(lambda dt: on_result(msg))
    threading.Thread(target=_worker, daemon=True).start()


class MeridianAlertApp(App):
    def build(self):
        Window.clearcolor = (0.98, 0.98, 0.96, 1)
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))

        root.add_widget(BoxLayout(size_hint_y=1))

        btn_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(16))
        start_colors = {"normal": (0.9, 0.25, 0.2, 1), "down": (0.7, 0.18, 0.15, 1)}
        start_btn = Button(
            text="Start Alert",
            font_size="28sp",
            size_hint_y=None,
            height=dp(72),
            background_color=start_colors["normal"],
            background_normal="",
            background_down="",
        )
        start_btn.bind(state=lambda b, v: setattr(b, "background_color", start_colors.get(v, start_colors["normal"])))

        end_colors = {"normal": (0.5, 0.5, 0.5, 1), "down": (0.35, 0.35, 0.35, 1)}
        end_btn = Button(
            text="End Alert",
            font_size="28sp",
            size_hint_y=None,
            height=dp(72),
            background_color=end_colors["normal"],
            background_normal="",
            background_down="",
        )
        end_btn.bind(state=lambda b, v: setattr(b, "background_color", end_colors.get(v, end_colors["normal"])))
        response_label = Label(
            text="",
            size_hint_y=None,
            height=dp(60),
            halign="center",
        )
        response_label.bind(size=lambda w, sz: setattr(w, "text_size", sz))

        def on_result(msg):
            response_label.text = msg

        start_btn.bind(on_press=lambda _: _post_alert(True, on_result))
        end_btn.bind(on_press=lambda _: _post_alert(False, on_result))

        btn_box.add_widget(start_btn)
        btn_box.add_widget(end_btn)
        btn_box.add_widget(response_label)
        root.add_widget(btn_box)

        root.add_widget(BoxLayout(size_hint_y=1))

        return root


if __name__ == "__main__":
    MeridianAlertApp().run()
