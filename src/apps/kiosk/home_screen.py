"""
Home screen: clock, medications, events.
"""

import logging
import os

logger = logging.getLogger(__name__)


def get_time_of_day_icon(time_of_day):
    """Get the appropriate icon for the time of day. Returns empty string if file not found."""
    _kiosk_dir = os.path.dirname(os.path.abspath(__file__))
    icon_map = {
        "Morning": os.path.join(_kiosk_dir, "icons", "sunrise.png"),
        "Noon": os.path.join(_kiosk_dir, "icons", "noon.png"),
        "Afternoon": os.path.join(_kiosk_dir, "icons", "noon.png"),
        "Evening": os.path.join(_kiosk_dir, "icons", "evening.png"),
        "Night": os.path.join(_kiosk_dir, "icons", "night.png"),
    }
    path = icon_map.get(time_of_day)
    if path and os.path.exists(path):
        return path
    return ""


def build_home_html(services, api_url: str) -> str:
    """Build home screen HTML for pywebview. Clock/med/events use ids for updateEl."""
    from . import html_primitives as hp

    time_svc = services.get("time_service")
    day = time_svc.get_dayof_week().upper() if time_svc else ""
    date = time_svc.get_month_day() if time_svc else ""
    year = time_svc.get_year() if time_svc else ""
    clock_time = time_svc.get_time() if time_svc else ""
    period = time_svc.get_am_pm().upper() if time_svc else ""
    icon_map = {"Morning": "sunrise.png", "Noon": "noon.png", "Afternoon": "noon.png", "Evening": "evening.png", "Night": "night.png"}
    icon_file = icon_map.get(time_svc.get_am_pm() if time_svc else "Morning", "sunrise.png")
    icon_html = f'<img src="../icons/{icon_file}" alt="" class="clock-period-icon" style="width:100px;height:100px">'

    clock = hp.kiosk_header(day, id_="clock-day")
    clock += '<div style="display:flex;align-items:center;gap:16px">'
    clock += hp.kiosk_subheader(period, id_="clock-period")
    clock += icon_html
    clock += "</div>"
    clock += hp.spacer(16)
    clock += hp.kiosk_hero(clock_time, id_="clock-time")
    clock += hp.spacer(8)
    clock += hp.kiosk_subheader(date, id_="clock-date")
    clock += hp.kiosk_subheader(year, id_="clock-year")

    med_content = '<div id="medication_content" class="state-placeholder state-loading">Loading medications...</div>'
    med_panel = hp.panel(
        hp.kiosk_header("Medications") + hp.spacer(16) + med_content,
        "med-panel",
    )

    events_content = '<div id="events_content" class="state-placeholder state-loading">Loading events...</div>'
    events_panel = hp.panel(
        hp.kiosk_header("Today's Events") + hp.spacer(16) + events_content,
        "events-panel",
    )

    bottom = hp.two_column_row(med_panel, events_panel)
    return clock + hp.spacer(32) + bottom
