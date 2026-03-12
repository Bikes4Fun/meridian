from datetime import datetime

from kivy.uix.boxlayout import BoxLayout

from apps.kiosk.modular_display import KioskLabel
from apps.kiosk.widgets import apply_debug_border


def _create_family_locations_title():
    """Create Family Locations screen title block."""
    title = KioskLabel(type="header", text="Family Locations")
    title.size_hint_y = None
    title.height = 70
    apply_debug_border(title)
    return title


def _create_family_possible_places_block(location_service):
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
    widget.size_hint_x = 0.5  # for_columns

    apply_debug_border(widget)
    return widget


def _create_family_checkins_block(location_service):
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
    widget.size_hint_x = 0.5  # for columns
    widget.height = max(120, int(n_lines * line_h))
    apply_debug_border(widget)
    return widget


def _create_family_future_map_block():
    """Create map container; MapView is added lazily on screen enter to avoid black screen in ScreenManager."""
    map_lat = (37.0056 + 37.139) / 2
    map_lon = (-113.503 + -113.599) / 2
    container = BoxLayout(size_hint_y=0.72)
    apply_debug_border(container)
    container._map_params = {"lat": map_lat, "lon": map_lon, "zoom": 11}
    return container


def build_map_screen(map_screen_widget, location_service):

    map_screen_widget.add_widget(_create_family_locations_title())

    columns_row = BoxLayout(orientation="horizontal", size_hint_y=0.28)
    columns_row.add_widget(_create_family_possible_places_block(location_service))
    columns_row.add_widget(_create_family_checkins_block(location_service))

    map_screen_widget.add_widget(columns_row)
    map_container = _create_family_future_map_block()
    map_screen_widget.map_container = map_container
    map_screen_widget.add_widget(map_container)

    return map_screen_widget
