"""
Chat screen: contact grid with chat entry. Uses KioskLabel/KioskButton for dementia-friendly styling.
"""

import os
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior

from .screen_primitives import KioskLabel, KioskButton
from .webview import open_chat_window


class ContactTile(ButtonBehavior, BoxLayout):
    """Clickable tile with optional photo and name for chat contact grid."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_background()

    def _setup_background(self):
        from kivy.graphics import Color, Rectangle
        with self.canvas.before:
            Color(0.4, 0.6, 0.85, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args):
        if hasattr(self, "_bg_rect"):
            self._bg_rect.pos = self.pos
            self._bg_rect.size = self.size


def build_chat_screen(services, kiosk_user_id: str, family_circle_id: str, screen):
    """Build fully constructed chat screen content widget. Wires on_enter to load contacts."""
    content = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(24))
    content.add_widget(
        KioskLabel(
            type="subheader", text="Family Chat", size_hint_y=None, height=dp(48)
        )
    )
    contacts_grid = GridLayout(cols=3, spacing=dp(12), size_hint_y=None, padding=dp(8))
    contacts_grid.bind(minimum_height=contacts_grid.setter("height"))
    scroll = ScrollView(size_hint=(1, 1))
    scroll.add_widget(contacts_grid)
    content.add_widget(scroll)

    def _load_contacts():
        contacts_grid.clear_widgets()
        contact_svc = services.get("contact_service") if services else None
        if not contact_svc or not family_circle_id:
            contacts_grid.add_widget(
                KioskLabel(
                    type="body",
                    text="No contacts (check server).",
                    size_hint_y=None,
                    height=dp(48),
                )
            )
            return
        r = contact_svc.get_contacts()
        if not r.success or not r.data:
            contacts_grid.add_widget(
                KioskLabel(
                    type="body",
                    text="No contacts.",
                    size_hint_y=None,
                    height=dp(48),
                )
            )
            return
        chat_contacts = [c for c in r.data if (c.get("sendbird_user_id") or "").strip()]
        if not chat_contacts:
            contacts_grid.add_widget(
                KioskLabel(
                    type="body",
                    text="No contacts with chat.",
                    size_hint_y=None,
                    height=dp(48),
                )
            )
            return
        entry_svc = services.get("chat_entry_service")
        loc_svc = services.get("location_service")
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        for c in chat_contacts:
            name = c.get("display_name") or c.get("id") or "Contact"
            sb_uid = (c.get("sendbird_user_id") or "").strip()
            user_id = c.get("user_id", "")
            photo_path = None
            if user_id and loc_svc and hasattr(loc_svc, "fetch_photo_to_cache"):
                photo_path = loc_svc.fetch_photo_to_cache(user_id, cache_dir)

            def _on_contact_click(sb, nm):
                if entry_svc and kiosk_user_id and family_circle_id:
                    r = entry_svc.get_entry_url(
                        recipient_sendbird_user_id=sb,
                        recipient_display_name=nm,
                    )
                    if r.success and r.data:
                        open_chat_window(r.data)

            tile = ContactTile(
                orientation="vertical",
                size_hint_y=None,
                height=dp(120),
                padding=dp(2),
                spacing=0,
            )
            if photo_path and os.path.exists(photo_path):
                img = Image(
                    source=photo_path,
                    size_hint_y=1,
                    allow_stretch=True,
                    keep_ratio=False,
                )
                tile.add_widget(img)
            lbl = KioskLabel(
                text=name,
                type="body",
                size_hint_y=None,
                height=dp(28),
                font_size=KioskLabel._TYPES["body"]["font_size"],
            )
            tile.add_widget(lbl)
            tile.bind(on_press=lambda *_a, sb=sb_uid, nm=name: _on_contact_click(sb, nm))
            contacts_grid.add_widget(tile)

    screen.bind(on_enter=lambda *_a: _load_contacts())
    return content
