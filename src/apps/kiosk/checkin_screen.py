"""
Family Locations screen. Layout: header, two columns (places, check-ins), map widget.
"""

import json
import logging

logger = logging.getLogger(__name__)


def build_checkin_html(
    services,
    api_url: str,
    family_circle_id: str,
    *,
    kiosk_user_id: str = "",
) -> tuple[str, str, str]:
    """Build Family Locations screen HTML, markers JSON, and places JSON. Uses map_widget for map."""
    from . import html_primitives as hp
    from . import map_widget

    loc_svc = services.get("location_service")
    checkins_html = hp.loading_state("Loading check-ins...")
    places = []

    if loc_svc:
        places_result = loc_svc.get_named_places()
        if places_result.success and places_result.data:
            places = [{"gps_latitude": p.get("gps_latitude"), "gps_longitude": p.get("gps_longitude"), "radius_metres": p.get("radius_metres")} for p in places_result.data]

        checkins_result = loc_svc.get_checkins()
        if checkins_result.success and checkins_result.data:
            lines = [f"• {c.get('contact_name', 'Unknown')}: {c.get('location_name') or 'Unknown'}" for c in checkins_result.data]
            checkins_html = hp.kiosk_body("\n".join(lines)) if lines else hp.empty_state("No check-ins")
        else:
            checkins_html = hp.empty_state("No check-ins yet")

    checkins_panel = hp.panel(hp.kiosk_subheader("Check-ins") + hp.spacer(16) + checkins_html)
    refresh_btn = hp.kiosk_button("Refresh", "pywebview.api.refresh_screen('family')", no_feedback=True, small=True)
    header_row = '<div class="family-locations-header-row">' + hp.kiosk_header("Family Locations") + refresh_btn + '</div>'
    top_content = header_row + hp.spacer(16) + checkins_panel + hp.spacer(16)
    map_html = map_widget.map_container_html()
    markers = map_widget.get_map_markers(
        services, api_url, family_circle_id, kiosk_user_id=kiosk_user_id
    )
    layout = (
        '<div class="family-locations-layout">'
        '<div class="family-locations-top">' + top_content + '</div>'
        + map_html +
        '</div>'
    )
    return layout, json.dumps(markers), json.dumps(places)
