"""
Clock widget: day, date, time, and time-of-day icon (sprite).
Reusable across screens that need clock display.
"""

import logging

logger = logging.getLogger(__name__)


def build_clock_html(services) -> str:
    """Build the full clock display HTML: day, period, icon, time, date, year."""
    from . import html_primitives as hp

    time_svc = services.get("time_service")
    day = time_svc.get_dayof_week().upper() if time_svc else ""
    date = time_svc.get_month_day() if time_svc else ""
    year = time_svc.get_year() if time_svc else ""
    clock_time = time_svc.get_time() if time_svc else ""
    if time_svc and getattr(time_svc, "get_day_period", None):
        period, sprite_period = time_svc.get_day_period()
        period = period.upper()
    else:
        period = (time_svc.get_am_pm().upper() if time_svc else "")
        sprite_period = "night"
    icon_html = f'<div class="clock-period-sprite" data-period="{sprite_period}" title=""></div>'

    clock = '<div id="clock-main">'
    clock += hp.kiosk_subheader(day, id_="clock-day")
    clock += hp.kiosk_hero(clock_time, id_="clock-time")
    date_line = time_svc.get_clock_date_line() if time_svc and getattr(time_svc, "get_clock_date_line", None) else f"{date}, {year}"
    clock += hp.kiosk_body_large(date_line, id_="clock-date")
    clock += "</div>"

    sprite_and_text = '<div id="sprite-and-text">'
    sprite_and_text += icon_html
    sprite_and_text += hp.kiosk_caption(period, id_="clock-period")
    sprite_and_text += "</div>"

    return f'<div class="clock-container">{clock}{sprite_and_text}</div>'
