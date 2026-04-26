"""
Kiosk Family Locations: screen HTML, check-in panel copy, map section + marker inputs; LocationHandler for “where is everyone”.

Scope: layout and data hooks consumed by map_widget / kiosk JS.
Not here: Leaflet init (kiosk.js), creating check-ins from this module, or location API implementation on the server.
"""

import html
import json
import logging
from datetime import datetime, timezone
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_PHONE_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false">'
    '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 3.07 9.81 '
    "19.79 19.79 0 0 1 .04 1.22 2 2 0 0 1 2 0h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11"
    'L6.09 7.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 14.92z"/>'
    "</svg>"
)

_MAP_PIN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false">'
    '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>'
    '<circle cx="12" cy="10" r="3"/>'
    "</svg>"
)

_RELOAD_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false">'
    '<path d="M23 4v6h-6"/>'
    '<path d="M1 20v-6h6"/>'
    '<path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>'
    "</svg>"
)


class LocationHandler:
    """Handler for Family/Location screen bridge methods."""

    def __init__(self, app):
        self._app = app

    def where_is_everyone(self) -> str:
        """Request family to refresh location. Returns message for user."""
        loc = self._app.services.get_location_service()
        if not loc or not hasattr(loc, "where_is_everyone"):
            return "Location request not available."
        return loc.where_is_everyone()


def _is_care_recipient(contact: dict, kiosk_user_id: str) -> bool:
    user_id = (contact.get("user_id") or "").strip()
    contact_id = (contact.get("id") or "").strip()
    relationship = (contact.get("relationship") or "").strip().lower()
    if kiosk_user_id and (user_id == kiosk_user_id or contact_id == kiosk_user_id):
        return True
    return relationship in ("care recipient", "care_recipient", "patient", "you")


def _family_member_detail_key(user_id: str, display_name: str, location: str) -> str:
    """Stable key for list rows, detail JSON, and map markers (must match across surfaces)."""
    uid = (user_id or "").strip()
    if uid:
        return uid
    n = (display_name or "").strip().lower()
    loc = (location or "").strip().lower()
    return f"n:{n}|{loc}"


