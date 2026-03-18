"""
Application factory for Meridian Kiosk (pywebview).
Creates and configures the pywebview app with KioskBridge for Python↔JS communication.

CLIENT vs SERVER:
- This module is used only by the client. api_url determines where services come from
  via api_client.create_kiosk_remote(); container is not used.

SERVER DEPLOYMENT: app_factory.py is not needed on the server.
"""

import json
import logging
import os
import threading
import time
from typing import Optional

from shared.config import (
    get_kiosk_tv_fullscreen,
    get_kiosk_tv_mode,
    get_kiosk_window_size,
)

from .api_client import create_kiosk_remote
from .events_handler import EventsHandler

logger = logging.getLogger(__name__)

NAV_BUTTONS = [
    {"text": "Home", "screen": "home"},
    {"text": "Emergency", "screen": "emergency"},
    {"text": "Family", "screen": "family"},
    {"text": "Chat", "screen": "chat"},
]


class KioskBridge:
    """Exposed to JS as pywebview.api. Delegates to screen handlers."""

    def __init__(self, app):
        self._app = app
        self._events = EventsHandler(app)

    def navigate(self, screen_name: str):
        """Switch to screen. Called from JS nav click handler."""
        logger.info(f"Nav: {screen_name}")
        self._app._navigate_to(screen_name)

    def open_chat(self, sendbird_user_id: str, display_name: str):
        """Open chat window for contact. Called from JS contact click."""
        logger.info(f"Open chat: {display_name} ({sendbird_user_id})")
        self._app._open_chat(sendbird_user_id, display_name)

    def print_emergency(self):
        """Print emergency document. Called from JS Print button."""
        logger.info("Print emergency (button)")
        self._app._print_emergency()

    def refresh_events(self):
        """Refresh home schedule. Called from JS after event change."""
        self._app._load_home_schedule()

    def open_add_event_modal(self) -> None:
        self._events.open_add_event_modal()

    def edit_event(self, event_data_json: str) -> None:
        self._events.edit_event(event_data_json)

    def submit_event_form(self, payload_json: str) -> str:
        return self._events.submit_event_form(payload_json)

    def add_event(self, payload_json: str) -> str:
        return self._events.add_event(payload_json)

    def update_event(self, event_id: str, payload_json: str) -> str:
        return self._events.update_event(event_id, payload_json)

    def delete_event(self, event_id: str) -> str:
        return self._events.delete_event(event_id)


