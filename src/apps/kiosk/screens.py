"""
Screen creation logic for Meridian Kiosk.
Handles the creation of different kiosk screens.
All widget/screen settings defined here (no external display_settings).
"""

import os
import logging

from shared.config import get_database_path
from .settings import DisplaySettings

# All kiosk display/widget settings defined here
KIOSK_SETTINGS = {
    "font_sizes": {"small": 28, "medium": 40, "body": 42, "large": 56, "title": 72, "huge": 120},
    "colors": {"nav": [0.4, 0.6, 0.85, 1], "surface": [0.95, 0.95, 0.93, 1], "text": [0.1, 0.1, 0.1, 1], "error": [0.9, 0.3, 0.3, 1]},
    "spacing": {"xs": 8, "sm": 16, "md": 24, "lg": 40},
    "touch_targets": {"minimum": 60, "comfortable": 80},
    "window_width": 740,
    "window_height": 1080,
    "window_left": 10,
    "window_top": 120,
    "clock_icon_size": 100,
    "clock_icon_height": 100,
    "clock_text_height": 50,
    "clock_day_height": 60,
    "clock_time_height": 120,
    "clock_date_height": 60,
    "clock_spacing": 0,
    "clock_padding": [15, 10],
    "main_padding": [0, 10, 0, 0],
    "home_layout": "vertical",
    "clock_proportion": 0.35,
    "todo_proportion": 0.65,
    "high_contrast": False,
    "large_text": True,
    "reduced_motion": False,
    "med_events_split": 0.5,
    "navigation_height": 90,
    "button_flat_style": True,
    "clock_background_color": [0.98, 0.98, 0.96, 1],
    "med_background_color": [0.94, 0.96, 0.98, 1],
    "events_background_color": [0.96, 0.98, 0.94, 1],
    "contacts_background_color": [0.98, 0.94, 0.94, 1],
    "medical_background_color": [0.94, 0.98, 0.94, 1],
    "calendar_background_color": [0.96, 0.94, 0.98, 1],
    "nav_background_color": [0.15, 0.2, 0.3, 1],
    "clock_orientation": "vertical",
    "med_orientation": "vertical",
    "events_orientation": "vertical",
    "bottom_section_orientation": "horizontal",
    "navigation_buttons": [
        {"text": "Home", "screen": "home", "color": "text", "background_color": "nav", "font_size": "large"},
        {"text": "Calendar", "screen": "calendar", "color": "text", "background_color": "nav", "font_size": "large"},
        {"text": "Emergency", "screen": "emergency", "color": "text", "background_color": "nav", "font_size": "large"},
        {"text": "Family", "screen": "family", "color": "text", "background_color": "nav", "font_size": "large"},
        {"text": "More", "screen": "more", "color": "text", "background_color": "nav", "font_size": "large"},
    ],
    "borders": {
        "clock": {"color": [0, 0, 0, 1], "width": 1},
        "clock_top_section": {"color": [0, 0, 0, 1], "width": 1},
        "clock_day_label": {"color": [0, 0, 0, 1], "width": 1},
        "clock_time_of_day_label": {"color": [0, 0, 0, 1], "width": 1},
        "clock_icon_container": {"color": [0, 0, 0, 1], "width": 1},
        "clock_time_label": {"color": [0, 0, 0, 1], "width": 1},
        "clock_bottom_section": {"color": [0, 0, 0, 1], "width": 1},
        "clock_date_label": {"color": [0, 0, 0, 1], "width": 1},
        "clock_year_label": {"color": [0, 0, 0, 1], "width": 1},
        "calendar": {"color": [0, 0, 0, 1], "width": 1},
        "today_events": {"color": [0, 0, 0, 1], "width": 1},
        "emergency_contacts": {"color": [0, 0, 0, 1], "width": 1},
        "emergency_profile_name": {"color": [0, 0, 0, 1], "width": 1},
        "emergency_profile_dnr": {"color": [0, 0, 0, 1], "width": 1},
        "emergency_profile_medical": {"color": [0, 0, 0, 1], "width": 1},
        "emergency_profile_conditions": {"color": [0, 0, 0, 1], "width": 1},
        "emergency_profile_proxy": {"color": [0, 0, 0, 1], "width": 1},
        "emergency_profile_poa": {"color": [0, 0, 0, 1], "width": 1},
        "family_locations": {"color": [0, 0, 0, 1], "width": 1},
        "family_locations_title": {"color": [0, 0, 0, 1], "width": 1},
        "family_locations_places": {"color": [0, 0, 0, 1], "width": 1},
        "family_locations_checkins": {"color": [0, 0, 0, 1], "width": 1},
        "family_future_map": {"color": [0, 0, 0, 1], "width": 1},
        "more": {"color": [0, 0, 0, 1], "width": 1},
    },
}


def get_kiosk_settings():
    """Return DisplaySettings built from KIOSK_SETTINGS. Used by app and factories."""
    return DisplaySettings.from_dict(KIOSK_SETTINGS)
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Line
from kivy_garden.mapview import MapView, MapMarker
from .modular_display import (
    KioskWidget,
    KioskLabel,
    KioskButton,
    KioskNavBar,
)
from .widgets import WidgetFactory, apply_border
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def _apply_demo_border(widget, color=(0.2, 0.4, 0.8, 1), width=3):
    """Apply a visible border for layout demo. Color is RGBA tuple."""

    def _draw(instance, value):
        instance.canvas.after.clear()
        with instance.canvas.after:
            Color(*color)
            Line(
                rectangle=(instance.x, instance.y, instance.width, instance.height),
                width=width,
            )

    widget.bind(pos=_draw, size=_draw)


