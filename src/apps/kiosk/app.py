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
from dataclasses import dataclass, field
from typing import Any, Optional

from shared.config import (
    get_kiosk_tv_fullscreen,
    get_kiosk_tv_mode,
    get_kiosk_window_size,
)

from .api_client import KioskRemoteServiceContainer, create_kiosk_remote
from .communication import ChatHandler
from .map_screen import LocationHandler
from .schedule_screen import ScheduleHandler, build_schedule_html
from .health_screen import HealthHandler
from .sensor_widgets import SensorHandler

logger = logging.getLogger(__name__)


@dataclass
class KioskRuntimeCache:
    """Session in-memory cache for reusable kiosk runtime data.

    Generic key/value + scoped key/value stores so all kiosk flows use one cache API.
    """

    values: dict[str, Any] = field(default_factory=dict)
    scoped_values: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put(self, key: str, value: Any) -> None:
        self.values[str(key)] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(str(key), default)

    def put_scoped(self, scope: str, key: str, value: Any) -> None:
        skey = str(scope)
        if skey not in self.scoped_values:
            self.scoped_values[skey] = {}
        self.scoped_values[skey][str(key)] = value

    def get_scoped(self, scope: str, key: str, default: Any = None) -> Any:
        return self.scoped_values.get(str(scope), {}).get(str(key), default)


NAV_BUTTONS = [
    {"text": "Home", "screen": "home"},
    {"text": "Schedule", "screen": "schedule"},
    {"text": "Family", "screen": "family"},
    {"text": "Settings", "screen": "settings"},
]

_SCREEN_REGISTRY: dict[str, object] | None = None


