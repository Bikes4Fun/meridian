"""
Application factory for Meridian Kiosk.
Creates and configures the application with proper dependency injection.

CLIENT vs SERVER:
- This module is used only by the client (Kivy UI). api_url (from main entry) determines where
  services come from via api_client.create_kiosk_remote(); container is not used.

SERVER DEPLOYMENT: app_factory.py is not needed on the server; the server uses server/app.py only.
"""

import logging
import os
from .api_client import create_kiosk_remote
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.clock import Clock
from kivy.core.window import Window
from .screens import ScreenFactory
from .home_screen import get_time_of_day_icon
import datetime


class MeridianKioskApp(App):
    """Main Kivy application for Meridian Kiosk using modular components."""

    def __init__(self, services, **kwargs):
        super().__init__(**kwargs)
        self.services = services
        self.screen_manager = None

    def build(self):
        """Build the application UI using modular components."""
        Window.clearcolor = (0.98, 0.98, 0.96, 1)
        Window.size = (740, 1080)
        Window.left = 10
        Window.top = 120
        Window.borderless = True  # Remove macOS title bar for TV display

        # Create a Kivy screen manager
        self.screen_manager = ScreenManager()

        screen_factory = ScreenFactory(
            self.services,
            self.screen_manager,
            kiosk_user_id=self.kiosk_user_id,
            family_circle_id=self.family_circle_id,
        )

        screen_factory.add_all_screens(screen_factory)

        # Sync photos on boot: fetch from server and cache locally for offline use
        Clock.schedule_once(lambda dt: self._sync_photos_on_boot(), 1.0)

        # Full clock refresh on boot (day, date, year)
        Clock.schedule_once(lambda dt: self.refresh_clock(), 1.0)
        # Per-second tick: time digits + time-of-day when period changes
        Clock.schedule_interval(self._tick_clock, 1.0)
        # Poll alert status: when activated, switch TV to emergency screen and enable flashing
        Clock.schedule_interval(self._check_alert_status, 2.0)

        # Load medications and events on boot
        Clock.schedule_once(lambda dt: self._load_medications(), 1.5)
        Clock.schedule_once(lambda dt: self._load_events(), 1.5)

        return self.screen_manager


    def _check_alert_status(self, dt=None):
        """Poll alert API; when activated, switch to emergency screen, enable flashing, and auto-print."""
        alert_svc = self.services.get("alert_service")
        if not alert_svc:
            return
        result = alert_svc.get_alert_status()
        if not result.success:
            return
        activated = result.data.get("activated", False) if result.data else False
        was_activated = getattr(self, "_alert_was_activated", False)
        self.services["_alert_activated"][0] = activated
        if activated and self.screen_manager:
            self.screen_manager.current = "emergency"
            if not was_activated:
                from .emergency_print import trigger_emergency_print

                Clock.schedule_once(
                    lambda _dt: trigger_emergency_print(self.services), 0.5
                )
        self._alert_was_activated = activated

    def _sync_photos_on_boot(self):
        """Fetch checkins and download photos to local cache for offline use."""
        loc_svc = self.services.get("location_service")
        if not loc_svc or not hasattr(loc_svc, "fetch_photo_to_cache"):
            return
        result = loc_svc.get_checkins()
        if not result.success or not result.data:
            return
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        for checkin in result.data:
            if checkin.get("photo_url") and checkin.get("user_id"):
                loc_svc.fetch_photo_to_cache(checkin["user_id"], cache_dir)

    def update_all(self):
        """Update all display elements."""
        self.refresh_clock()
        self._load_medications()
        self._load_events()

    def _tick_clock(self, dt=1):
        """Per-second clock tick: time digits + time-of-day label/icon when period changes."""
        if not hasattr(self, "_clock_widget") or not self._clock_widget:
            return
        cw = self._clock_widget
        time_svc = self.services.get("time_service")
        if not time_svc:
            return

        cw.time_label.text = time_svc.get_time()
        current_time_of_day = time_svc.get_am_pm()
        if not hasattr(self, "_last_time_of_day"):
            self._last_time_of_day = current_time_of_day
        if current_time_of_day != self._last_time_of_day:
            self._last_time_of_day = current_time_of_day
            cw.time_of_day_label.text = current_time_of_day.upper()
            if hasattr(cw, "time_of_day_icon"):
                cw.time_of_day_icon.source = get_time_of_day_icon(current_time_of_day)

    def refresh_clock(self):
        """Full clock refresh: day, date, year, then per-second tick."""
        if not hasattr(self, "_clock_widget") or not self._clock_widget:
            return
        cw = self._clock_widget
        time_svc = self.services.get("time_service")
        if not time_svc:
            return

        cw.day_label.text = time_svc.get_dayof_week().upper()
        cw.date_label.text = time_svc.get_month_day()
        if hasattr(cw, "year_label"):
            cw.year_label.text = time_svc.get_year()
        self._tick_clock()

    def _load_medications(self):
        """Load medication data."""
        if self.services.get("medication_service") and hasattr(self, "home_screen"):
            result = self.services["medication_service"].get_medication_data()
            if result.success:
                # Group medications by time period
                time_groups = {}
                for med in result.data.get("timed_medications", []):
                    time_period = med.get("time", "Unknown")
                    if time_period not in time_groups:
                        time_groups[time_period] = []
                    time_groups[time_period].append(med)

                # Sort time groups chronologically
                group_times = result.data.get("medication_time_groups", {})
                sorted_times = sorted(
                    time_groups.keys(), key=lambda t: group_times.get(t, "23:59:59")
                )

                # Build display text with groups
                meds_text = []
                for time_period in sorted_times:
                    meds = time_groups[time_period]
                    if meds:  # Only show group if it has medications
                        meds_text.append(f"{time_period}:")
                        for med in meds:
                            status = "Done" if med["status"] == "done" else "Not Done"
                            meds_text.append(f"  • {med['name']}: {status}")

                # Add PRN medications if any
                prn_meds = result.data.get("prn_medications", [])
                if prn_meds:
                    meds_text.append("PRN (As Needed):")
                    for med in prn_meds:
                        last_taken = (
                            f"Last: {med['last_taken']}"
                            if med["last_taken"]
                            else "Not taken today"
                        )
                        meds_text.append(f"  • {med['name']}: {last_taken}")

                # Find medication widget in nested structure
                self._find_and_update_widget(
                    self.home_screen,
                    "medication_content",
                    "\n".join(meds_text) if meds_text else "No medications",
                )
            else:
                # Find medication widget and show error
                self._find_and_update_widget(
                    self.home_screen, "medication_content", "Error loading medications"
                )

    def _load_events(self):
        """Load events data."""
        logger = logging.getLogger(__name__)
        if self.services.get("calendar_service") and hasattr(self, "home_screen"):
            today = datetime.datetime.now()
            logger.debug(
                f"Loading events for today: {today.strftime('%Y-%m-%d')} (day={today.day})"
            )
            result = self.services["calendar_service"].get_events_for_date(
                today.strftime("%Y-%m-%d")
            )

            logger.debug(
                f"Events query result: success={result.success}, data_count={len(result.data) if result.data else 0}"
            )
            if result.data:
                logger.debug(f"Events found: {result.data}")

            if result.success and result.data:
                events_text = [f"• {event}" for event in result.data]
                # Find events widget in nested structure
                self._find_and_update_widget(
                    self.home_screen, "events_content", "\n".join(events_text)
                )
            else:
                # Find events widget and show no events
                logger.debug(f"No events found for today, showing 'No events today'")
                self._find_and_update_widget(
                    self.home_screen, "events_content", "No events today"
                )

    def _find_and_update_widget(self, parent, attribute_name, text):
        """Recursively find widget with specific attribute and update its text."""
        for child in parent.children:
            if hasattr(child, attribute_name):
                getattr(child, attribute_name).text = text
                return True
            # Recursively search in child widgets
            if hasattr(child, "children"):
                if self._find_and_update_widget(child, attribute_name, text):
                    return True
        return False

def create_app(
    kiosk_user_id: str, family_circle_id: str, api_url: str = None
) -> MeridianKioskApp:
    """Create the Meridian Kiosk. kiosk_user_id and family_circle_id required. api_url from main entry."""
    if not api_url:
        raise ValueError(
            "api_url required. Pass from main entry (e.g. create_app(..., api_url=...))."
        )
    if not kiosk_user_id or not family_circle_id:
        raise ValueError("kiosk_user_id and family_circle_id required.")
    try:
        import requests

        session = requests.Session()
    except ImportError:
        session = None
    remote_services = create_kiosk_remote(
        api_url,
        kiosk_user_id=kiosk_user_id,
        family_circle_id=family_circle_id,
        session=session,
    )
    app = MeridianKioskApp(services=remote_services)
    app.kiosk_user_id = kiosk_user_id
    app.family_circle_id = family_circle_id
    return app
