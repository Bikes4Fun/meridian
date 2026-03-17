"""
Chat screen: contact grid with chat entry.
"""


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
