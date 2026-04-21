"""
Kiosk Home screen: layout, Up Next + “what’s next today” timeline, and merged schedule item loading.

Scope: merge medications + calendar into sortable items; emit HTML for injected regions; clock fragment.
Not here: event modal markup (schedule_screen), nav/screen switching (app), per-second clock updates (app), or non-home screens.
"""

import html as html_module
import json
import logging

from . import schedule_screen
from . import health_screen

logger = logging.getLogger(__name__)


def build_clock_html(services) -> str:
    """Build the full clock display HTML: day, period, icon, time, date, year."""
    from . import html_primitives as hp

    time_svc = services.get_time_service()
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


def build_home_html(
    services, api_url: str, family_circle_id: str = "", kiosk_user_id: str = ""
) -> str:
    """Home shell: clock (local) + schedule regions. MeridianKioskApp hydrates via _load_home_schedule (API)."""
    from . import html_primitives as hp

    clock = build_clock_html(services)
    up_next = f'<div class="up-next-card" id="up_next_content"><div class="up-next-card-inner">{hp.loading_state("Loading schedule…")}</div></div>'
    whats_next_header = health_screen.HealthHandler.build_home_whats_next_header_row()
    timeline = f"""<div class="timeline-card timeline-card--home-whats-next">
        {whats_next_header}
        <div id="timeline_content" class="timeline-list">{hp.loading_state("Loading schedule…")}</div>
    </div>"""
    inner = (
        clock
        + up_next
        + timeline
        + schedule_screen.get_event_form_overlay_html()
    )
    return f'<div class="home-screen">{inner}</div>'


def load_schedule_items(services) -> tuple[list, object]:
    """Fetch meds + events, merge into chronological items. Returns (items, now)."""
    import datetime

    med_svc = services.get_medication_service()
    cal_svc = services.get_calendar_service()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now = datetime.datetime.now()
    items = []
    group_times = {}
    if med_svc:
        result = med_svc.get_medication_data()
        if result.success and result.data:
            data = result.data or {}
            group_times = data.get("medication_time_groups", {})
            for m in data.get("timed_medications", []):
                t = m.get("time", "Unknown")
                gt = group_times.get(t, "23:59:59")
                try:
                    dt_str = f"{today}T{gt}"
                    dt = datetime.datetime.fromisoformat(dt_str)
                except Exception:
                    dt = now
                items.append(
                    {
                        "type": "med",
                        "dt": dt,
                        "title": m.get("name", "?"),
                        "done": m.get("status") == "done",
                        "med_id": m.get("id"),
                        "time_slot": t,
                    }
                )
            for m in data.get("prn_medications", []):
                doses = int(m.get("doses_today") or 0)
                max_raw = m.get("max_daily")
                max_d = None
                if max_raw is not None and str(max_raw).strip() != "":
                    try:
                        max_d = int(max_raw)
                        if max_d <= 0:
                            max_d = None
                    except (TypeError, ValueError):
                        max_d = None
                can_take_more = max_d is None or doses < max_d
                items.append(
                    {
                        "type": "prn",
                        "dt": now,
                        "title": m.get("name", "?"),
                        "done": m.get("status") == "taken",
                        "med_id": m.get("id"),
                        "time_slot": "prn",
                        "prn_can_take_more": can_take_more,
                    }
                )
    if cal_svc:
        result = cal_svc.get_events_for_date(today)
        if result.success and result.data:
            for e in result.data:
                st = e.get("start_time")
                dt = now
                if st:
                    try:
                        dt = datetime.datetime.fromisoformat(
                            str(st).replace("Z", "+00:00")
                        )
                        if dt.tzinfo:
                            dt = dt.replace(tzinfo=None)
                    except Exception:
                        pass
                items.append(
                    {
                        "type": "event",
                        "dt": dt,
                        "title": e.get("title", "?"),
                        "done": False,
                        "display": e.get("display", e.get("title", "?")),
                        "event_id": e.get("id"),
                        "event_data": e,
                    }
                )
    items.sort(key=lambda x: x["dt"])
    return items, now


def _item_blocks_up_next(it: dict, now) -> bool:
    """True if this row still needs attention (scheduled pending in the future, or PRN with room for more doses)."""
    if it.get("type") == "prn":
        return bool(it.get("prn_can_take_more", True))
    if it["dt"] < now:
        return False
    return not it.get("done")


def build_up_next_html(items: list, now) -> str:
    """Build Up Next card HTML. First item still needing action, or 'All done for today'."""
    next_item = None
    for it in items:
        if _item_blocks_up_next(it, now):
            next_item = it
            break
    if not next_item:
        return '<div class="up-next-card-inner"><span class="up-next-done">All done for today</span></div>'
    diff = next_item["dt"] - now
    mins = int(diff.total_seconds() / 60)
    if mins < 60:
        subtext = f"in {mins} min"
    else:
        h = mins // 60
        m = mins % 60
        subtext = f"in {h}h {m}m" if m else f"in {h} hour"
    time_str = (
        "As needed"
        if next_item.get("type") == "prn"
        else next_item["dt"].strftime("%I:%M %p")
    )
    icon = "💊" if next_item["type"] in ("med", "prn") else "📅"
    title_esc = html_module.escape(next_item["title"])
    return f'<div class="up-next-card-inner"><span class="up-next-icon">{icon}</span><div><span class="up-next-title">{title_esc}</span><span class="up-next-sub">{time_str} • {subtext}</span></div></div>'


def build_timeline_html(items: list) -> str:
    """Build What's Next Today: every item for today, chronological; list scrolls in CSS if tall."""
    if not items:
        return (
            '<div class="state-placeholder state-empty">Nothing scheduled today</div>'
        )
    result = []
    for it in items:
        done = it.get("done")
        bar_class = (
            "timeline-bar-med" if it["type"] in ("med", "prn") else "timeline-bar-event"
        )
        time_str = (
            "As needed" if it.get("type") == "prn" else it["dt"].strftime("%I:%M %p")
        )
        check = " ✓" if done else ""
        cls = "timeline-item timeline-item-done" if done else "timeline-item"
        title = it.get("display", it.get("title", "?"))
        title_esc = html_module.escape(str(title))
        extra = ""
        if it.get("type") == "med" and it.get("med_id") is not None:
            mid = html_module.escape(str(it["med_id"]))
            slot = html_module.escape(str(it.get("time_slot", "")), quote=True)
            if not done:
                extra = f'<span class="timeline-item-actions"><button type="button" class="med-taken-btn timeline-action-btn btn-small" data-med-id="{mid}" data-med-time="{slot}" data-med-done="false">Take</button></span>'
        elif it.get("type") == "prn" and it.get("med_id") is not None:
            mid = html_module.escape(str(it["med_id"]))
            slot = html_module.escape(str(it.get("time_slot", "")), quote=True)
            can_more = it.get("prn_can_take_more", True)
            if (not done) or can_more:
                extra = f'<span class="timeline-item-actions"><button type="button" class="med-taken-btn timeline-action-btn btn-small" data-med-id="{mid}" data-med-time="{slot}" data-prn-action="take" data-med-done="false">Take</button></span>'
        elif it.get("type") == "event" and it.get("event_id"):
            edata = html_module.escape(json.dumps(it.get("event_data", {})), quote=True)
            extra = f'<span class="timeline-item-actions"><button type="button" class="event-edit-btn timeline-action-btn btn-small" data-event="{edata}">Edit</button></span>'
        result.append(
            f'<div class="{cls}"><span class="{bar_class}"></span><span class="timeline-item-main">{time_str} • {title_esc}{check}</span>{extra}</div>'
        )
    return "\n".join(result)
