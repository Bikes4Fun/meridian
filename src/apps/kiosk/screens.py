"""
Screen creation logic for Meridian Kiosk.
Thin registry: each create_x_screen follows the same 4-line pattern.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from .screen_primitives import KioskNavBar


class ScreenFactory:
    """Factory for creating kiosk screens."""

    def __init__(
        self, services, screen_manager, kiosk_user_id: str, family_circle_id: str
    ):
        self.services = services
        self.screen_manager = screen_manager
        self.kiosk_user_id = kiosk_user_id
        self.family_circle_id = family_circle_id

    def screen_template_boxlayout(self):
        template_settings = {
            "orientation": "vertical",
            "size_hint": (1, 1),
            "padding": 24,
            "spacing": 24,
        }

        main_layout = BoxLayout(**template_settings)
        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)

        return main_layout

    def create_home_screen(self):
        """Create home screen: clock, medications, events."""
        from .home_screen import build_home_screen

        screen = Screen(name="home")
        main_layout = self.screen_template_boxlayout()

        content, clock_widget, med_widget, events_widget = build_home_screen(
            self.services
        )
        content.size_hint = (1, 1)
        main_layout.add_widget(content)

        screen.add_widget(main_layout)
        return screen, clock_widget, med_widget, events_widget

    def create_emergency_screen(self):
        """Create emergency screen: critical patient info for EMS."""
        from .emergency_screen import build_emergency_screen

        screen = Screen(name="emergency")
        main_layout = self.screen_template_boxlayout()

        emergency_profile = build_emergency_screen(self.services)
        emergency_profile.size_hint = (1, 1)
        main_layout.add_widget(emergency_profile)

        screen.add_widget(main_layout)
        return screen

    def create_checkin_screen(self):
        """Create family location check-in screen."""
        from .checkin_screen import build_checkin_screen

        screen = Screen(name="family")
        main_layout = self.screen_template_boxlayout()

        family_widget = build_checkin_screen(self.services, screen)
        family_widget.size_hint = (1, 1)
        main_layout.add_widget(family_widget)

        screen.add_widget(main_layout)
        return screen

    def create_chat_screen(self):
        """Create chat screen: contact grid with chat entry."""
        from .chat_screen import build_chat_screen

        screen = Screen(name="chat")
        main_layout = self.screen_template_boxlayout()

        content = build_chat_screen(
            self.services, self.kiosk_user_id, self.family_circle_id, screen
        )
        main_layout.add_widget(content)
        screen.add_widget(main_layout)

        return screen

    def _create_navigation(self):
        """Create navigation bar using modular components."""
        nav_buttons = [
            {"text": "Home", "screen": "home"},
            {"text": "Emergency", "screen": "emergency"},
            {"text": "Family", "screen": "family"},
            {"text": "Chat", "screen": "chat"},
        ]
        if not self.services.get("chat_entry_service"):
            nav_buttons = [b for b in nav_buttons if b["screen"] != "chat"]
        return KioskNavBar(
            screen_manager=self.screen_manager,
            buttons=nav_buttons,
        )
