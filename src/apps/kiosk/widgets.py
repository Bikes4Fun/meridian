"""
Widget creation logic for Meridian Kiosk.
Handles the creation of individual UI widgets.
"""

from .modular_display import (
    KioskWidget,
    KioskLabel,
    KioskButton,
)


# Top section: Day + Time of day (left) | Icon (right)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


def _format_contacts_for_display(contacts, include_header=True):
    """Format contact dicts into display text. Used by widgets."""
    if not contacts:
        return "No emergency contacts found"
    lines = ["Emergency Contacts:"] if include_header else []
    for c in contacts:
        phone = c.get("phone") or ""
        rel = c.get("relationship") or ""
        lines.append(f"• {c.get('display_name', '')} - {phone}: {rel}")
    return "\n".join(lines)


def apply_debug_border(widget, **kwargs):
    """Apply default border to widget."""
    b = {"color": [0, 0, 0, 1], "width": 1}
    b.update(kwargs)
    
    def make_updater(color, width):
        def update(instance, value):
            instance.canvas.after.clear()
            with instance.canvas.after:
                Color(*color)
                Line(
                    rectangle=(instance.x, instance.y, instance.width, instance.height),
                    width=width,
                )

        return update

    widget.bind(
        pos=make_updater(b["color"], b["width"]),
        size=make_updater(b["color"], b["width"]),
    )


