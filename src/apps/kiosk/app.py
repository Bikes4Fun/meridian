"""
Meridian Kiosk client (pywebview): window/bridge, screen registry, background loops (clock, stove push, alert poll, incoming call).

Scope: orchestration and navigation; uses api_client.create_kiosk_remote() / KioskRemoteServiceContainer (not the server DB container).

Not here: per-screen HTML beyond dispatch; REST/Flask; database services. Server does not import this module.
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
    get_kiosk_webview_debug,
    get_kiosk_window_size,
)

from .api_client import KioskRemoteServiceContainer, create_kiosk_remote
from .communication import ChatHandler
from .map_screen import LocationHandler
from .schedule_screen import ScheduleHandler, build_schedule_html
from .health_screen import HealthHandler
from .sensor_widgets import SensorHandler

logger = logging.getLogger(__name__)

NAV_BUTTONS = [
    {"text": "Home", "screen": "home"},
    {"text": "Schedule", "screen": "schedule"},
    {"text": "Family", "screen": "family"},
    {"text": "Chat", "screen": "chat"},
]

_SCREEN_REGISTRY: dict[str, object] | None = None


def _get_screen_registry():
    """Lazy registry so screen modules load only when needed."""
    global _SCREEN_REGISTRY
    if _SCREEN_REGISTRY is not None:
        return _SCREEN_REGISTRY
    from .map_screen import build_checkin_html
    from .communication import build_chat_html
    from .emergency_screen import build_emergency_html
    from .health_screen import build_health_html
    from .home_screen import build_home_html
    from .settings_screen import build_medications_html, build_settings_html

    def home(app: "MeridianKioskApp"):
        return (
            build_home_html(
                app.services,
                app.api_url,
                family_circle_id=app.family_circle_id,
                kiosk_user_id=app.kiosk_user_id,
            ),
            None,
        )

    def emergency(app: "MeridianKioskApp"):
        return build_emergency_html(app.services, app.api_url), None

    def family(app: "MeridianKioskApp"):
        html, markers_json, places_json = build_checkin_html(
            app.services,
            app.api_url,
            app.family_circle_id,
            kiosk_user_id=app.kiosk_user_id,
        )
        return (
            html,
            f"initMap({json.dumps(markers_json)}, {json.dumps(places_json)})",
        )

    def chat(app: "MeridianKioskApp"):
        return (
            build_chat_html(
                app.services,
                app.api_url,
                app.kiosk_user_id,
                app.family_circle_id,
            ),
            None,
        )

    def health(app: "MeridianKioskApp"):
        return build_health_html(app.services, app.api_url), None

    def schedule(app: "MeridianKioskApp"):
        return build_schedule_html(app.services, app.api_url), None

    def settings(app: "MeridianKioskApp"):
        return build_settings_html(app.services, app.api_url), None

    def medications(app: "MeridianKioskApp"):
        return build_medications_html(app.services, app.api_url), None

    _SCREEN_REGISTRY = {
        "home": home,
        "emergency": emergency,
        "family": family,
        "chat": chat,
        "health": health,
        "schedule": schedule,
        "settings": settings,
        "medications": medications,
    }
    return _SCREEN_REGISTRY


class KioskBridge:
    """Exposed to JS as pywebview.api. Thin bridge; calendar modal DOM is kiosk.js (meridianKioskEvents)."""

    def __init__(self, app):
        self._app = app
        self._chat = ChatHandler(app)
        self._health = HealthHandler(app)
        self._location = LocationHandler(app)
        self._schedule = ScheduleHandler(app)
        self._sensor = app._sensor

    def navigate(self, screen_name: str):
        """Switch to screen. Called from JS nav click handler."""
        logger.info(f"Nav: {screen_name}")
        self._app._navigate_to(screen_name)

    def call_phone(self, phone: str, display_name: str = "") -> str:
        """Place a phone call via server Twilio endpoint."""
        return self._chat.call_phone(phone, display_name)

    def print_emergency(self):
        """Print emergency document. Called from JS Print button."""
        logger.info("Print emergency (button)")
        self._app._print_emergency()

    def refresh_events(self):
        """Refresh home Up Next and timeline. Called from JS after event change."""
        self._app._load_home_schedule()

    def reload_screen(self, screen_id: str) -> None:
        """Rebuild screen HTML from the server (same ids as data-screen on top nav or footer—no separate footer API)."""
        sid = (screen_id or "").strip()
        if sid == "home":
            self._app._load_home_schedule()
            return
        if sid in (
            "health",
            "schedule",
            "family",
            "chat",
            "settings",
            "medications",
            "emergency",
        ):
            self._app._navigate_to(sid)

    def submit_event_form(self, payload_json: str) -> str:
        return self._schedule.submit_event_form(payload_json)

    def add_event(self, payload_json: str) -> str:
        return self._schedule.submit_event_form(payload_json)

    def update_event(self, event_id: str, payload_json: str) -> str:
        try:
            data = json.loads(payload_json)
        except json.JSONDecodeError as e:
            return str(e)
        data["id"] = event_id
        return self._schedule.submit_event_form(json.dumps(data))

    def delete_event(self, event_id: str) -> str:
        return self._schedule.delete_event(event_id)

    def mark_medication_taken(
        self, medication_id: int, time_slot: str, taken: bool
    ) -> str:
        return self._health.mark_medication_taken(medication_id, time_slot, taken)

    def get_medications_editor_rows(self) -> str:
        return self._health.get_medications_editor_rows()

    def save_medications_editor_rows(
        self, rows_json: str, initial_snapshot_json: str
    ) -> str:
        return self._health.save_medications_editor_rows(
            rows_json, initial_snapshot_json
        )

    def snooze_stove_temp(self) -> None:
        """Snooze stove warnings and clear emergency alert (same POST as webapp cancel)."""
        self._sensor.snooze_stove_alerts()

    def where_is_everyone(self) -> str:
        return self._location.where_is_everyone()


class MeridianKioskApp:
    """Pywebview kiosk app. Python drives data and HTML; JS is thin bridge."""

    def __init__(
        self,
        services: KioskRemoteServiceContainer,
        api_url: str,
        kiosk_user_id: str,
        family_circle_id: str,
    ):
        self.services = services
        self.api_url = api_url
        self.kiosk_user_id = kiosk_user_id
        self.family_circle_id = family_circle_id
        self._window = None
        self._bridge = None
        self._alert_was_activated = False
        self._last_incoming_call_id = 0
        self._sensor = SensorHandler(self)

    def run(self):
        """Create window, wire bridge, start webview loop."""
        import webview

        base = (self.api_url or "").rstrip("/")
        url = (
            f"{base}/kiosk-auth?user_id={self.kiosk_user_id}&family_circle_id={self.family_circle_id}"
            if base
            else None
        )
        if not url:
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
            resizable=True,
            frameless=frameless,
            fullscreen=fullscreen,
            js_api=self._bridge,
        )

        def on_loaded(*args, **kwargs):
            threading.Thread(target=self._on_ready, daemon=True).start()

        self._window.events.loaded += on_loaded
        _wv_debug = get_kiosk_webview_debug()
        if _wv_debug:
            logger.info(
                "Kiosk pywebview debug on (MERIDIAN_KIOSK_WEBVIEW_DEBUG): Web Inspector enabled where supported"
            )
        webview.start(debug=_wv_debug)

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
            if screen_name == "settings":
                self._sensor.push_stove_temp_display()
        except Exception as e:
            logger.exception(f"navigate failed: {e}")

    def _build_screen_html(self, screen_name: str) -> tuple[str, Optional[str]]:
        """Build HTML for screen. Returns (html, extra_js) where extra_js runs after showScreen (e.g. initMap)."""
        from . import html_primitives as hp

        builder = _get_screen_registry().get(screen_name)
        if builder:
            return builder(self)
        return hp.error_state("Unknown screen"), None

    def _print_emergency(self):
        """Trigger emergency print (same flow as alert-activated)."""
        from .emergency_screen import trigger_emergency_print

        trigger_emergency_print(self.services)

    def _on_ready(self):
        """Runs in background thread after load. Initial screen, clock, meds, events, alerts."""
        logger.info("Kiosk loaded, initializing...")
        time.sleep(0.3)
        self._navigate_to("home")
        self._refresh_clock()
        self._sensor.start()
        threading.Thread(target=self._start_clock_tick, daemon=True).start()
        threading.Thread(target=self._start_alert_poll, daemon=True).start()
        threading.Thread(target=self._start_incoming_call_poll, daemon=True).start()

    def _refresh_clock(self):
        """Full clock update: day, date line, time, period label + sprite."""
        time_svc = self.services.get_time_service()
        if not time_svc:
            return
        self._eval_el("clock-day", time_svc.get_dayof_week().upper())
        if getattr(time_svc, "get_clock_date_line", None):
            self._eval_el("clock-date", time_svc.get_clock_date_line())
        else:
            self._eval_el(
                "clock-date",
                f"{time_svc.get_month_day()}, {time_svc.get_year()}",
            )
        self._eval_el("clock-time", time_svc.get_time())
        self._eval_clock_period(time_svc)

    def _eval_clock_period(self, time_svc) -> None:
        if getattr(time_svc, "get_day_period", None):
            label, sprite = time_svc.get_day_period()
            self._eval(
                f"updateClockPeriod({json.dumps(label.upper())}, {json.dumps(sprite)})"
            )
        else:
            self._eval_el("clock-period", time_svc.get_am_pm().upper())

    def _eval_el(self, el_id: str, content: str):
        """Update element by id."""
        self._eval(f"updateEl({json.dumps(el_id)}, {json.dumps(content)})")

    def _start_clock_tick(self):
        """Per-second clock tick in background."""
        while True:
            time.sleep(1)
            time_svc = self.services.get_time_service()
            if not time_svc:
                continue
            self._eval_el("clock-time", time_svc.get_time())
            self._eval_clock_period(time_svc)

    def _load_home_schedule(self):
        """Update Up Next and timeline. Fetches data via home_screen, pushes to webview."""
        from .home_screen import (
            build_timeline_html,
            build_up_next_html,
            load_schedule_items,
        )

        items, now = load_schedule_items(self.services)
        self._eval_el("up_next_content", build_up_next_html(items, now))
        self._eval_el("timeline_content", build_timeline_html(items))

    def _refresh_schedule_if_shown(self) -> None:
        """Tell kiosk.js to reload Schedule screen if it is active."""
        self._eval("meridianKioskEvents.refreshScheduleIfShown()")

    def _start_alert_poll(self):
        """Poll alert; when activated, switch to emergency, add flash, trigger print."""
        from .emergency_screen import trigger_emergency_print

        while True:
            time.sleep(10)
            alert_svc = self.services.get_alert_service()
            if not alert_svc:
                continue
            result = alert_svc.get_alert_status()
            if not result.success or not result.data:
                continue
            activated = result.data.get("activated", False)
            self.services.alert_activated_holder[0] = activated
            if activated:
                self._navigate_to("emergency")
                self._eval("document.body.classList.add('alert-active')")
                if not self._alert_was_activated:
                    time.sleep(0.5)
                    trigger_emergency_print(self.services)
            else:
                self._eval("document.body.classList.remove('alert-active')")
            self._alert_was_activated = activated

    def _start_incoming_call_poll(self):
        """Poll incoming call signal and open chat window for auto-answer flow."""
        while True:
            time.sleep(1)
            call_svc = self.services.get_incoming_call_service()
            if not call_svc:
                continue
            result = call_svc.get_incoming_call()
            if not result.success or not result.data:
                continue
            call_id = int(result.data.get("call_id") or 0)
            if call_id <= 0 or call_id == self._last_incoming_call_id:
                continue
            caller_user_id = (result.data.get("from_user_id") or "").strip()
            display_name = (result.data.get("from_display_name") or "").strip()
            if not caller_user_id:
                continue
            self._last_incoming_call_id = call_id
            self._navigate_to("chat")
            call_svc.acknowledge_incoming_call(call_id)

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
