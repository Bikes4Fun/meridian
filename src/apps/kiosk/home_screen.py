"""
Home screen: Option 5 - Up Next, What's Next Today, side-by-side action buttons.
Owns all home presentation: structure, schedule data merge, and HTML for dynamic content.
Event modal: single source in events_handler.get_event_form_overlay_html().
"""

import html as html_module
import json
import logging
import os

from . import events_handler

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


def build_home_html(services, api_url: str, family_circle_id: str = "", kiosk_user_id: str = "") -> str:
    """Option 5: Up Next + What's Next Today + side-by-side action buttons."""
    from . import html_primitives as hp

    time_svc = services.get("time_service")
    day = time_svc.get_dayof_week().upper() if time_svc else ""
    date = time_svc.get_month_day() if time_svc else ""
    year = time_svc.get_year() if time_svc else ""
    clock_time = time_svc.get_time() if time_svc else ""
    period = time_svc.get_am_pm().upper() if time_svc else ""
    icon_map = {"Morning": "sunrise.png", "Noon": "noon.png", "Afternoon": "noon.png", "Evening": "evening.png", "Night": "night.png"}
    icon_file = icon_map.get(time_svc.get_am_pm() if time_svc else "Morning", "sunrise.png")
    icon_html = f'<img src="icons/{icon_file}" alt="" class="clock-period-icon" style="width:100px;height:100px">'

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

    items, now = load_schedule_items(services)
    up_next_html = build_up_next_html(items, now)
    timeline_html = build_timeline_html(items)
    up_next = f'<div class="up-next-card" id="up_next_content">{up_next_html}</div>'
    timeline = f'''<div class="timeline-card">
        <div class="timeline-header">WHAT'S NEXT TODAY</div>
        <div id="timeline_content" class="timeline-list">{timeline_html}</div>
        <button type="button" class="timeline-view-btn" data-screen="schedule">View Full Schedule</button>
    </div>'''
    actions = '''<div class="home-action-row">
        <button type="button" class="add-event-btn" id="addEventBtn">+ Add Event</button>
        <button type="button" class="manage-meds-btn" data-screen="medications">Manage Medications</button>
    </div>'''
    return clock + hp.spacer(24) + up_next + hp.spacer(16) + timeline + hp.spacer(16) + actions + events_handler.get_event_form_overlay_html()


def load_schedule_items(services) -> tuple[list, object]:
    """Fetch meds + events, merge into chronological items. Returns (items, now)."""
    import datetime

    med_svc = services.get("medication_service")
    cal_svc = services.get("calendar_service")
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
                items.append({
                    "type": "med",
                    "dt": dt,
                    "title": m.get("name", "?"),
                    "done": m.get("status") == "done",
                    "med_id": m.get("id"),
                    "time_slot": t,
                })
            for m in data.get("prn_medications", []):
                items.append({
                    "type": "prn",
                    "dt": now,
                    "title": m.get("name", "?"),
                    "done": m.get("status") == "taken",
                    "med_id": m.get("id"),
                    "time_slot": "prn",
                })
    if cal_svc:
        result = cal_svc.get_events_for_date(today)
        if result.success and result.data:
            for e in result.data:
                st = e.get("start_time")
                dt = now
                if st:
                    try:
                        dt = datetime.datetime.fromisoformat(str(st).replace("Z", "+00:00"))
                        if dt.tzinfo:
                            dt = dt.replace(tzinfo=None)
                    except Exception:
                        pass
                items.append({
                    "type": "event",
                    "dt": dt,
                    "title": e.get("title", "?"),
                    "done": False,
                    "display": e.get("display", e.get("title", "?")),
                    "event_id": e.get("id"),
                    "event_data": e,
                })
    items.sort(key=lambda x: x["dt"])
    return items, now


def build_up_next_html(items: list, now) -> str:
    """Build Up Next card HTML. First non-done future item, or 'All done for today'."""
    next_item = None
    for it in items:
        if not it.get("done") and it["dt"] >= now:
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
    time_str = next_item["dt"].strftime("%I:%M %p")
    icon = "💊" if next_item["type"] == "med" else "📅"
    title_esc = html_module.escape(next_item["title"])
    return f'<div class="up-next-card-inner"><span class="up-next-icon">{icon}</span><div><span class="up-next-title">{title_esc}</span><span class="up-next-sub">{time_str} • {subtext}</span></div></div>'


def build_timeline_html(items: list) -> str:
    """Build What's Next Today list: 1-2 done, 1-3 upcoming, in chronological order."""
    if not items:
        return '<div class="state-placeholder state-empty">Nothing scheduled today</div>'
    done_count = 0
    upcoming_count = 0
    shown = []
    for it in items:
        if it.get("done"):
            if done_count >= 2:
                continue
            done_count += 1
        else:
            if upcoming_count >= 3:
                continue
            upcoming_count += 1
        shown.append(it)
    result = []
    for it in shown:
        done = it.get("done")
        bar_class = "timeline-bar-med" if it["type"] in ("med", "prn") else "timeline-bar-event"
        time_str = "As needed" if it.get("type") == "prn" else it["dt"].strftime("%I:%M %p")
        check = " ✓" if done else ""
        cls = "timeline-item timeline-item-done" if done else "timeline-item"
        title = it.get("display", it.get("title", "?"))
        title_esc = html_module.escape(str(title))
        extra = ""
        if (it.get("type") in ("med", "prn")) and it.get("med_id") is not None:
            mid = html_module.escape(str(it["med_id"]))
            slot = html_module.escape(str(it.get("time_slot", "")), quote=True)
            lbl = "Uncheck" if done else ("Take" if it.get("type") == "prn" else "Check took")
            extra = f' <button type="button" class="med-taken-btn" data-med-id="{mid}" data-med-time="{slot}" data-med-done="{str(done).lower()}" style="font-size:11px;padding:2px 6px;">{lbl}</button>'
        elif it.get("type") == "event" and it.get("event_id"):
            eid = html_module.escape(str(it["event_id"]))
            edata = html_module.escape(json.dumps(it.get("event_data", {})), quote=True)
            extra = f' <button type="button" class="event-edit-btn" data-event-id="{eid}" data-event="{edata}" style="font-size:11px;padding:2px 6px;">Edit</button> <button type="button" class="event-delete-btn" data-event-id="{eid}" style="font-size:11px;padding:2px 6px;">Delete</button>'
        result.append(f'<div class="{cls}"><span class="{bar_class}"></span><span>{time_str} • {title_esc}{check}</span>{extra}</div>')
    return "\n".join(result)
