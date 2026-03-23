"""
Clock widget: day, date, time, and time-of-day icon (sprite).
Reusable across screens that need clock display.
"""

import datetime
import logging

logger = logging.getLogger(__name__)


def _sprite_period_from_hour(hour: int) -> str:
    """Map hour (0-23) to sprite frame: morning, noon, evening, night."""
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 14:
        return "noon"
    if 14 <= hour < 18:
        return "evening"
    return "night"


def build_clock_html(services) -> str:
    """Build the full clock display HTML: day, period, icon, time, date, year."""
    from . import html_primitives as hp

    time_svc = services.get("time_service")
    day = time_svc.get_dayof_week().upper() if time_svc else ""
    date = time_svc.get_month_day() if time_svc else ""
    year = time_svc.get_year() if time_svc else ""
    clock_time = time_svc.get_time() if time_svc else ""
    period = time_svc.get_am_pm().upper() if time_svc else ""
    sprite_period = _sprite_period_from_hour(datetime.datetime.now().hour)
    icon_html = f'<div class="clock-period-sprite" data-period="{sprite_period}" title=""></div>'

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

    return clock
