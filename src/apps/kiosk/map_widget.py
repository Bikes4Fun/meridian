"""
Map widget: builds location markers and map container HTML.
Reusable across screens (Family Locations, future map views).
"""

import json
import logging

logger = logging.getLogger(__name__)


def get_map_markers(
    services,
    api_url: str,
    family_circle_id: str,
    *,
    kiosk_user_id: str = "",
) -> list:
    """Build markers for the map: patient at home, then family check-ins. Returns list of marker dicts."""
    loc_svc = services.get("location_service")
    markers = []

    if not loc_svc:
        return markers

    places_result = loc_svc.get_named_places()
    base = api_url.rstrip("/")

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
            photo_src = loc_svc.fetch_photo(f"{base}/api/users/{kiosk_user_id}/photo") if base else None
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
    checkins_result = loc_svc.get_checkins()
    if checkins_result.success and checkins_result.data:
        for c in checkins_result.data:
            lat = c.get("latitude")
            lon = c.get("longitude")
            if lat is None or lon is None:
                continue
            name = c.get("contact_name", "Unknown")
            loc = c.get("location_name") or ""
            user_id = c.get("user_id") or ""
            photo_src = loc_svc.fetch_photo(f"{base}/api/users/{user_id}/photo") if base and user_id else None
            m = {"lat": lat, "lon": lon, "name": name, "location_name": loc}
            if photo_src:
                m["photo_src"] = photo_src
            markers.append(m)

    return markers


def map_container_html(element_id: str = "map") -> str:
    """Return the map container div HTML. Default id='map' for initMap."""
    return f'<div id="{element_id}"></div>'
