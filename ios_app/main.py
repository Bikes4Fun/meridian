"""
Minimal Meridian iOS app: Start Alert, End Alert. POSTs to kiosk API.
"""
import json
import os
import urllib.request
import ssl
import threading

from kivy.clock import Clock

API_URL = os.getenv("MERIDIAN_API_URL", "http://127.0.0.1:8000")
API_USER_ID = os.getenv("MERIDIAN_API_USER_ID", "fm_005")
API_FAMILY_CIRCLE_ID = os.getenv("MERIDIAN_API_FAMILY_CIRCLE_ID", "F00000")

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.metrics import dp


def _post_alert(activated, on_result):
    def _worker():
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
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                body = resp.read().decode()
                data = json.loads(body)
                msg = f"Success: {data}"
        except Exception as e:
            msg = f"Error: {e}"
        Clock.schedule_once(lambda dt: on_result(msg))
    threading.Thread(target=_worker, daemon=True).start()


class MeridianAlertApp(App):
    def build(self):
        Window.clearcolor = (0.98, 0.98, 0.96, 1)
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))

        root.add_widget(BoxLayout(size_hint_y=1))

        btn_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(16))
        start_btn = Button(
            text="Start Alert",
            font_size="28sp",
            size_hint_y=None,
            height=dp(72),
            background_color=(0.9, 0.25, 0.2, 1),
            background_normal="",
            background_down="",
        )
        end_btn = Button(
            text="End Alert",
            font_size="28sp",
            size_hint_y=None,
            height=dp(72),
            background_color=(0.5, 0.5, 0.5, 1),
            background_normal="",
            background_down="",
        )
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