class MeridianKioskApp:
    """Pywebview kiosk app. Python drives data and HTML; JS is thin bridge."""

    def __init__(self, services, api_url: str, kiosk_user_id: str, family_circle_id: str):
        self.services = services
        self.api_url = api_url
        self.kiosk_user_id = kiosk_user_id
        self.family_circle_id = family_circle_id
        self._window = None
        self._bridge = None
        self._alert_was_activated = False

    def run(self):
        """Create window, wire bridge, start webview loop."""
        import webview

        web_dir = os.path.join(os.path.dirname(__file__), "web")
        html_path = os.path.join(web_dir, "kiosk.html")
        url = "file://" + os.path.abspath(html_path).replace("\\", "/")

        w, h = get_kiosk_window_size()
        x, y = 10, 120
        frameless = False
        fullscreen = False
        if get_kiosk_tv_mode():
            from shared.config import get_kiosk_tv_position

            x, y = get_kiosk_tv_position()
            frameless = True
            fullscreen = get_kiosk_tv_fullscreen()
        self._bridge = KioskBridge(self)
        self._window = webview.create_window(
            "Meridian Kiosk",
            url,
            width=w,
            height=h,
            x=x,
            y=y,
            resizable=False,
            frameless=frameless,
            fullscreen=fullscreen,
            js_api=self._bridge,
        )

        def on_loaded(*args, **kwargs):
            threading.Thread(target=self._on_ready, daemon=True).start()

        self._window.events.loaded += on_loaded
        webview.start()

    def _eval(self, js: str):
        """Run JS in webview. Handles threading/platform quirks."""
        try:
            self._window.evaluate_js(js)
        except Exception as e:
            logger.debug(f"evaluate_js failed: {e}")

    def _navigate_to(self, screen_name: str):
        """Show screen by name. Builds HTML and calls showScreen."""
        try:
            logger.info(f"Building screen: {screen_name}")
            html, extra = self._build_screen_html(screen_name)
            escaped = json.dumps(html)
            self._eval(f"showScreen({json.dumps(screen_name)}, {escaped})")
            if extra:
                self._eval(extra)
        except Exception as e:
            logger.exception(f"navigate failed: {e}")

    def _build_screen_html(self, screen_name: str) -> tuple[str, Optional[str]]:
        """Build HTML for screen. Returns (html, extra_js) where extra_js runs after showScreen (e.g. initMap)."""
        from . import html_primitives as hp

        if screen_name == "home":
            from .home_screen import build_home_html
            return build_home_html(
                self.services, self.api_url,
                family_circle_id=self.family_circle_id,
                kiosk_user_id=self.kiosk_user_id,
            ), None

        if screen_name == "emergency":
            from .emergency_screen import build_emergency_html
            return build_emergency_html(self.services, self.api_url), None

        if screen_name == "family":
            from .checkin_screen import build_checkin_html
            html, markers_json = build_checkin_html(
                self.services, self.api_url, self.family_circle_id
            )
            return html, f"initMap({json.dumps(markers_json)})"

        if screen_name == "chat":
            from .chat_screen import build_chat_html
            return build_chat_html(
                self.services, self.api_url, self.kiosk_user_id, self.family_circle_id
            ), None

        if screen_name == "medications":
            from .medications_screen import build_medications_html
            return build_medications_html(self.services, self.api_url), None

        if screen_name == "schedule":
            from .events_handler import build_schedule_html
            return build_schedule_html(self.services, self.api_url), None

        return hp.error_state("Unknown screen"), None

    def _open_chat(self, sendbird_user_id: str, display_name: str):
        """Fetch chat URL and open in webview."""
        entry_svc = self.services.get("chat_entry_service")
        if not entry_svc:
            logger.warning("open_chat: no chat_entry_service")
            return
        r = entry_svc.get_entry_url(
            recipient_sendbird_user_id=sendbird_user_id,
            recipient_display_name=display_name,
        )
        if r.success and r.data:
            from .webview import open_chat_window

            open_chat_window(r.data)
        else:
            logger.warning(f"open_chat: get_entry_url failed: {getattr(r, 'error', None)}")

    def _print_emergency(self):
        """Trigger emergency print (same flow as alert-activated)."""
        from .emergency_print import trigger_emergency_print

        trigger_emergency_print(self.services)

    def _on_ready(self):
        """Runs in background thread after load. Initial screen, clock, meds, events, alerts."""
        logger.info("Kiosk loaded, initializing...")
        time.sleep(0.3)
        self._navigate_to("home")
        self._refresh_clock()
        self._start_clock_tick()
        self._start_alert_poll()

    def _refresh_clock(self):
        """Full clock update: day, date, year, time, time-of-day."""
        time_svc = self.services.get("time_service")
        if not time_svc:
            return
        self._eval_el("clock-day", time_svc.get_dayof_week().upper())
        self._eval_el("clock-date", time_svc.get_month_day())
        self._eval_el("clock-year", time_svc.get_year())
        self._eval_el("clock-time", time_svc.get_time())
        self._eval_el("clock-period", time_svc.get_am_pm().upper())

    def _eval_el(self, el_id: str, content: str):
        """Update element by id."""
        self._eval(f"updateEl({json.dumps(el_id)}, {json.dumps(content)})")

    def _start_clock_tick(self):
        """Per-second clock tick in background."""
        while True:
            time.sleep(1)
            time_svc = self.services.get("time_service")
            if not time_svc:
                continue
            self._eval_el("clock-time", time_svc.get_time())
            self._eval_el("clock-period", time_svc.get_am_pm().upper())

    def _load_home_schedule(self):
        """Update Up Next and timeline. Fetches data via home_screen, pushes to webview."""
        from .home_screen import build_timeline_html, build_up_next_html, load_schedule_items

        items, now = load_schedule_items(self.services)
        self._eval_el("up_next_content", build_up_next_html(items, now))
        self._eval_el("timeline_content", build_timeline_html(items))

    def _start_alert_poll(self):
        """Poll alert; when activated, switch to emergency, add flash, trigger print."""
        from .emergency_print import trigger_emergency_print

        while True:
            time.sleep(2)
            alert_svc = self.services.get("alert_service")
            if not alert_svc:
                continue
            result = alert_svc.get_alert_status()
            if not result.success or not result.data:
                continue
            activated = result.data.get("activated", False)
            self.services.get("_alert_activated", [False])[0] = activated
            if activated:
                self._navigate_to("emergency")
                self._eval("document.body.classList.add('alert-active')")
                if not self._alert_was_activated:
                    time.sleep(0.5)
                    trigger_emergency_print(self.services)
            else:
                self._eval("document.body.classList.remove('alert-active')")
            self._alert_was_activated = activated


def create_app(
    kiosk_user_id: str, family_circle_id: str, api_url: str = None
) -> MeridianKioskApp:
    """Create the Meridian Kiosk. api_url, kiosk_user_id, family_circle_id required."""
    if not api_url:
        raise ValueError("api_url required.")
    if not kiosk_user_id or not family_circle_id:
        raise ValueError("kiosk_user_id and family_circle_id required.")
    try:
        import requests

        session = requests.Session()
    except ImportError:
        session = None
    services = create_kiosk_remote(
        api_url,
        kiosk_user_id=kiosk_user_id,
        family_circle_id=family_circle_id,
        session=session,
    )
    return MeridianKioskApp(
        services=services,
        api_url=api_url,
        kiosk_user_id=kiosk_user_id,
        family_circle_id=family_circle_id,
    )
