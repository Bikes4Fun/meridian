"""
Kiosk Chat: contact grid HTML; ChatHandler fetches chat entry URL and opens a separate webview.

Scope: list contacts, open_chat_window helper, bridge open_chat / open_chat_with_call.
Not here: Sendbird/session logic inside the chat web page, or contact administration APIs.
"""

import html
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def open_chat_window(url):
    """Open URL in pywebview. Uses subprocess to avoid blocking the main kiosk window."""
    if not url:
        return
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys, webview; webview.create_window('Family Chat', sys.argv[1], width=800, height=600); webview.start()",
                url,
            ]
        )
    except Exception:
        try:
            import webview

            webview.create_window("Family Chat", url, width=800, height=600)
            webview.start()
        except ImportError:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            import webbrowser

            webbrowser.open(url)


class ChatHandler:
    """Fetch chat entry URL and open in new pywebview window. JS calls open_chat (no window.open)."""

    def __init__(self, app):
        self._app = app

    def open_chat(
        self, sendbird_user_id: str, display_name: str, auto_start_call: bool = False
    ) -> None:
        """Fetch chat entry URL for contact and open in new pywebview window."""
        entry_svc = self._app.services.get_chat_entry_service()
        if not entry_svc:
            logger.warning("open_chat: no chat_entry_service")
            return
        r = entry_svc.get_entry_url(
            recipient_sendbird_user_id=sendbird_user_id,
            recipient_display_name=display_name,
            auto_start_call=auto_start_call,
        )
        if r.success and r.data:
            open_chat_window(str(r.data))
        else:
            logger.warning("open_chat failed: %s", getattr(r, "error", None))


def build_chat_html(
    services, api_url: str, kiosk_user_id: str, family_circle_id: str
) -> str:
    """Build chat screen HTML for pywebview. Contact tiles use data-sb-uid/data-name; kiosk.js delegates open_chat."""
    from . import html_primitives as hp
    from .api_client import fetch_photo_b64

    contact_svc = services.get_contact_service()
    if not contact_svc or not family_circle_id:
        return hp.kiosk_screen_blocked(
            "Family Chat", hp.error_state("No contacts (check server).")
        )
    r = contact_svc.get_contacts()
    if not r.success or not r.data:
        return hp.kiosk_screen_blocked(
            "Family Chat", hp.empty_state("No contacts.")
        )
    def _is_care_recipient(contact: dict) -> bool:
        user_id = (contact.get("user_id") or "").strip()
        contact_id = (contact.get("id") or "").strip()
        relationship = (contact.get("relationship") or "").strip().lower()
        if kiosk_user_id and (user_id == kiosk_user_id or contact_id == kiosk_user_id):
            return True
        return relationship in ("care recipient", "care_recipient", "patient", "you")

    chat_contacts = [
        c
        for c in r.data
        if (c.get("sendbird_user_id") or "").strip() and not _is_care_recipient(c)
    ]
    if not chat_contacts:
        return hp.kiosk_screen_blocked(
            "Family Chat", hp.empty_state("No contacts with chat.")
        )

    base = api_url.rstrip("/")
    tiles = []
    for c in chat_contacts:
        name = c.get("display_name") or c.get("id") or "Contact"
        sb_uid = (c.get("sendbird_user_id") or "").strip()
        user_id = c.get("user_id") or ""
        contact_id = c.get("id") or ""
        avatar_src = None
        if user_id:
            avatar_src = fetch_photo_b64(
                f"{base}/api/users/{user_id}/photo",
                contact_svc._session,
                contact_svc._headers,
            )
        if not avatar_src and contact_id:
            avatar_src = fetch_photo_b64(
                f"{base}/api/family_circles/{family_circle_id}/contacts/{contact_id}/photo",
                contact_svc._session,
                contact_svc._headers,
            )
        tile = hp.contact_tile(avatar_src, name, data_sb_uid=sb_uid, data_name=name)
        safe_sb_uid = html.escape(sb_uid)
        safe_name = html.escape(name)
        action_row = (
            '<div class="chat-contact-actions">'
            f'<button type="button" class="timeline-action-btn btn-small contact-call-btn" data-sb-uid="{safe_sb_uid}" data-name="{safe_name}">📞 VOICE CALL</button>'
            "</div>"
        )
        tiles.append(
            f'<div class="chat-contact-card">{tile}{action_row}</div>'
        )
    grid = "".join(tiles)
    return (
        hp.kiosk_header("Family Chat")
        + hp.spacer(24)
        + f'<div class="chat-contact-grid">{grid}</div>'
    )
