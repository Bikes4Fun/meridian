"""
Screen creation logic for Dementia TV application.
Handles the creation of different application screens.
"""

import os

from config import get_database_path
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.mapview import MapView, MapMarker
from display.modular_display import (
    DementiaWidget,
    DementiaLabel,
    DementiaButton,
    DementiaNavBar,
)
from display.widgets import WidgetFactory, apply_border
from PIL import Image, ImageDraw


def _crop_image_to_circle(src_path, size=200):
    """Crop image to circle; save as PNG. Returns absolute path to output file, or None if source missing."""
    if not src_path or not os.path.exists(src_path):
        return None
    src_abs = os.path.abspath(src_path)
    out = src_abs.rsplit(".", 1)[0] + "_circle.png"
    if os.path.exists(out):
        return os.path.abspath(out)
    try:
        img = (
            Image.open(src_abs)
            .convert("RGBA")
            .resize((size, size), Image.Resampling.LANCZOS)
        )
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        out_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out_img.paste(img, mask=mask)
        out_img.save(out)
        return os.path.abspath(out)
    except Exception:
        return None


class CustomMarker(MapMarker):
    """MapMarker with fixed size for Life360-style profile photo display."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(50), dp(50))
        self.anchor_x = 0.5
        self.anchor_y = 0


class ScreenFactory:
    """Factory for creating application screens."""

    def __init__(self, services, screen_manager, display_settings=None, user_id=None):
        self.services = services
        self.screen_manager = screen_manager
        self.display_settings = display_settings
        self.user_id = user_id
        self.widget_factory = WidgetFactory(services, display_settings=display_settings)

    def create_home_screen(self):
        """Create home screen using modular components."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to ScreenFactory")

        screen = Screen(name="home")

        # Use actual user settings - no hardcoded defaults
        settings = self.display_settings

        # Main layout
        main_layout = BoxLayout(orientation=settings.home_layout)
        main_layout.size_hint = (1, 1)
        main_layout.padding = settings.main_padding

        # Navigation bar
        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)

        # Clock widget
        clock_widget = self.widget_factory.create_widget("clock")
        clock_widget.size_hint = (1, settings.clock_proportion)
        main_layout.add_widget(clock_widget)

        # Bottom section - medications and events side by side
        bottom_section = BoxLayout(orientation=settings.bottom_section_orientation)
        bottom_section.size_hint = (1, settings.todo_proportion)

        # Medications (left side)
        med_widget = self.widget_factory.create_widget("medication")
        med_widget.size_hint = (settings.med_events_split, 1)
        bottom_section.add_widget(med_widget)

        # Events (right side)
        events_widget = self.widget_factory.create_widget("events")
        events_widget.size_hint = (1 - settings.med_events_split, 1)
        bottom_section.add_widget(events_widget)

        main_layout.add_widget(bottom_section)
        screen.add_widget(main_layout)

        return screen

    def create_calendar_screen(self):
        """Create calendar screen using modular components."""
        screen = Screen(name="calendar")

        # Main layout
        main_layout = BoxLayout(orientation="vertical")
        main_layout.size_hint = (1, 1)
        main_layout.padding = self.display_settings.main_padding

        # Navigation bar
        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)

        # Calendar content area
        content_layout = BoxLayout(orientation="horizontal")
        content_layout.size_hint = (1, 1)

        # Calendar widget (left side)
        calendar_widget = self.widget_factory.create_widget("calendar")
        calendar_widget.size_hint = (0.67, 1)
        content_layout.add_widget(calendar_widget)

        # Today's events widget (right side)
        today_widget = self.widget_factory.create_widget("today_events")
        today_widget.size_hint = (0.33, 1)
        content_layout.add_widget(today_widget)

        # Link today_events_widget to widget_factory so calendar clicks can update it
        self.widget_factory.today_events_widget = today_widget

        main_layout.add_widget(content_layout)
        screen.add_widget(main_layout)

        return screen

    def create_emergency_screen(self):
        """Create emergency screen: critical patient info for EMS (name, DNR, contacts, meds, allergies)."""
        screen = Screen(name="emergency")

        main_layout = BoxLayout(orientation="vertical")
        main_layout.size_hint = (1, 1)
        main_layout.padding = self.display_settings.main_padding

        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)

        emergency_profile = self.widget_factory.create_widget("emergency_profile")
        emergency_profile.size_hint = (1, 1)
        main_layout.add_widget(emergency_profile)

        screen.add_widget(main_layout)
        return screen

    def create_more_screen(self):
        """Create more options screen using modular components."""
        screen = Screen(name="more")

        # Main layout
        main_layout = BoxLayout(orientation="vertical")
        main_layout.size_hint = (1, 1)
        main_layout.padding = self.display_settings.main_padding

        # Navigation bar
        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)

        # More content
        more_widget = DementiaWidget(
            orientation="vertical", display_settings=self.display_settings
        )
        more_widget.size_hint = (1, 1)
        apply_border(more_widget, "more", self.display_settings)

        # More title
        title = DementiaLabel(
            display_settings=self.display_settings,
            font_size="title",
            text="More Options",
        )
        more_widget.add_widget(title)

        # More content
        more_content = DementiaLabel(
            display_settings=self.display_settings,
            font_size="body",
            text="Additional features coming soon...",
        )
        more_widget.add_widget(more_content)

        main_layout.add_widget(more_widget)
        screen.add_widget(main_layout)

        return screen

    def create_family_screen(self):
        """Create family location check-in screen using modular components."""
        screen = Screen(name="family")

        # Main layout
        main_layout = BoxLayout(orientation="vertical")
        main_layout.size_hint = (1, 1)
        main_layout.padding = self.display_settings.main_padding

        # Navigation bar
        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)

        # Family location widget
        family_widget = self.widget_factory.create_widget("family_locations")
        family_widget.size_hint = (1, 1)
        main_layout.add_widget(family_widget)

        screen.add_widget(main_layout)

        # Lazy-load MapView on screen enter (avoids black screen when nested in ScreenManager)
        def on_family_enter(instance):
            container = getattr(family_widget, "map_container", None)
            if (
                container
                and not container.children
                and hasattr(container, "_map_params")
            ):
                p = container._map_params
                map_view = MapView(lat=p["lat"], lon=p["lon"], zoom=p["zoom"])
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                loc_svc = self.services.get("location_service")
                if loc_svc:
                    result = loc_svc.get_checkins()
                    if result.success and result.data:
                        for checkin in result.data:
                            lat = checkin.get("latitude")
                            lon = checkin.get("longitude")
                            if lat is None or lon is None:
                                continue
                            photo_fn = checkin.get("photo_filename")
                            if photo_fn:
                                src = (
                                    os.path.join(base, photo_fn)
                                    if not os.path.isabs(photo_fn)
                                    else photo_fn
                                )
                                circle_img = _crop_image_to_circle(src)
                                if circle_img:
                                    marker = CustomMarker(
                                        lat=lat, lon=lon, source=circle_img
                                    )
                                else:
                                    marker = MapMarker(lat=lat, lon=lon)
                            else:
                                marker = MapMarker(lat=lat, lon=lon)
                            map_view.add_marker(marker)
                container.add_widget(map_view)

        screen.bind(on_enter=on_family_enter)

        return screen

    def _create_navigation(self):
        """Create navigation bar using modular components."""
        # Navigation buttons from user settings (user-configurable)
        nav_buttons = self.display_settings.navigation_buttons

        return DementiaNavBar(
            screen_manager=self.screen_manager,
            buttons=nav_buttons,
            display_settings=self.display_settings,
        )