def _crop_image_to_circle(src_path, size=200):
    """Crop image to circle; save as PNG. Returns absolute path to output file, or None if source missing."""
    if not src_path or not os.path.exists(src_path):
        logger.warning(
            "[family map] Could not load photo for marker: %s",
            "no path provided" if not src_path else "file not found: %s" % src_path,
        )
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
    except Exception as e:
        logger.warning("[family map] Failed to crop photo to circle: %s - %s", src_path, e)
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
    """Factory for creating kiosk screens."""

    def __init__(self, services, screen_manager, display_settings=None, user_id=None):
        settings = get_kiosk_settings() if display_settings is None else display_settings
        self.services = services
        self.screen_manager = screen_manager
        self.display_settings = settings
        self.user_id = user_id
        self.widget_factory = WidgetFactory(services, display_settings=settings)

    def screen_template_boxlayout(self):
        s = self.display_settings
        return {
            "orientation": s.home_layout,
            "size_hint": (1, 1),
            "padding": s.main_padding,
            "spacing": s.spacing["md"],
        }


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
            if container and not container.children and hasattr(container, "_map_params"):
                p = container._map_params
                cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
                map_view = MapView(lat=p["lat"], lon=p["lon"], zoom=p["zoom"], cache_dir=cache_dir)
                base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
                loc_svc = self.services.get("location_service")
                if loc_svc:
                    result = loc_svc.get_checkins()
                    if result.success and result.data:
                        for checkin in result.data:
                            lat = checkin.get("latitude")
                            lon = checkin.get("longitude")
                            if lat is None or lon is None:
                                continue
                            src = None
                            photo_url = checkin.get("photo_url")
                            user_id = checkin.get("user_id")
                            if photo_url and user_id and hasattr(loc_svc, "fetch_photo_to_cache"):
                                src = loc_svc.fetch_photo_to_cache(user_id, cache_dir)
                            if not src:
                                photo_fn = checkin.get("photo_filename")
                                if photo_fn:
                                    if os.path.isabs(photo_fn):
                                        src = photo_fn
                                    elif "/" in photo_fn or os.path.sep in photo_fn:
                                        src = os.path.join(base, photo_fn)
                                    else:
                                        src = os.path.join(base, "dev", "demo", "data", "family_img", photo_fn)
                                    if not os.path.exists(src) and "demo/demo_data" in photo_fn:
                                        src = os.path.join(base, photo_fn.replace("demo/demo_data", "dev/demo/data"))
                                        logger.info("[family map] Using fallback path for old DB: %s", src)
                            if src:
                                circle_img = _crop_image_to_circle(src)
                                if circle_img:
                                    marker = CustomMarker(lat=lat, lon=lon, source=circle_img)
                                else:
                                    logger.warning(
                                        "[family map] Using default marker (no photo) for checkin at %s,%s",
                                        lat, lon
                                    )
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

        return KioskNavBar(
            screen_manager=self.screen_manager,
            buttons=nav_buttons,
            display_settings=self.display_settings,
        )

# -------------

    def _demo_header(self):
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(80),
            spacing=dp(8),
            padding=dp(8),
        )

        _apply_demo_border(header, color=(0.8, 0.2, 0.2, 1))
        
        left_box = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(120), spacing=dp(8))
        left_label = KioskLabel(
            display_settings=self.display_settings, font_size="body", text="LEFT"
        )
        left_label.color = (0.55, 0.55, 0.55, 1)
        left_box.add_widget(left_label)
        _apply_demo_border(left_box, color=(0.2, 0.2, 0.2, 1))
        header.add_widget(left_box)
        
        right_box = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(120), spacing=dp(8))
        right_label = KioskLabel(
            display_settings=self.display_settings, font_size="body", text="RIGHT"
        )
        right_label.color = (0.55, 0.55, 0.55, 1)
        right_box.add_widget(right_label)
        _apply_demo_border(right_box, color=(0.2, 0.2, 0.2, 1))
        header.add_widget(right_box)
        
        return header

    def _demo_content(self):
        content = BoxLayout(orientation="horizontal", size_hint=(1, 1), spacing=dp(8))
        sidebar = BoxLayout(orientation="vertical", size_hint_x=0.25)
        
        # Sidebar
        sidebar_label = KioskLabel(
            display_settings=self.display_settings, font_size="body", text="SIDEBAR"
        )
        sidebar_label.color = (0.55, 0.55, 0.55, 1)
        sidebar.add_widget(sidebar_label)
        _apply_demo_border(sidebar, color=(0.2, 0.7, 0.3, 1))
        content.add_widget(sidebar)

        # Main
        main_area = BoxLayout(orientation="vertical", size_hint_x=0.75)
        main_label = KioskLabel(
            display_settings=self.display_settings, font_size="body", text="MAIN"
        )
        main_label.color = (0.55, 0.55, 0.55, 1)
        main_area.add_widget(main_label)
        _apply_demo_border(main_area, color=(0.2, 0.4, 0.8, 1))
        content.add_widget(main_area)
        
        return content

    def _demo_footer(self):
        footer = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(60))
        footer_label = KioskLabel(
            display_settings=self.display_settings, font_size="body", text="FOOTER"
        )
        footer_label.color = (0.55, 0.55, 0.55, 1)
        footer.add_widget(footer_label)
        _apply_demo_border(footer, color=(0.9, 0.6, 0.1, 1))
        return footer

    def create_demo_screen(self):
        """Demo screen: blank boxes with labeled regions to visualize layout behavior."""
        screen = Screen(name="more")

        main = BoxLayout(**self.screen_template_boxlayout())
        main.add_widget(self._create_navigation())
        main.add_widget(self._demo_header())
        main.add_widget(self._demo_content())
        main.add_widget(self._demo_footer())

        screen.add_widget(main)
        return screen

