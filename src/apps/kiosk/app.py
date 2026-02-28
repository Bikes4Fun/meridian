"""
Application factory for Dementia TV.
Creates and configures the application with proper dependency injection.

CLIENT vs SERVER:
- This module is used only by the client (Kivy UI). api_url (from main entry) determines where
  services come from via client/remote.create_remote(); container is not used.
- Display settings from GET /api/settings (no local DB needed).

SERVER DEPLOYMENT: app_factory.py is not needed on the server; the server uses server/app.py only.
"""

import logging
from typing import Optional
from shared.config import ConfigManager
from .api_client import create_remote, get_display_settings
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.clock import Clock
from kivy.core.window import Window
from .screens import ScreenFactory
from .widgets import WidgetFactory
import datetime


class DementiaTVApp(App):
    """Main Kivy application for Dementia TV using modular components."""

    def __init__(self, services, display_settings=None, **kwargs):
        super().__init__(**kwargs)
        self.services = services
        self.display_settings = display_settings
        self.screen_manager = None
        self.screen_factory = None
        self.widget_factory = None

    def build(self):
        """Build the application UI using modular components."""
        Window.size = (
            self.display_settings.window_width,
            self.display_settings.window_height,
        )
        Window.left = self.display_settings.window_left
        Window.top = self.display_settings.window_top
        Window.borderless = True  # Remove macOS title bar for TV display

        # Create screen manager
        self.screen_manager = ScreenManager()

        # Create factories
        self.screen_factory = ScreenFactory(
            self.services, self.screen_manager, display_settings=self.display_settings
        )
        self.widget_factory = WidgetFactory(
            self.services, display_settings=self.display_settings
        )

        # Create screens
        home_screen = self.screen_factory.create_home_screen()
        self.screen_manager.add_widget(home_screen)

        calendar_screen = self.screen_factory.create_calendar_screen()
        self.screen_manager.add_widget(calendar_screen)

        emergency_screen = self.screen_factory.create_emergency_screen()
        self.screen_manager.add_widget(emergency_screen)

        family_screen = self.screen_factory.create_family_screen()
        self.screen_manager.add_widget(family_screen)

        more_screen = self.screen_factory.create_more_screen()
        self.screen_manager.add_widget(more_screen)

        self.screen_manager.current = "family"

        # Store reference for updates
        self.home_screen = home_screen

        # Initial update
        self.update_all()

        # Schedule periodic updates (every second)
        Clock.schedule_interval(self.update_time, 1.0)
        # Poll alert status: when activated, switch TV to emergency screen and enable flashing
        Clock.schedule_interval(self._check_alert_status, 2.0)

        return self.screen_manager

    def _check_alert_status(self, dt=None):
        """Poll alert API; when activated, switch to emergency screen and enable flashing."""
        alert_svc = self.services.get("alert_service")
        if not alert_svc:
            return
        result = alert_svc.get_alert_status()
        if not result.success:
            return
        activated = result.data.get("activated", False) if result.data else False
        self.services["_alert_activated"][0] = activated
        if activated and self.screen_manager:
            self.screen_manager.current = "emergency"

    def update_all(self):
        """Update all display elements."""
        self.update_clock()
        self._load_medications()
        self._load_events()

    def update_clock(self):
        """Update clock display."""
        if hasattr(self, "home_screen"):
            # Find clock widget using recursive search
            clock_widget = self._find_widget_by_attribute(self.home_screen, "day_label")
            if clock_widget:
                # Day of week (uppercase)
                clock_widget.day_label.text = (
                    self.services["time_service"].get_dayof_week().upper()
                )

                # Time of day text and icon
                time_of_day = self.services["time_service"].get_am_pm()
                clock_widget.time_of_day_label.text = time_of_day.upper()
                self._last_time_of_day = time_of_day  # Store for change detection

                if hasattr(clock_widget, "time_of_day_icon"):
                    icon_path = self.widget_factory._get_time_of_day_icon(time_of_day)
                    clock_widget.time_of_day_icon.source = icon_path

                # Time
                clock_widget.time_label.text = self.services["time_service"].get_time()

                # Date split: month+day on left, year on right
                clock_widget.date_label.text = self.services[
                    "time_service"
                ].get_month_day()
                if hasattr(clock_widget, "year_label"):
                    clock_widget.year_label.text = self.services[
                        "time_service"
                    ].get_year()

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

    def _find_widget_by_attribute(self, parent, attribute_name):
        """Recursively find widget with specific attribute."""
        for child in parent.children:
            if hasattr(child, attribute_name):
                return child
            # Recursively search in child widgets
            if hasattr(child, "children"):
                result = self._find_widget_by_attribute(child, attribute_name)
                if result:
                    return result
        return None

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

    def update_time(self, dt=1):
        """Update time display and check for time-of-day changes."""
        if hasattr(self, "home_screen"):
            clock_widget = self._find_widget_by_attribute(
                self.home_screen, "time_label"
            )
            if clock_widget:
                clock_widget.time_label.text = self.services["time_service"].get_time()

                # Check if time-of-day changed (morning->afternoon->evening->night)
                current_time_of_day = self.services["time_service"].get_am_pm()
                if not hasattr(self, "_last_time_of_day"):
                    self._last_time_of_day = current_time_of_day

                if current_time_of_day != self._last_time_of_day:
                    self._last_time_of_day = current_time_of_day
                    clock_widget.time_of_day_label.text = current_time_of_day.upper()
                    if hasattr(clock_widget, "time_of_day_icon"):
                        icon_path = self.widget_factory._get_time_of_day_icon(
                            current_time_of_day
                        )
                        clock_widget.time_of_day_icon.source = icon_path


class AppFactory:
    """Factory for creating the Dementia TV application."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()

    def create_application(self, user_id=None, api_url: str = None) -> DementiaTVApp:
        """Create the Dementia TV application with all dependencies.
        api_url: API server base URL (from main entry config). Display settings from GET /api/settings.
        """
        if not api_url:
            raise ValueError("api_url required. Pass from main entry (e.g. create_app(..., api_url=...)).")
        try:
            import requests
            session = requests.Session()
        except ImportError:
            session = None
        display_settings = get_display_settings(
            api_url, user_id=user_id, session=session
        )
        services = create_remote(api_url, user_id=user_id, session=session)

        # Create and return the application
        return DementiaTVApp(services=services, display_settings=display_settings)


def create_app(
    config_manager: Optional[ConfigManager] = None, user_id=None, api_url: str = None) -> DementiaTVApp:
    """Create the Dementia TV application. api_url from main entry configuration."""
    factory = AppFactory(config_manager)
    return factory.create_application(user_id=user_id, api_url=api_url)
