"""
Chat screen: contact grid with chat entry. Uses KioskLabel/KioskButton for dementia-friendly styling.
"""

import os


def build_chat_html(services, api_url: str, kiosk_user_id: str, family_circle_id: str) -> str:
    """Build chat screen HTML for pywebview. Contact tiles call pywebview.api.open_chat(sb_uid, name)."""
    import json
    from . import html_primitives as hp

    contact_svc = services.get("contact_service")
    if not contact_svc or not family_circle_id:
        return hp.kiosk_header("Family Chat") + hp.spacer(16) + hp.error_state("No contacts (check server).")
    r = contact_svc.get_contacts()
    if not r.success or not r.data:
        return hp.kiosk_header("Family Chat") + hp.spacer(16) + hp.empty_state("No contacts.")
    chat_contacts = [c for c in r.data if (c.get("sendbird_user_id") or "").strip()]
    if not chat_contacts:
        return hp.kiosk_header("Family Chat") + hp.spacer(16) + hp.empty_state("No contacts with chat.")

    tiles = []
    for c in chat_contacts:
        name = c.get("display_name") or c.get("id") or "Contact"
        sb_uid = (c.get("sendbird_user_id") or "").strip()
        user_id = c.get("user_id") or ""
        onclick = f"pywebview.api.open_chat({json.dumps(sb_uid)}, {json.dumps(name)})"
        tiles.append(hp.contact_tile(api_url, name, user_id, onclick))
    grid = "".join(tiles)
    return hp.kiosk_header("Family Chat") + hp.spacer(24) + f'<div style="display:flex;flex-wrap:wrap;gap:20px">{grid}</div>'


def build_chat_screen(services, kiosk_user_id: str, family_circle_id: str, screen):
    """Build fully constructed chat screen content widget. Wires on_enter to load contacts."""
    from kivy.metrics import dp
    from kivy.uix.behaviors import ButtonBehavior
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.image import Image
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.gridlayout import GridLayout
    from .checkin_screen import _crop_image_to_circle
    from .screen_primitives import KioskLabel
    from .kiosk_metrics import scaled
    from .webview import open_chat_window

    class ContactTile(ButtonBehavior, BoxLayout):
        """Clickable tile: photo (optional) + name. orientation=vertical."""
        pass

    content = BoxLayout(orientation="vertical", padding=scaled(24), spacing=scaled(24))
    content.add_widget(
        KioskLabel(
            type="subheader", text="Family Chat", size_hint_y=None, height=scaled(48)
        )
    )
    contacts_grid = GridLayout(cols=3, spacing=scaled(20), size_hint_y=None, padding=scaled(12))
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
                    height=scaled(48),
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
                    height=scaled(48),
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
                    height=scaled(48),
                )
            )
            return
        entry_svc = services.get("chat_entry_service")
        loc_svc = services.get("location_service")
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        for c in chat_contacts:
            name = c.get("display_name") or c.get("id") or "Contact"
            sb_uid = (c.get("sendbird_user_id") or "").strip()

            def _on_contact_click(sb, nm):
                if entry_svc and kiosk_user_id and family_circle_id:
                    r = entry_svc.get_entry_url(
                        recipient_sendbird_user_id=sb,
                        recipient_display_name=nm,
                    )
                    if r.success and r.data:
                        open_chat_window(r.data)

            tile = ContactTile(orientation="vertical")
            tile.size_hint_y = None
            tile.height = scaled(140)
            avatar_size = scaled(96)
            src = None
            if c.get("user_id") and loc_svc and hasattr(loc_svc, "fetch_photo_to_cache"):
                src = loc_svc.fetch_photo_to_cache(c["user_id"], cache_dir)
            circle_img = _crop_image_to_circle(src, size=96) if src else None
            if circle_img:
                img = Image(source=circle_img, size_hint=(None, None), size=(avatar_size, avatar_size))
                tile.add_widget(img)
            else:
                initial = (name or "?")[0].upper()
                fallback = KioskLabel(
                    type="body", text=initial, size_hint=(None, None), size=(avatar_size, avatar_size),
                    halign="center", valign="middle", color=(1, 1, 1, 1)
                )
                from kivy.graphics import Color, RoundedRectangle
                with fallback.canvas.before:
                    Color(0.69, 0.69, 0.69, 1)
                    fallback._bg = RoundedRectangle(pos=fallback.pos, size=fallback.size, radius=[avatar_size / 2])
                def _update_bg(w, *_a):
                    w._bg.pos = w.pos
                    w._bg.size = w.size
                fallback.bind(pos=_update_bg, size=_update_bg)
                tile.add_widget(fallback)
            tile.add_widget(
                KioskLabel(type="body", text=name, size_hint_y=None, height=scaled(32))
            )
            tile.bind(on_press=lambda *_a, sb=sb_uid, nm=name: _on_contact_click(sb, nm))
            contacts_grid.add_widget(tile)

    screen.bind(on_enter=lambda *_a: _load_contacts())
    return content
