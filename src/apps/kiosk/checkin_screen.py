"""
Check-in (family locations / map) screen. Title, columns, map with markers.
MapView is lazy-loaded on screen enter.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


def build_checkin_html(services, api_url: str, family_circle_id: str) -> tuple[str, str]:
    """Build family/checkin screen HTML and map markers JSON for pywebview. Returns (html, markers_json)."""
    from . import html_primitives as hp

    loc_svc = services.get("location_service")
    places_svc = loc_svc
    markers = []
    places_html = hp.loading_state("Loading places...")
    checkins_html = hp.loading_state("Loading check-ins...")

    if loc_svc:
        places_result = loc_svc.get_named_places()
        if places_result.success and places_result.data:
            lines = [f"• {p.get('location_name', 'Unknown')}" for p in places_result.data]
            places_html = hp.kiosk_body("\n".join(lines)) if lines else hp.empty_state("No named places")
        else:
            places_html = hp.empty_state("No named places")

        checkins_result = loc_svc.get_checkins()
        if checkins_result.success and checkins_result.data:
            lines = []
            for c in checkins_result.data:
                name = c.get("contact_name", "Unknown")
                loc = c.get("location_name") or "Unknown"
                lat = c.get("latitude")
                lon = c.get("longitude")
                if lat is not None and lon is not None:
                    markers.append({"lat": lat, "lon": lon, "name": name})
                lines.append(f"• {name}: {loc}")
            checkins_html = hp.kiosk_body("\n".join(lines)) if lines else hp.empty_state("No check-ins")
        else:
            checkins_html = hp.empty_state("No check-ins yet")

    left_panel = hp.panel(hp.kiosk_subheader("Possible family locations") + hp.spacer(16) + places_html)
    right_panel = hp.panel(hp.kiosk_subheader("Check-ins") + hp.spacer(16) + checkins_html)
    row = hp.two_column_row(left_panel, right_panel)
    map_div = '<div id="map"></div>'
    return hp.kiosk_header("Family Locations") + hp.spacer(24) + row + hp.spacer(24) + map_div, json.dumps(markers)


def _crop_image_to_circle(src_path, size=200):
    """Crop image to circle; save as PNG. Returns absolute path to output file, or None if source missing."""
    if not src_path or not os.path.exists(src_path):
        logger.warning(
            "[family map] Could not load photo for marker: %s",
            "no path provided" if not src_path else "file not found: %s" % src_path,
        )
        return None
    src_abs = os.path.abspath(src_path)
    out = src_abs.rsplit(".", 1)[0] + "_circle.png"
    if os.path.exists(out):
        return os.path.abspath(out)
    try:
        from PIL import Image, ImageDraw

        img = (
            Image.open(src_abs)
            .convert("RGBA")
            .resize((size, size), Image.Resampling.LANCZOS)
        )
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        out_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out_img.paste(img, mask=mask)
        out_img.save(out)
        return os.path.abspath(out)
    except Exception as e:
        logger.warning(
            "[family map] Failed to crop photo to circle: %s - %s", src_path, e
        )
        return None
