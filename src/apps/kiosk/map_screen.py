"""
Kiosk Family Locations: screen HTML, check-in panel copy, map section + marker inputs; LocationHandler for “where is everyone”.

Scope: layout and data hooks consumed by map_widget / kiosk JS.
Not here: Leaflet init (kiosk.js), creating check-ins from this module, or location API implementation on the server.
"""

import html
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


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


def _family_voice_grid_fragment(
    services,
    hp,
    kiosk_user_id: str,
    family_circle_id: str,
    contacts_data: Optional[list],
) -> str:
    from .communication import contact_widget

    contact_svc = services.get_contact_service()
    if not contact_svc or not family_circle_id or not contacts_data:
        return ""
    chat_contacts = [
        c
        for c in contacts_data
        if not _is_care_recipient(c, kiosk_user_id)
        and (c.get("phone") or "").strip()
    ]
    if not chat_contacts:
        return ""
    tiles = [contact_widget(c, contact_svc, hp) for c in chat_contacts]
    grid = "".join(tiles)
    return (
        hp.spacer(20)
        + hp.kiosk_subheader("Family voices")
        + hp.spacer(12)
        + f'<div class="chat-contact-grid">{grid}</div>'
    )


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
    if contact_svc and family_circle_id:
        cr = contact_svc.get_contacts()
        if cr.success and cr.data:
            contacts_data = cr.data
            for c in contacts_data:
                uid = (c.get("user_id") or "").strip()
                if uid:
                    contacts_by_uid[uid] = c

    checkins_html = hp.loading_state("Loading check-ins...")
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
        if checkins_result.success and checkins_result.data:
            rows_html: list[str] = []
            for c in checkins_result.data:
                name_raw = c.get("contact_name") or "Unknown"
                loc_raw = c.get("location_name") or "Unknown"
                uid = (c.get("user_id") or "").strip()
                contact = contacts_by_uid.get(uid, {})
                phone = (contact.get("phone") or "").strip()
                display_name = (contact.get("display_name") or name_raw or "").strip()
                safe_name = html.escape(display_name)
                safe_phone = html.escape(phone) if phone else ""
                name_esc = html.escape(str(name_raw))
                loc_esc = html.escape(str(loc_raw))
                if phone:
                    btn = (
                        '<button type="button" class="timeline-action-btn btn-small contact-call-btn" '
                        f'data-phone="{safe_phone}" data-name="{safe_name}">📞 Call</button>'
                    )
                else:
                    btn = (
                        '<button type="button" class="timeline-action-btn btn-small" '
                        'disabled aria-disabled="true">No phone</button>'
                    )
                rows_html.append(
                    '<div class="family-checkin-row">'
                    f'<span class="family-checkin-line">{name_esc}: {loc_esc}</span>'
                    f'<div class="family-checkin-actions">{btn}</div>'
                    "</div>"
                )
            checkins_html = (
                f'<div class="family-checkins-list">{"".join(rows_html)}</div>'
                if rows_html
                else hp.empty_state("No check-ins")
            )
        else:
            checkins_html = hp.empty_state("No check-ins yet")

    voice_grid = _family_voice_grid_fragment(
        services, hp, kiosk_user_id, family_circle_id, contacts_data
    )
    checkins_panel = hp.panel(
        hp.kiosk_subheader("Check-ins")
        + hp.spacer(16)
        + checkins_html
        + voice_grid
    )
    refresh_btn = hp.kiosk_button(
        "Refresh",
        "pywebview.api.reload_screen('family')",
        no_feedback=True,
        small=True,
    )
    where_btn = hp.kiosk_button(
        "Where is everyone?",
        "var m=pywebview.api.where_is_everyone();"
        "if(m&&typeof m.then==='function')m.then(function(msg){if(msg)showToast(msg);});"
        "else if(m)showToast(m);",
        no_feedback=False,
        small=True,
    )
    header_row = (
        '<div class="family-locations-header-row">'
        + hp.kiosk_header("Family Locations")
        + refresh_btn
        + where_btn
        + "</div>"
    )
    top_content = header_row + hp.spacer(16) + checkins_panel + hp.spacer(16)
    map_html = map_container_html()
    markers = get_map_markers(
        services,
        api_url,
        family_circle_id,
        kiosk_user_id=kiosk_user_id,
        places_result=places_result,
        checkins_result=checkins_result,
    )
    raw_places = places_result.data if places_result and places_result.success else None
    raw_checkins = checkins_result.data if checkins_result and checkins_result.success else None
    center: Optional[tuple[float, float]] = None
    if raw_places:
        home_place = None
        for p in raw_places:
            if "home" in (p.get("location_name") or "").lower():
                home_place = p
                break
        if not home_place:
            home_place = raw_places[0]
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
    layout = (
        '<div class="family-locations-layout">'
        '<div class="family-locations-top">'
        + top_content
        + "</div>"
        + map_html
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
            patient_m = {
                "lat": lat,
                "lon": lon,
                "name": "You",
                "is_patient": True,
                "home_place_name": home_place.get("location_name") or "Home",
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
            name = c.get("contact_name", "Unknown")
            loc = c.get("location_name") or ""
            user_id = c.get("user_id") or ""
            photo_src = loc_svc.get_user_photo_b64((user_id or "").strip())
            m = {"lat": lat, "lon": lon, "name": name, "location_name": loc}
            if photo_src:
                m["photo_src"] = photo_src
            markers.append(m)

    return markers


def map_container_html(element_id: str = "map") -> str:
    """Return the map container div HTML. Default id='map' for initMap."""
    return f'<div id="{element_id}"></div>'