class KioskNavBar(KioskWidget):
    """Generic navigation bar with configurable buttons."""

    def __init__(self, screen_manager=None, buttons=None, **kwargs):
        defaults = {
            "orientation": "horizontal",
            "size_hint": (1, None),
            "height": 90,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
        self.screen_manager = screen_manager
        self.buttons = buttons or []

        # Create navigation buttons
        self._create_nav_buttons()

    def _create_nav_buttons(self):
        """Create navigation buttons from configuration."""
        if not self.buttons:
            print("WARNING: No nav buttons configured!")
            return

        nav_button_width = 1.0 / len(self.buttons)

        for button_config in self.buttons:
            if isinstance(button_config, dict):
                text = button_config["text"]
                screen_name = button_config["screen"]
            else:
                continue

            btn = KioskButton(
                text=text,
                size_hint=(nav_button_width, None),
                height=self.height,
            )

            # Create proper closures for all callbacks to avoid reference issues
            def make_press_handler(btn_text, btn_screen):
                def press_handler(instance):
                    # print(f"on_press FIRED for button '{btn_text}' -> screen '{btn_screen}'")
                    self._navigate_to_screen(btn_screen)

                return press_handler

            btn.bind(on_press=make_press_handler(text, screen_name))
            self.add_widget(btn)

    def _navigate_to_screen(self, screen_name):
        """Navigate to specified screen."""
        if self.screen_manager:
            self.screen_manager.current = screen_name
        else:
            print(
                f"ERROR: Cannot navigate to '{screen_name}' - screen_manager is None!"
            )

    def add_button(self, text, screen_name, color="primary", font_size="large"):
        """Add a button to the navigation bar dynamically."""
        button_config = {
            "text": text,
            "screen": screen_name,
            "color": color,
            "font_size": font_size,
        }
        self.buttons.append(button_config)

        # Recreate buttons
        self.clear_widgets()
        self._create_nav_buttons()

    def remove_button(self, screen_name):
        """Remove a button from the navigation bar."""
        self.buttons = [
            btn
            for btn in self.buttons
            if (isinstance(btn, dict) and btn.get("screen") != screen_name)
            or (isinstance(btn, tuple) and len(btn) > 1 and btn[1] != screen_name)
        ]

        # Recreate buttons
        self.clear_widgets()
        self._create_nav_buttons()


class WidgetFactory:
    """Factory for creating UI widgets based on user preferences."""

    def __init__(self, services):
        self.services = services
        self.time_service = services.get("time_service")
        self.calendar_service = services.get("calendar_service")
        self.emergency_service = services.get("emergency_service")
        self.medication_service = services.get("medication_service")
        self.ice_profile_service = services.get("ice_profile_service")
        self.location_service = services.get("location_service")

    def create_widget(self, widget_type, **kwargs):
        """Create a widget of the specified type."""
        widget_creators = {
            "clock": self.create_clock_widget,
            "medication": self.create_medication_widget,
            "events": self.create_events_widget,
            "emergency_profile": self.create_emergency_screen_widget,
            "family_locations": self.create_family_locations_widget,
        }

        if widget_type not in widget_creators:
            raise ValueError(f"Unknown widget type: {widget_type}")

        return widget_creators[widget_type](**kwargs)

    def get_available_widgets(self):
        """Get list of available widget types."""
        return [
            "clock",
            "medication",
            "events",
            "emergency_profile",
            "family_locations",
        ]

    def is_widget_enabled(self, widget_type):
        """Check if a widget type is enabled for the user."""
        # all widgets are enabled by default
        # TODO: check user preferences from user_setting
        return True

    def get_user_widget_preferences(self):
        """Get user's widget preferences."""
        # For now, return default preferences
        # TODO: load from user_settings
        return {
            "clock": True,
            "medication": True,
            "events": True,
            "emergency_profile": True,
            "family_locations": True,
        }

    def create_widgets_for_screen(self, screen_type):
        """Create all widgets needed for a specific screen type."""
        screen_widgets = {
            "home": ["clock", "medication", "events"],
            "emergency": ["emergency_profile"],
            "more": [],
        }

        if screen_type not in screen_widgets:
            return []

        widgets = []
        for widget_type in screen_widgets[screen_type]:
            if self.is_widget_enabled(widget_type):
                widget = self.create_widget(widget_type)
                widgets.append((widget_type, widget))

        return widgets

    def create_clock_widget(self):
        """Create clock widget using modular components - dementia clock style."""
        # Widget-specific tokens (clock, med, events)
        CLOCK_ICON_SIZE = 100
        CLOCK_DAY_HEIGHT = 60
        CLOCK_TEXT_HEIGHT = 50
        CLOCK_TIME_HEIGHT = 120
        CLOCK_DATE_HEIGHT = 60
        CLOCK_SPACING = 0
        CLOCK_PADDING = [15, 10]
        text_color = (0.1, 0.1, 0.1, 1)

        clock = KioskWidget()
        clock.spacing = CLOCK_SPACING
        clock.padding = CLOCK_PADDING
        apply_debug_border(clock)

        top_section = BoxLayout(orientation="horizontal")
        top_section.size_hint = (1, None)
        top_section.height = CLOCK_DAY_HEIGHT + CLOCK_TEXT_HEIGHT
        apply_debug_border(top_section)

        # Left side: Day and Time of day stacked
        left_stack = BoxLayout(orientation="vertical")
        left_stack.size_hint = (0.7, 1)

        day_label = KioskLabel(type="header", text="")
        day_label.color = text_color
        day_label.size_hint = (1, 0.5)
        apply_debug_border(day_label)
        left_stack.add_widget(day_label)

        time_of_day_label = KioskLabel(type="subheader", text="")
        time_of_day_label.color = text_color
        time_of_day_label.halign = "left"
        time_of_day_label.valign = "top"
        time_of_day_label.size_hint = (1, 0.5)
        apply_debug_border(time_of_day_label)
        left_stack.add_widget(time_of_day_label)

        top_section.add_widget(left_stack)

        # Right side: Icon (centered in container)
        icon_container = AnchorLayout(anchor_x="center", anchor_y="center")
        icon_container.size_hint = (0.3, 1)
        apply_debug_border(icon_container)

        time_of_day_icon = Image()
        time_of_day_icon.size_hint = (None, None)
        time_of_day_icon.width = CLOCK_ICON_SIZE
        time_of_day_icon.height = CLOCK_ICON_SIZE
        # Set initial icon based on current time
        initial_time_of_day = (
            self.time_service.get_am_pm() if self.time_service else "Morning"
        )
        time_of_day_icon.source = self._get_time_of_day_icon(initial_time_of_day)
        icon_container.add_widget(time_of_day_icon)

        top_section.add_widget(icon_container)
        clock.add_widget(top_section)

        # Main time display - very large, centered
        time_label = KioskLabel(type="hero", text="")
        time_label.color = text_color
        time_label.halign = "center"
        time_label.valign = "middle"
        time_label.size_hint = (1, None)
        time_label.height = CLOCK_TIME_HEIGHT
        apply_debug_border(time_label)
        clock.add_widget(time_label)

        # Bottom section: Month Day (left) | Year (right)
        bottom_section = BoxLayout(orientation="horizontal")
        bottom_section.size_hint = (1, None)
        bottom_section.height = CLOCK_DATE_HEIGHT
        apply_debug_border(bottom_section)

        date_label = KioskLabel(type="subheader", text="")
        date_label.color = text_color
        date_label.halign = "left"
        date_label.valign = "middle"
        date_label.size_hint = (0.6, 1)
        apply_debug_border(date_label)
        bottom_section.add_widget(date_label)

        year_label = KioskLabel(type="subheader", text="")
        year_label.color = text_color
        year_label.halign = "right"
        year_label.valign = "middle"
        year_label.size_hint = (0.4, 1)
        apply_debug_border(year_label)
        bottom_section.add_widget(year_label)

        clock.add_widget(bottom_section)

        # Store references for updates
        clock.day_label = day_label
        clock.time_of_day_icon = time_of_day_icon
        clock.time_of_day_label = time_of_day_label
        clock.time_label = time_label
        clock.date_label = date_label
        clock.year_label = year_label

        return clock

    def _get_time_of_day_icon(self, time_of_day):
        """Get the appropriate icon for the time of day. Returns None if file not found."""
        _kiosk_dir = os.path.dirname(os.path.abspath(__file__))
        icon_map = {
            "Morning": os.path.join(_kiosk_dir, "icons", "sunrise.png"),
            "Noon": os.path.join(_kiosk_dir, "icons", "noon.png"),
            "Afternoon": os.path.join(_kiosk_dir, "icons", "noon.png"),  # Use noon for afternoon
            "Evening": os.path.join(_kiosk_dir, "icons", "evening.png"),
            "Night": os.path.join(_kiosk_dir, "icons", "night.png"),
        }
        path = icon_map.get(time_of_day)
        if path and os.path.exists(path):
            return path
        return ""


    def create_medication_widget(self):
        """Create medication widget using modular components."""
        light_blue = (0.94, 0.96, 0.98, 1)
        med = KioskWidget(background_color=light_blue,)

        title = KioskLabel(type="header", text="Medications")
        med.add_widget(title)

        med_content = KioskLabel(type="body", text="Loading medications...")
        med.add_widget(med_content)
        med.medication_content = med_content

        return med

    def create_events_widget(self):
        """Create events widget using modular components."""
        EVENTS_BG = (0.96, 0.98, 0.94, 1)
        events = KioskWidget(
            orientation="vertical",
            background_color=EVENTS_BG,
        )

        title = KioskLabel(type="header", text="Today's Events")
        events.add_widget(title)

        events_content = KioskLabel(type="body", text="Loading events...")
        events.add_widget(events_content)
        events.events_content = events_content

        return events

    def create_emergency_screen_widget(self):
        """Create emergency profile in form style. Implemented in emergency_profile.py."""
        from .emergency_profile_widget import create_emergency_layout_widget as build_emergency_layout_widget
        emergency_widget = KioskWidget()

        if not self.ice_profile_service:
            err_label = KioskLabel(type="header", text="Emergency profile service not available")
            emergency_widget.add_widget(err_label)
            return emergency_widget

        all_data = self.ice_profile_service.get_ice_profile()
        if not all_data.success or not all_data.data:
            err_label = KioskLabel(type="header", text="Emergency profile not found")
            emergency_widget.add_widget(err_label)
            return emergency_widget

        ec_result = self.ice_profile_service.get_emergency_contacts()
        if not ec_result.success or not ec_result.data:
            # create error for emergency data
            return emergency_widget

        e_data = all_data.data
        e_contacts = {
            "contacts": ec_result.data,
            "poa_name": e_data.get("poa_name"),
            "poa_phone": e_data.get("poa_phone"),
            "medical_proxy_name": ((e_data.get("emergency") or {}).get("proxy") or {}).get("name"),
            "medical_proxy_phone": e_data.get("medical_proxy_phone"),
        }

        return build_emergency_layout_widget(
            emergency_widget,
            e_data,
            e_contacts,
            self.services,
        )

    def _create_family_locations_title(self):
        """Create Family Locations screen title block."""
        title = KioskLabel(type="header", text="Family Locations")
        title.size_hint_y = None
        title.height = 70
        apply_debug_border(title)
        return title

    def _create_family_possible_places_block(self):
        """Create possible family locations block (debug)."""
        prefix = "possible family locations:\n"
        if self.location_service:
            places_result = self.location_service.get_named_places()
            if places_result.success and places_result.data:
                lines = []
                for p in places_result.data:
                    lat, lon = p.get("gps_latitude"), p.get("gps_longitude")
                    coords = (
                        f"{lat:.6f},{lon:.6f}"
                        if lat is not None and lon is not None
                        else "—"
                    )
                    lines.append(f"• {p.get('location_name', 'Unknown')}:\n   {coords}")
                suffix = "\n".join(lines)
            else:
                suffix = "(none)"
        else:
            suffix = "(unavailable)"
        widget = KioskLabel(type="body", text=prefix + suffix, shorten=False)
        widget.size_hint_x = 0.5  # for_columns

        apply_debug_border(widget)
        return widget

    def _create_family_checkins_block(self):
        """Create family check-ins block."""
        line_h = 32 + 4
        if self.location_service:
            result = self.location_service.get_checkins()
            if result.success and result.data:

                checkins_text = []
                for checkin in result.data:
                    contact_name = checkin.get("contact_name", "Unknown")
                    location = checkin.get("location_name", None)

                    if not location:
                        lat = checkin.get("latitude")
                        lon = checkin.get("longitude")
                        location = (
                            f"{lat:.6f}, {lon:.6f}"
                            if lat is not None and lon is not None
                            else "Unknown location"
                        )

                    time_str = datetime.now().strftime("%H:%M")

                    lines = [f"• {contact_name}", f"  {location} at {time_str}"]
                    checkins_text.append("\n".join(lines))

                n_lines = (
                    sum(c.count("\n") + 1 for c in checkins_text)
                    + (len(checkins_text) - 1) * 2
                )
                text = "\n\n".join(checkins_text)
            else:
                n_lines = 2
                text = "No family check-ins yet"

        else:
            n_lines = 2
            text = "Location service not available"

        widget = KioskLabel(type="body", text=text, shorten=False)
        widget.size_hint_x = 0.5  # for columns
        widget.height = max(120, int(n_lines * line_h))
        apply_debug_border(widget)
        return widget

    def _create_family_future_map_block(self):
        """Create map container; MapView is added lazily on screen enter to avoid black screen in ScreenManager."""
        map_lat = (37.0056 + 37.139) / 2
        map_lon = (-113.503 + -113.599) / 2
        container = BoxLayout(size_hint_y=0.72)
        apply_debug_border(container)
        container._map_params = {"lat": map_lat, "lon": map_lon, "zoom": 11}
        return container

    def create_family_locations_widget(self):
        """Create family location check-in widget; arranges title, possible places, and check-ins."""
        family = KioskWidget(orientation="vertical")
        apply_debug_border(family)
        family.add_widget(self._create_family_locations_title())

        columns_row = BoxLayout(orientation="horizontal", size_hint_y=0.28)
        columns_row.add_widget(self._create_family_possible_places_block())
        columns_row.add_widget(self._create_family_checkins_block())

        family.add_widget(columns_row)
        map_container = self._create_family_future_map_block()
        family.map_container = map_container
        family.add_widget(map_container)
        return family
