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
from kivy.graphics import Color, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


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


class WidgetFactory:
    """Factory for creating UI widgets based on user preferences."""

    def __init__(self, services):
        self.services = services
        self.time_service = services.get("time_service")
        self.calendar_service = services.get("calendar_service")
        self.emergency_service = services.get("emergency_service")
        self.medication_service = services.get("medication_service")
        self.location_service = services.get("location_service")

    # TODO create_widget seem duplicated with specific widgets? Is is needed from a best practices + KISS perspective?
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
            "Afternoon": os.path.join(
                _kiosk_dir, "icons", "noon.png"
            ),  # Use noon for afternoon
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
        med = KioskWidget(
            background_color=light_blue,
        )

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
        from .emergency_profile_widget import (
            create_emergency_layout_widget as build_emergency_layout_widget,
        )

        # TODO: why are we renaming a function to use as a new name?
        emergency_widget = KioskWidget()

        if not self.emergency_service:
            err_label = KioskLabel(
                type="header", text="Emergency profile service not available"
            )
            emergency_widget.add_widget(err_label)
            return emergency_widget

        all_data = self.emergency_service.get_emergency_profile()
        if not all_data.success or not all_data.data:
            err_label = KioskLabel(type="header", text="Emergency profile not found")
            emergency_widget.add_widget(err_label)
            return emergency_widget

        e_data = all_data.data
        e_contacts = {
            "contacts": e_data.get("emergency_contacts") or [],
            "poa_name": e_data.get("poa_name"),
            "poa_phone": e_data.get("poa_phone"),
            "medical_proxy_name": (
                (e_data.get("emergency") or {}).get("proxy") or {}
            ).get("name"),
            "medical_proxy_phone": e_data.get("medical_proxy_phone"),
        }

        return build_emergency_layout_widget(
            emergency_widget,
            e_data,
            e_contacts,
            self.services,
        )

    def create_family_locations_widget(self):
        """Create family location check-in widget; arranges title, possible places, and check-ins."""
        from .map_screen import build_map_screen

        map_screen_widget = KioskWidget(orientation="vertical")
        apply_debug_border(map_screen_widget)

        built_map_screen = build_map_screen(map_screen_widget, self.location_service)
        return built_map_screen
