"""
Screen creation logic for Meridian Kiosk.
Handles the creation of different kiosk screens.
"""

import os
import logging

from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.behaviors import ButtonBehavior
from kivy_garden.mapview import MapView, MapMarker
from .modular_display import (
    KioskLabel,
)
from .widgets import WidgetFactory, apply_debug_border, KioskNavBar

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_DYTE_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dyte_meeting.html")


def _dyte_html_with_token(auth_token):
    """Return full HTML string for Dyte meeting with token embedded (for pywebview)."""
    import json
    with open(_DYTE_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("__DYTE_AUTH_TOKEN__", json.dumps(auth_token))


def _run_webview_subprocess(html):
    """Run pywebview in this process (must be main thread). Used as multiprocessing.Process target."""
    try:
        import webview
        webview.create_window("Video call", html=html, width=900, height=700)
        webview.start()
    except Exception as e:
        logger.warning("WebView failed: %s", e)


class ContactCard(ButtonBehavior, BoxLayout):
    """Clickable card: photo (or placeholder) and display name. .member holds the family member dict."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.size_hint_y = None
        self.height = dp(220)
        self.member = None


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
        defaults = {}
        defaults.update(kwargs)
        super().__init__(**defaults)
        self.size_hint = (None, None)
        self.size = (dp(50), dp(50))
        self.anchor_x = 0.5
        self.anchor_y = 0


class ScreenFactory:
    """Factory for creating kiosk screens."""

    def __init__(self, services, screen_manager, user_id=None):
        self.services = services
        self.screen_manager = screen_manager
        self.user_id = user_id
        self.widget_factory = WidgetFactory(services)


    def screen_template_boxlayout(self):
        template_settings = {
            "orientation": "vertical",
            "size_hint": (1, 1),
            "padding": 24,
            "spacing": 24,
        }
        
        # Main layout
        main_layout = BoxLayout(**template_settings)

        # Navigation bar
        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)
        
        return main_layout


    def create_home_screen(self):
        """Create home screen using modular components."""
        screen = Screen(name="home")
        main_layout = self.screen_template_boxlayout()

        home_screen_top_bottom_split = .35
        # TOP SECTION
        # Clock widget
        clock_widget = self.widget_factory.create_widget("clock")
        clock_widget.size_hint = (1, home_screen_top_bottom_split)
        main_layout.add_widget(clock_widget)

        # BOTTOM SECTION - medications and events side by side
        bottom_section = BoxLayout(
            orientation="horizontal",
            size_hint = (1, 1-home_screen_top_bottom_split)
        )

        med_events_split = .5
        # Medications (left side)
        med_widget = self.widget_factory.create_widget("medication")
        med_widget.size_hint = (med_events_split, 1)
        bottom_section.add_widget(med_widget)

        # Events (right side)
        events_widget = self.widget_factory.create_widget("events")
        events_widget.size_hint = (1 - med_events_split, 1)
        bottom_section.add_widget(events_widget)

        main_layout.add_widget(bottom_section)
        
        screen.add_widget(main_layout)
        return screen


    def create_emergency_screen(self):
        """Create emergency screen: critical patient info for EMS (name, DNR, contacts, meds, allergies)."""
        screen = Screen(name="emergency")
        main_layout = self.screen_template_boxlayout()

        emergency_profile = self.widget_factory.create_widget("emergency_profile")
        emergency_profile.size_hint = (1, 1)
        main_layout.add_widget(emergency_profile)

        screen.add_widget(main_layout)
        return screen


    def create_family_screen(self):
        """Create family location check-in screen using modular components."""
        screen = Screen(name="family")
        main_layout = self.screen_template_boxlayout()

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

    def create_call_screen(self):
        """Call/contacts screen: family member photos; tap to start video call (Dyte in pywebview)."""
        import multiprocessing
        screen = Screen(name="call")
        main_layout = self.screen_template_boxlayout()

        scroll = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=2, size_hint_y=None, padding=dp(16), spacing=dp(16))
        grid.bind(minimum_height=grid.setter("height"))

        family_svc = self.services.get("family_service")
        video_svc = self.services.get("video_service")
        loc_svc = self.services.get("location_service")
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

        members = []
        if family_svc:
            result = family_svc.get_family_members()
            if result.success and result.data:
                members = result.data

        def on_member_press(instance):
            """Start video call: get token, open Dyte in pywebview (subprocess so it has main thread)."""
            if not video_svc:
                logger.warning("Video service not available")
                return
            result = video_svc.get_participant_token()
            if not result.success:
                logger.warning("Video join failed: %s", result.error)
                return
            token = result.data.get("authToken")
            if not token:
                return
            html = _dyte_html_with_token(token)
            p = multiprocessing.Process(target=_run_webview_subprocess, args=(html,))
            p.start()

        for m in members:
            card = ContactCard()
            card.member = m
            user_id = m.get("id") or ""
            display_name = m.get("display_name") or user_id or "?"
            photo_path = None
            if loc_svc and user_id and hasattr(loc_svc, "fetch_photo_to_cache"):
                photo_path = loc_svc.fetch_photo_to_cache(user_id, cache_dir)
            img = KivyImage(
                source=photo_path if photo_path else "",
                size_hint_y=0.8,
                allow_stretch=True,
                keep_ratio=True,
            )
            card.add_widget(img)
            label = KioskLabel(type="body", text=display_name)
            label.size_hint_y = 0.2
            label.halign = "center"
            card.add_widget(label)
            card.bind(on_press=on_member_press)
            grid.add_widget(card)

        scroll.add_widget(grid)
        main_layout.add_widget(scroll)
        screen.add_widget(main_layout)
        return screen

    def _create_navigation(self):
        """Create navigation bar using modular components."""
        nav_buttons = [
            {"text": "Home", "screen": "home"},
            {"text": "Emergency", "screen": "emergency"},
            {"text": "Family", "screen": "family"},
            {"text": "Call", "screen": "call"},
            {"text": "Demo", "screen": "demo"},
        ]
        return KioskNavBar(
            screen_manager=self.screen_manager,
            buttons=nav_buttons,
        )


# -------------
# DEMO SCREEN FOR TESTING DESIGN METHODS

    def _demo_header(self):
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(80),
            spacing=dp(8),
            padding=dp(8),
        )


        apply_debug_border(header, color=(0.8, 0.2, 0.2, 1))
        
        left_box = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(120), spacing=dp(8))
        left_label = KioskLabel(type="caption", text="LEFT")
        left_box.add_widget(left_label)
        apply_debug_border(left_box, color=(0.2, 0.2, 0.2, 1))
        header.add_widget(left_box)
        
        right_box = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(120), spacing=dp(8))
        right_label = KioskLabel(type="caption", text="RIGHT")
        right_box.add_widget(right_label)
        apply_debug_border(right_box, color=(0.2, 0.2, 0.2, 1))
        header.add_widget(right_box)
        
        return header

    def _demo_content(self):
        content = BoxLayout(orientation="horizontal", size_hint=(1, 1), spacing=dp(8))
        sidebar = BoxLayout(orientation="vertical", size_hint_x=0.25)
        
        # Sidebar
        sidebar_label = KioskLabel(type="caption", text="SIDEBAR")
        sidebar.add_widget(sidebar_label)
        apply_debug_border(sidebar, color=(0.2, 0.7, 0.3, 1))
        content.add_widget(sidebar)

        # Main
        main_area = BoxLayout(orientation="vertical", size_hint_x=0.75)
        main_label = KioskLabel(type="caption", text="MAIN")
        main_area.add_widget(main_label)
        apply_debug_border(main_area, color=(0.2, 0.4, 0.8, 1))
        content.add_widget(main_area)
        
        return content

    def _demo_footer(self):
        footer = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(60))
        footer_label = KioskLabel(type="caption", text="FOOTER")
        footer.add_widget(footer_label)
        apply_debug_border(footer, color=(0.9, 0.6, 0.1, 1))
        return footer

    def create_demo_screen(self):
        """Demo screen: blank boxes with labeled regions to visualize layout behavior."""
        screen = Screen(name="demo")
        main_layout = self.screen_template_boxlayout()

        main_layout.add_widget(self._demo_header())
        main_layout.add_widget(self._demo_content())
        main_layout.add_widget(self._demo_footer())

        screen.add_widget(main_layout)
        return screen