def _get_screen_registry():
    """Lazy registry so screen modules load only when needed."""
    global _SCREEN_REGISTRY
    if _SCREEN_REGISTRY is not None:
        return _SCREEN_REGISTRY
    from .map_screen import build_checkin_html
    from .emergency_screen import build_emergency_html
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
            runtime_cache=app._runtime_cache,
        )
        return (
            html,
            f"initMap({json.dumps(markers_json)}, {json.dumps(places_json)})",
        )

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
        logger.debug(f"Nav: {screen_name}")
        self._app._navigate_to(screen_name)

    def call_phone(self, phone: str, display_name: str = "") -> str:
        """Place a phone call via server Twilio endpoint."""
        return self._chat.call_phone(phone, display_name)

    def get_voice_token(self):
        """Get Twilio voice token for kiosk browser SDK via Python bridge."""
        return self._chat.get_voice_token()

    def print_emergency(self):
        """Print emergency document. Called from JS Print button."""
        logger.debug("Print emergency (button)")
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
            "schedule",
            "family",
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

    def mark_all_non_prn_taken(self) -> str:
        return self._health.mark_all_non_prn_taken()

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
        self._runtime_cache = KioskRuntimeCache()

    def run(self):
        """Create window, wire bridge, start webview loop."""
        import webview

        base = (self.api_url or "").rstrip("/")
        auth_query = (
            f"user_id={self.kiosk_user_id}&family_circle_id={self.family_circle_id}"
        )
        if (os.environ.get("MERIDIAN_KIOSK_NGROK_BYPASS") or "").strip() == "1":
            auth_query = f"{auth_query}&ngrok-skip-browser-warning=true"
        url = (
            f"{base}/kiosk-auth?{auth_query}"
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
        devtools_enabled = (os.environ.get("MERIDIAN_KIOSK_DEVTOOLS") or "0").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        try:
            webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = devtools_enabled
        except Exception:
            pass
        kiosk_user_agent = (
            os.environ.get("MERIDIAN_KIOSK_USER_AGENT") or "Meridian-Kiosk/1.0"
        ).strip()
        gui_pref = (os.environ.get("MERIDIAN_KIOSK_WEBVIEW_GUI") or "qt").strip().lower()
        if gui_pref:
            try:
                logger.info(f"Kiosk pywebview GUI preference: {gui_pref}")
                if devtools_enabled:
                    logger.info("Kiosk webview devtools enabled")
                webview.start(
                    debug=devtools_enabled,
                    gui=gui_pref,
                    user_agent=kiosk_user_agent,
                )
                return
            except Exception as e:
                logger.error(
                    f"Kiosk pywebview GUI '{gui_pref}' unavailable; refusing fallback backend: {e}"
                )
                raise RuntimeError(
                    f"Failed to start kiosk webview with required GUI backend '{gui_pref}'"
                ) from e
        raise RuntimeError("MERIDIAN_KIOSK_WEBVIEW_GUI must be set (use 'qt').")

    def _eval(self, js: str):
        """Run JS in webview. Handles threading/platform quirks."""
        try:
            self._window.evaluate_js(js)
        except Exception as e:
            logger.debug(f"evaluate_js failed: {e}")

    def _navigate_to(self, screen_name: str):
        """Show screen by name. Builds HTML and calls showScreen."""
        try:
            logger.debug(f"Building screen: {screen_name}")
            html, extra = self._build_screen_html(screen_name)
            self._runtime_cache.put_scoped("screen_html", screen_name, html)
            if extra:
                self._runtime_cache.put_scoped("screen_extra_js", screen_name, extra)
            escaped = json.dumps(html)
            self._eval(f"showScreen({json.dumps(screen_name)}, {escaped})")
            if extra:
                self._eval(extra)
            if screen_name == "settings":
                self._sensor.push_stove_temp_display()
            if screen_name == "home":
                self._load_home_schedule()
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
        """Runs in background thread after load. Initial screen, clock, meds, events, alerts.

        Boot is two phases: (1) Full-screen watermark (#kiosk-boot-overlay) from first line below
        until home shell + schedule + clock are ready. (2) Watermark off; fixed corner floater
        (#kiosk-boot-corner) with status text until _boot_cache_warmup (photos, places, tiles) finishes.
        The corner floater persists across navigations until caching completes.
        """
        logger.info("Kiosk loaded, initializing...")
        self._set_corner_boot_loading(False, "")
        self._set_boot_loading(True, "Starting Meridian...")
        time.sleep(0.3)
        self._set_boot_loading(True, "Loading home data...")
        self._navigate_to("home")
        self._set_boot_loading(True, "Loading clock...")
        self._refresh_clock()
        self._set_boot_loading(False)
        self._set_corner_boot_loading(True, "Loading…")
        threading.Thread(target=self._boot_cache_warmup, daemon=True).start()
        vs = self.services.get_voice_service()
        if vs and getattr(vs, "log_twilio_startup_check", None):
            threading.Thread(
                target=vs.log_twilio_startup_check,
                daemon=True,
            ).start()
        # self._sensor.start_stove_sensor()
        threading.Thread(target=self._start_clock_tick, daemon=True).start()
        threading.Thread(target=self._start_alert_poll, daemon=True).start()
        threading.Thread(target=self._start_incoming_call_poll, daemon=True).start()

    def _home_map_center(self):
        """Lat/lon for named 'home' place (same logic as family map)."""
        loc = self.services.get_location_service()
        if not loc:
            return None, None
        fc = (self.family_circle_id or "").strip()
        if not fc:
            return None, None
        r = loc.get_named_places(fc)
        if not r.success or not r.data:
            return None, None
        home_place = None
        for p in r.data:
            if "home" in (p.get("location_name") or "").lower():
                home_place = p
                break
        if not home_place:
            home_place = r.data[0]
        lat = home_place.get("gps_latitude")
        lon = home_place.get("gps_longitude")
        if lat is None or lon is None:
            return None, None
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            return None, None

    def _boot_cache_warmup(self) -> None:
        """Background cache: photos, named places (home center), OSM tiles. Clears #kiosk-boot-corner in finally."""
        try:
            self._start_photo_warmup()
            self._set_corner_boot_loading(True, "Loading places…")
            lat, lon = self._home_map_center()
            if lat is not None and lon is not None:
                self._runtime_cache.put("last_map_center", (float(lat), float(lon)))
            loc = self.services.get_location_service()
            if loc and lat is not None and lon is not None:
                self._set_corner_boot_loading(True, "Loading map tiles…")
                loc.warm_osm_tiles_around(lat, lon)
        except Exception as e:
            logger.warning("Map tile warmup failed: %s", e)
        finally:
            self._set_boot_loading(False)
            self._set_corner_boot_loading(False, "")

    def _start_photo_warmup(self) -> None:
        """Warm user/contact photo cache in background after first paint."""
        scanned = 0
        loaded = 0
        skipped_no_linked_user = 0
        no_photo = 0
        try:
            contact_svc = self.services.get_contact_service()
            if not contact_svc:
                logger.info("Photo warmup skipped: contact service unavailable")
                return
            result = contact_svc.get_contacts()
            if not result.success or not result.data:
                logger.info("Photo warmup skipped: no contacts")
                return
            total = len(result.data)
            for c in result.data:
                scanned += 1
                user_id = (c.get("user_id") or "").strip()
                if not user_id:
                    skipped_no_linked_user += 1
                else:
                    avatar_src = contact_svc.get_user_photo_b64(user_id)
                    if avatar_src:
                        loaded += 1
                    else:
                        no_photo += 1
                if scanned == 1 or scanned == total or scanned % 3 == 0:
                    self._set_corner_boot_loading(
                        True, f"Loading photos… ({scanned}/{total})"
                    )
            logger.info(
                "Photo warmup complete: contacts=%s loaded=%s skipped_no_linked_user=%s no_photo=%s",
                scanned,
                loaded,
                skipped_no_linked_user,
                no_photo,
            )
        except Exception as e:
            logger.warning(f"Photo warmup failed: {e}")

    def _set_boot_loading(self, active: bool, message: str = "") -> None:
        """Show/hide boot overlay with optional status text."""
        self._eval(
            f"setBootLoading({json.dumps(bool(active))}, {json.dumps(message)})"
        )

    def _set_corner_boot_loading(self, active: bool, message: str = "") -> None:
        """Show/hide #kiosk-boot-corner spinner + caption (kiosk.html / setKioskCornerBootLoading)."""
        self._eval(
            f"setKioskCornerBootLoading({json.dumps(bool(active))}, {json.dumps(message)})"
        )

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
        self._runtime_cache.put(
            "home_schedule",
            {
                "items": items,
                "now": now,
                "calendar_events_today": [
                    it.get("event_data")
                    for it in items
                    if it.get("type") == "event" and it.get("event_data")
                ],
            },
        )
        self._eval_el("up_next_content", build_up_next_html(items, now))
        self._eval_el("timeline_content", build_timeline_html(items))

    def _refresh_schedule_if_shown(self) -> None:
        """Tell kiosk.js to reload Schedule screen if it is active."""
        self._eval("meridianKioskEvents.refreshScheduleIfShown()")

    def _start_alert_poll(self):
        """Poll alert; when activated, switch to emergency and add flash."""

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
                # if not self._alert_was_activated:
                #     time.sleep(0.5)
                #     trigger_emergency_print(self.services)
            else:
                self._eval("document.body.classList.remove('alert-active')")
            self._alert_was_activated = activated

    def _start_incoming_call_poll(self):
        """Poll incoming call signal and open Family screen for auto-answer flow."""
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
            self._navigate_to("family")
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
