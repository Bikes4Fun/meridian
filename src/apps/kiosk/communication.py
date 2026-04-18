"""
Kiosk Chat: contact grid HTML and voice-call actions.

Scope: list contacts and trigger voice calls.
Not here: Twilio/session logic inside the chat web page, or contact administration APIs.
"""

import html
import logging
import os
import re

from .html_primitives import avatar_img

logger = logging.getLogger(__name__)
_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class ChatHandler:
    """Handle chat screen voice-call actions from the kiosk UI."""

    def __init__(self, app):
        self._app = app

    def _clean_call_error(self, err: str) -> str:
        cleaned = _ANSI_ESCAPE_RE.sub("", (err or "")).strip()
        low = cleaned.lower()
        if "trial accounts may only make calls to verified numbers" in low:
            return "Call failed: destination number is not verified in Twilio trial account."
        if "twilio not configured" in low:
            return "Voice calling unavailable: Twilio is not configured on the server."
        if "503" in low:
            return "Voice calling unavailable (server 503)."
        return cleaned or "call failed"

    def call_phone(self, phone: str, display_name: str = "") -> str:
        """Trigger a voice call for this contact via server Twilio route."""
        voice_svc = self._app.services.get_voice_service()
        if not voice_svc:
            return "voice service unavailable"
        r = voice_svc.place_call(phone)
        if r.success:
            who = (display_name or phone or "contact").strip()
            return f"Calling {who}"
        err = (r.error or "").strip()
        logger.warning(f"Voice call failed for {phone}: {err or 'unknown error'}")
        return self._clean_call_error(err)


def contact_tile(
    avatar_src, name, onclick_js=None, relationship="", data_contact_id="", data_name=""
):
    """Person/contact card. avatar_src = data URI from fetch_photo_b64."""
    initial = (name or "?")[0].upper()
    name_escaped = html.escape(str(name or "Contact"))
    img_tag = avatar_img(avatar_src, name)
    rel_part = (
        f'<div class="contact-relationship">{html.escape(str(relationship))}</div>'
        if relationship
        else ""
    )
    avatar_block = f'<div class="avatar-wrapper"><div class="contact-initial">{html.escape(initial)}</div>{img_tag}</div>'
    if data_contact_id or data_name:
        cid = (
            f' data-contact-id="{html.escape(str(data_contact_id))}"'
            if data_contact_id
            else ""
        )
        nm = f' data-name="{html.escape(str(data_name))}"' if data_name else ""
        return f'<div class="contact-tile" role="button"{cid}{nm}>{avatar_block}<div class="contact-name">{name_escaped}</div>{rel_part}</div>'
    return f'<div class="contact-tile" onclick="{onclick_js}">{avatar_block}<div class="contact-name">{name_escaped}</div>{rel_part}</div>'


def contact_widget(c, contact_svc, hp) -> str:
    # build each contact card

    name = c.get("display_name") or c.get("id") or "Contact"
    phone = (c.get("phone") or "").strip()
    user_id = c.get("user_id") or ""
    contact_id = c.get("id") or ""
    # Inline base64 avatars mean one HTTP GET per photo through the API (slow on ngrok/Qt).
    # Initials-only is instant; set MERIDIAN_KIOSK_CHAT_AVATARS=1 to fetch photos (slower).
    avatar_src = None
    if (os.environ.get("MERIDIAN_KIOSK_CHAT_AVATARS") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        avatar_src = contact_svc.get_best_contact_photo_b64(user_id, contact_id)
    tile = contact_tile(avatar_src, name, data_name=name)
    safe_phone = html.escape(phone)
    safe_name = html.escape(name)
    disabled = ' disabled aria-disabled="true"' if not phone else ""
    label = "📞 VOICE CALL" if phone else "NO PHONE"

    action_row = (
        '<div class="chat-contact-actions">'
        f'<button type="button" class="timeline-action-btn btn-small contact-call-btn" data-phone="{safe_phone}" data-name="{safe_name}"{disabled}>{label}</button>'
        "</div>"
    )

    return f'<div class="chat-contact-card">{tile}{action_row}</div>'


def build_chat_html(
    services, api_url: str, kiosk_user_id: str, family_circle_id: str
) -> str:
    """Build chat screen HTML for pywebview. Contact cards include optional voice actions."""
    from . import html_primitives as hp

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
        if not _is_care_recipient(c) and (c.get("phone") or "").strip()
    ]
    if not chat_contacts:
        return hp.kiosk_screen_blocked(
            "Family Chat", hp.empty_state("No contacts with phone numbers.")
        )

    tiles = []

    for c in chat_contacts:
        tiles.append(contact_widget(c, contact_svc, hp))

    grid = "".join(tiles)
    return (
        hp.kiosk_header("Family Chat")
        + hp.spacer(24)
        + f'<div class="chat-contact-grid">{grid}</div>'
    )
