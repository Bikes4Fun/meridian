"""
Minimal Meridian iOS app: Start Alert, End Alert. POSTs to kiosk API.
"""
import json
import urllib.request
import ssl

API_URL = "http://127.0.0.1:8000"
API_USER_ID = "fm_005"
API_FAMILY_CIRCLE_ID = "F00000"

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.metrics import dp


def _post_alert(activated):
    try:
        req = urllib.request.Request(
            API_URL.rstrip("/") + "/api/emergency/alert",
            data=json.dumps({"activated": activated}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-User-Id": API_USER_ID,
                "X-Family-Circle-Id": API_FAMILY_CIRCLE_ID,
            },
            method="POST",
        )
        ctx = ssl.create_default_context()
        urllib.request.urlopen(req, timeout=5, context=ctx)
    except Exception:
        pass


class MeridianAlertApp(App):
    def build(self):
        Window.clearcolor = (0.98, 0.98, 0.96, 1)
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))

        start_btn = Button(
            text="Start Alert",
            font_size="28sp",
            size_hint_y=None,
            height=dp(72),
            background_color=(0.9, 0.25, 0.2, 1),
            background_normal="",
            background_down="",
        )
        start_btn.bind(on_press=lambda _: _post_alert(True))

        end_btn = Button(
            text="End Alert",
            font_size="28sp",
            size_hint_y=None,
            height=dp(72),
            background_color=(0.5, 0.5, 0.5, 1),
            background_normal="",
            background_down="",
        )
        end_btn.bind(on_press=lambda _: _post_alert(False))

        root.add_widget(start_btn)
        root.add_widget(end_btn)

        root.add_widget(BoxLayout(size_hint_y=1))

        return root


if __name__ == "__main__":
    MeridianAlertApp().run()
