"""
Check-in (family locations / map) screen. Title, columns, map with markers.
MapView is lazy-loaded on screen enter.
"""

import os
import logging
from datetime import datetime

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.mapview import MapView, MapMarker

from .screen_primitives import KioskLabel, KioskWidget, apply_debug_border

logger = logging.getLogger(__name__)


def _create_title():
    """Create Family Locations screen title block."""
    title = KioskLabel(type="header", text="Family Locations")
    title.size_hint_y = None
    title.height = 70
    apply_debug_border(title)
    return title


def _create_possible_places_block(location_service):
    """Create possible family locations block (debug)."""
    prefix = "possible family locations:\n"
    if location_service:
        places_result = location_service.get_named_places()
        if places_result.success and places_result.data:
            lines = []
            for p in places_result.data:
                lat, lon = p.get("gps_latitude"), p.get("gps_longitude")
                coords = (
                    f"{lat:.6f},{lon:.6f}"
                    if lat is not None and lon is not None
                    else "—"
                )
                lines.append(f"• {p.get('location_name', 'Unknown')}:\n   {coords}")
            suffix = "\n".join(lines)
        else:
            suffix = "(none)"
    else:
        suffix = "(unavailable)"
    widget = KioskLabel(type="body", text=prefix + suffix, shorten=False)
    widget.size_hint_x = 0.5
    apply_debug_border(widget)
    return widget


def _create_checkins_block(location_service):
    """Create family check-ins block."""
    line_h = 32 + 4
    if location_service:
        result = location_service.get_checkins()
        if result.success and result.data:
            checkins_text = []
            for checkin in result.data:
                contact_name = checkin.get("contact_name", "Unknown")
                location = checkin.get("location_name", None)

                if not location:
                    lat = checkin.get("latitude")
                    lon = checkin.get("longitude")
                    location = (
                        f"{lat:.6f}, {lon:.6f}"
                        if lat is not None and lon is not None
                        else "Unknown location"
                    )

                time_str = datetime.now().strftime("%H:%M")

                lines = [f"• {contact_name}", f"  {location} at {time_str}"]
                checkins_text.append("\n".join(lines))

            n_lines = (
                sum(c.count("\n") + 1 for c in checkins_text)
                + (len(checkins_text) - 1) * 2
            )
            text = "\n\n".join(checkins_text)
        else:
            n_lines = 2
            text = "No family check-ins yet"

    else:
        n_lines = 2
        text = "Location service not available"

    widget = KioskLabel(type="body", text=text, shorten=False)
    widget.size_hint_x = 0.5
    widget.height = max(120, int(n_lines * line_h))
    apply_debug_border(widget)
    return widget


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


class CustomMarker(MapMarker):
    """MapMarker with fixed size for Life360-style profile photo display."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(50), dp(50))
        self.anchor_x = 0.5
        self.anchor_y = 0


def _create_map_container():
    """Create map container; MapView added lazily on screen enter."""
    container = BoxLayout(size_hint_y=0.72)
    apply_debug_border(container)
    return container


def build_checkin_screen(services, screen):
    """Build fully constructed check-in (family locations) widget. Wires lazy-load MapView on screen enter internally."""
    loc_svc = services.get("location_service")
    map_lat = (37.0056 + 37.139) / 2
    map_lon = (-113.503 + -113.599) / 2
    map_params = {"lat": map_lat, "lon": map_lon, "zoom": 11}
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

    widget = KioskWidget(orientation="vertical")
    apply_debug_border(widget)

    widget.add_widget(_create_title())

    columns_row = BoxLayout(orientation="horizontal", size_hint_y=0.28)
    columns_row.add_widget(_create_possible_places_block(loc_svc))
    columns_row.add_widget(_create_checkins_block(loc_svc))
    widget.add_widget(columns_row)

    map_container = _create_map_container()
    widget.map_container = map_container
    widget.add_widget(map_container)

    def on_checkin_enter(instance):
        if map_container.children:
            return
        map_view = MapView(
            lat=map_params["lat"],
            lon=map_params["lon"],
            zoom=map_params["zoom"],
            cache_dir=cache_dir,
        )
        if loc_svc:
            result = loc_svc.get_checkins()
            if result.success and result.data:
                for checkin in result.data:
                    lat = checkin.get("latitude")
                    lon = checkin.get("longitude")
                    if lat is None or lon is None:
                        continue
                    src = None
                    photo_url = checkin.get("photo_url")
                    user_id = checkin.get("user_id")
                    if (
                        photo_url
                        and user_id
                        and hasattr(loc_svc, "fetch_photo_to_cache")
                    ):
                        src = loc_svc.fetch_photo_to_cache(user_id, cache_dir)
                    if not src:
                        photo_fn = checkin.get("photo_filename")
                        if photo_fn and os.path.isabs(photo_fn):
                            src = photo_fn
                        elif photo_fn:
                            src = os.path.join(base, photo_fn)
                    if src:
                        circle_img = _crop_image_to_circle(src)
                        if circle_img:
                            marker = CustomMarker(lat=lat, lon=lon, source=circle_img)
                        else:
                            marker = MapMarker(lat=lat, lon=lon)
                    else:
                        marker = MapMarker(lat=lat, lon=lon)
                    map_view.add_marker(marker)
        map_container.add_widget(map_view)

    screen.bind(on_enter=on_checkin_enter)
    return widget
