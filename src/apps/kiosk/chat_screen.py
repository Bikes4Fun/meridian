"""
Chat screen: contact grid with chat entry. ChatHandler fetches entry URL for JS window.open.
"""

import logging

logger = logging.getLogger(__name__)


class ChatHandler:
    """Fetch chat entry URL for kiosk. JS opens URL with window.open."""

    def __init__(self, app):
        self._app = app

    def get_chat_url(self, sendbird_user_id: str, display_name: str) -> str:
        """Fetch chat entry URL for contact. Returns URL or empty on failure."""
        entry_svc = self._app.services.get("chat_entry_service")
        if not entry_svc:
            logger.warning("get_chat_url: no chat_entry_service")
            return ""
        r = entry_svc.get_entry_url(
            recipient_sendbird_user_id=sendbird_user_id,
            recipient_display_name=display_name,
        )
        if r.success and r.data:
            return str(r.data)
        logger.warning(f"get_chat_url failed: {getattr(r, 'error', None)}")
        return ""


def build_chat_html(services, api_url: str, kiosk_user_id: str, family_circle_id: str) -> str:
    """Build chat screen HTML for pywebview. Contact tiles use data-sb-uid/data-name; kiosk.js delegates open_chat."""
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

    base = api_url.rstrip("/")
    tiles = []
    for c in chat_contacts:
        name = c.get("display_name") or c.get("id") or "Contact"
        sb_uid = (c.get("sendbird_user_id") or "").strip()
        user_id = c.get("user_id") or ""
        contact_id = c.get("id") or ""
        avatar_src = None
        if user_id:
            avatar_src = contact_svc.fetch_photo(f"{base}/api/users/{user_id}/photo")
        if not avatar_src and contact_id:
            avatar_src = contact_svc.fetch_photo(f"{base}/api/family_circles/{family_circle_id}/contacts/{contact_id}/photo")
        tiles.append(hp.contact_tile(avatar_src, name, data_sb_uid=sb_uid, data_name=name))
    grid = "".join(tiles)
    return hp.kiosk_header("Family Chat") + hp.spacer(24) + f'<div style="display:flex;flex-wrap:wrap;gap:20px">{grid}</div>'