def _format_last_checked_label(checkin: dict) -> str:
    raw = (
        checkin.get("last_checked_at")
        or checkin.get("checked_in_at")
        or checkin.get("checkin_at")
        or checkin.get("timestamp")
        or checkin.get("created_at")
        or checkin.get("updated_at")
        or ""
    )
    if not raw:
        return ""
    dt: Optional[datetime] = None
    if isinstance(raw, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            dt = None
    elif isinstance(raw, str):
        s = raw.strip()
        if s:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                dt = None
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 120:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    local_dt = dt.astimezone()
    return f"{local_dt.strftime('%b')} {local_dt.day}"


def _family_avatar_fragment(name: str, photo_src: Optional[str]) -> str:
    initial = (name or "?")[:1].upper()
    img_html = ""
    if photo_src:
        img_html = f'<img class="avatar" src="{html.escape(photo_src)}" alt="{html.escape(name)}">'
    return (
        '<div class="family-member-avatar avatar-wrapper">'
        f'<div class="contact-initial">{html.escape(initial)}</div>'
        f"{img_html}"
        "</div>"
    )


def _family_panel_body_fragment(
    loc_svc,
    hp,
    contacts_by_uid: dict[str, dict],
    contacts_by_name_unique: dict[str, Optional[dict]],
    checkins_data: Optional[list],
    kiosk_user_id: str,
    home_place_name: str,
) -> tuple[str, dict[str, dict]]:
    rows: list[str] = []
    details: dict[str, dict] = {}
    you_photo_src = (
        loc_svc.get_user_photo_b64((kiosk_user_id or "").strip())
        if loc_svc and kiosk_user_id
        else None
    )
    dk_you = _family_member_detail_key(kiosk_user_id, "You", home_place_name)
    details[dk_you] = {
        "display_name": "You",
        "relationship": "",
        "location": home_place_name or "Home",
        "last_seen": "",
        "phone": "",
        "photo_src": you_photo_src or "",
    }
    rows.append(
        f'<div class="family-member-row family-member-row--you" data-detail-key="{html.escape(dk_you)}">'
        f"{_family_avatar_fragment('You', you_photo_src)}"
        '<div class="family-member-main">'
        '<div class="family-member-topline">'
        '<div class="family-member-name-rel-wrap">'
        '<span class="family-member-name">You</span>'
        "</div>"
        "</div>"
        '<div class="family-member-subline">'
        f'<span class="family-member-location">{html.escape(home_place_name or "Home")}</span>'
        "</div>"
        "</div>"
        '<div class="family-member-action" aria-hidden="true"></div>'
        "</div>"
    )
    if not checkins_data:
        rows.append('<div class="family-empty-state">No locations yet</div>')
        return f'<div class="family-member-list">{"".join(rows)}</div>', details

    seen: set[str] = set()
    for c in checkins_data:
        uid = (c.get("user_id") or "").strip()
        name_raw = (c.get("contact_name") or "Unknown").strip()
        loc_raw = (c.get("location_name") or "Unknown location").strip()
        key = uid or f"{name_raw}|{loc_raw}"
        if key in seen:
            continue
        seen.add(key)

        name_key = (name_raw or "").strip().lower()
        contact = contacts_by_uid.get(uid) or contacts_by_name_unique.get(name_key) or {}
        display_name = (contact.get("display_name") or name_raw or "").strip() or "Unknown"
        relationship = (contact.get("relationship") or "").strip()
        phone = (contact.get("phone") or "").strip()
        last_checked = _format_last_checked_label(c)
        safe_name = html.escape(display_name)
        safe_relationship = html.escape(relationship)
        safe_loc = html.escape(loc_raw or "Unknown location")
        safe_phone = html.escape(phone) if phone else ""
        photo_src = loc_svc.get_user_photo_b64(uid) if uid else None
        disabled = ' disabled aria-disabled="true"' if not phone else ""
        safe_last_checked = html.escape(last_checked)
        relationship_html = (
            f'<span class="family-member-relationship">{safe_relationship}</span>'
            if safe_relationship
            else ""
        )
        last_seen_html = (
            f'<span class="family-member-last-seen">· {safe_last_checked}</span>'
            if safe_last_checked
            else ""
        )
        dk = _family_member_detail_key(uid, display_name, loc_raw)
        details[dk] = {
            "display_name": display_name,
            "relationship": relationship,
            "location": loc_raw or "Unknown location",
            "last_seen": last_checked,
            "phone": phone,
            "photo_src": photo_src or "",
        }
        rows.append(
            f'<div class="family-member-row" data-detail-key="{html.escape(dk)}">'
            f"{_family_avatar_fragment(display_name, photo_src)}"
            '<div class="family-member-main">'
            '<div class="family-member-topline">'
            '<div class="family-member-name-rel-wrap">'
            f'<span class="family-member-name">{safe_name}</span>'
            f"{relationship_html}"
            "</div>"
            "</div>"
            '<div class="family-member-subline">'
            f'<span class="family-member-location">{safe_loc}</span>'
            f"{last_seen_html}"
            "</div>"
            "</div>"
            f'<button type="button" class="timeline-action-btn btn-small contact-call-btn family-member-call-btn" data-phone="{safe_phone}" data-name="{safe_name}" aria-label="Call {safe_name}"{disabled}>{_PHONE_ICON_SVG}</button>'
            "</div>"
        )
    return f'<div class="family-member-list">{"".join(rows)}</div>', details


def build_checkin_html(
    services,
    api_url: str,
    family_circle_id: str,
    *,
    kiosk_user_id: str = "",
    runtime_cache: Any = None,
) -> tuple[str, str, str]:
    """Build Family Locations screen HTML, markers JSON, and places JSON. Uses map_widget for map."""
    from . import html_primitives as hp

    loc_svc = services.get_location_service()
    contact_svc = services.get_contact_service()
    contacts_data: Optional[list] = None
    contacts_by_uid: dict[str, dict] = {}
    contacts_by_name_unique: dict[str, Optional[dict]] = {}
    if contact_svc and family_circle_id:
        cr = contact_svc.get_contacts()
        if cr.success and cr.data:
            contacts_data = cr.data
            for c in contacts_data:
                uid = (c.get("user_id") or c.get("linked_user_id") or "").strip()
                if uid:
                    contacts_by_uid[uid] = c
                name_key = (c.get("display_name") or "").strip().lower()
                if not name_key:
                    continue
                if name_key in contacts_by_name_unique:
                    contacts_by_name_unique[name_key] = None
                else:
                    contacts_by_name_unique[name_key] = c

    places = []
    places_result = None
    checkins_result = None

    if loc_svc:
        places_result = loc_svc.get_named_places(family_circle_id)
        if places_result.success and places_result.data:
            places = [
                {
                    "gps_latitude": p.get("gps_latitude"),
                    "gps_longitude": p.get("gps_longitude"),
                    "radius_metres": p.get("radius_metres"),
                }
                for p in places_result.data
            ]

        checkins_result = loc_svc.get_checkins(family_circle_id)

    raw_places = places_result.data if places_result and places_result.success else None
    raw_checkins = checkins_result.data if checkins_result and checkins_result.success else None
    home_place_name = "Home"
    home_place = None
    if raw_places:
        for p in raw_places:
            if "home" in (p.get("location_name") or "").lower():
                home_place = p
                break
        if not home_place:
            home_place = raw_places[0]
        home_place_name = (home_place.get("location_name") or "Home").strip() or "Home"
    panel_body, family_details = _family_panel_body_fragment(
        loc_svc,
        hp,
        contacts_by_uid,
        contacts_by_name_unique,
        raw_checkins,
        kiosk_user_id,
        home_place_name,
    )
    where_onclick = (
        "var m=pywebview.api.where_is_everyone();"
        "if(m&&typeof m.then==='function')m.then(function(msg){if(msg)showToast(msg);});"
        "else if(m)showToast(m);"
    )
    family_page_actions = (
        '<div class="family-page-actions">'
        '<button type="button" class="family-panel-icon-btn" '
        'onclick="window._familyMap && window._familyMap.zoomIn()" '
        'aria-label="Zoom in">+</button>'
        '<button type="button" class="family-panel-icon-btn" '
        'onclick="window._familyMap && window._familyMap.zoomOut()" '
        'aria-label="Zoom out">\u2212</button>'
        '<button type="button" class="family-panel-icon-btn" '
        f'onclick="{html.escape(where_onclick)}" '
        f'aria-label="Where is everyone?">{_MAP_PIN_SVG}</button>'
        '<button type="button" class="family-panel-icon-btn" '
        "onclick=\"pywebview.api.reload_screen('family')\" "
        f'aria-label="Refresh">{_RELOAD_SVG}</button>'
        "</div>"
    )
    map_html = map_container_html()
    markers = get_map_markers(
        services,
        api_url,
        family_circle_id,
        kiosk_user_id=kiosk_user_id,
        places_result=places_result,
        checkins_result=checkins_result,
        contacts_by_uid=contacts_by_uid,
        contacts_by_name_unique=contacts_by_name_unique,
    )
    center: Optional[tuple[float, float]] = None
    if home_place:
        la = home_place.get("gps_latitude")
        lo = home_place.get("gps_longitude")
        if la is not None and lo is not None:
            try:
                center = (float(la), float(lo))
            except (TypeError, ValueError):
                pass
    if runtime_cache is not None:
        runtime_cache.put(
            "family_locations",
            {
                "named_places": raw_places,
                "checkins": raw_checkins,
                "map_markers": markers,
                "map_places": places,
                "center": center,
            },
        )
        if center:
            runtime_cache.put("last_map_center", center)
    details_json = json.dumps(family_details, separators=(",", ":"))
    call_icon_tpl = f'<template id="family-call-btn-svg">{_PHONE_ICON_SVG}</template>'
    details_script = (
        '<script type="application/json" id="family-member-details">'
        + details_json
        + "</script>"
    )
    layout = (
        '<div class="family-locations-layout">'
        + map_html
        + family_page_actions
        + '<div class="family-panel">'
        + '<button type="button" class="family-panel-head" aria-expanded="true" '
        + 'aria-controls="family-panel-body">'
        + '<span class="family-panel-handle" aria-hidden="true"></span>'
        + "</button>"
        + '<div class="family-panel-body" id="family-panel-body">'
        + panel_body
        + "</div>"
        + details_script
        + call_icon_tpl
        + "</div>"
        + "</div>"
    )
    return layout, json.dumps(markers), json.dumps(places)


def get_map_markers(
    services,
    api_url: str,
    family_circle_id: str,
    *,
    kiosk_user_id: str = "",
    places_result=None,
    checkins_result=None,
    contacts_by_uid: Optional[dict[str, dict]] = None,
    contacts_by_name_unique: Optional[dict[str, Optional[dict]]] = None,
) -> list:
    """Build markers for the map: patient at home, then family check-ins. Returns list of marker dicts."""
    loc_svc = services.get_location_service()
    markers = []

    if not loc_svc:
        return markers

    if places_result is None:
        places_result = loc_svc.get_named_places(family_circle_id)

    # Patient/self at home first (so map centers on them)
    home_place = None
    if places_result.success and places_result.data:
        for p in places_result.data:
            if "home" in (p.get("location_name") or "").lower():
                home_place = p
                break
        if not home_place and places_result.data:
            home_place = places_result.data[0]
    if home_place and kiosk_user_id:
        lat = home_place.get("gps_latitude")
        lon = home_place.get("gps_longitude")
        if lat is not None and lon is not None:
            photo_src = loc_svc.get_user_photo_b64((kiosk_user_id or "").strip())
            hname = home_place.get("location_name") or "Home"
            patient_m = {
                "lat": lat,
                "lon": lon,
                "name": "You",
                "is_patient": True,
                "home_place_name": hname,
                "user_id": (kiosk_user_id or "").strip(),
                "detail_key": _family_member_detail_key(kiosk_user_id, "You", hname),
            }
            if photo_src:
                patient_m["photo_src"] = photo_src
            markers.append(patient_m)

    # Family check-ins
    if checkins_result is None:
        checkins_result = loc_svc.get_checkins(family_circle_id)
    if checkins_result.success and checkins_result.data:
        for c in checkins_result.data:
            lat = c.get("latitude")
            lon = c.get("longitude")
            if lat is None or lon is None:
                continue
            name_raw = (c.get("contact_name") or "Unknown").strip()
            loc = c.get("location_name") or ""
            user_id = (c.get("user_id") or "").strip()
            photo_src = loc_svc.get_user_photo_b64((user_id or "").strip())
            display_name = name_raw
            if contacts_by_uid or contacts_by_name_unique:
                name_key = name_raw.lower()
                contact = (contacts_by_uid or {}).get(user_id) or (
                    (contacts_by_name_unique or {}).get(name_key) or {}
                )
                display_name = (
                    (contact.get("display_name") or name_raw or "").strip() or "Unknown"
                )
            loc_raw = (loc or "Unknown location").strip() or "Unknown location"
            dk = _family_member_detail_key(user_id, display_name, loc_raw)
            m = {
                "lat": lat,
                "lon": lon,
                "name": display_name,
                "location_name": loc,
                "user_id": user_id,
                "detail_key": dk,
            }
            if photo_src:
                m["photo_src"] = photo_src
            markers.append(m)

    return markers


def map_container_html(element_id: str = "map") -> str:
    """Return the map container div HTML. Default id='map' for initMap."""
    return f'<div id="{element_id}"></div>'
