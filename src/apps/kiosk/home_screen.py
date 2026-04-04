"""
Home screen: Option 5 - Up Next, What's Next Today, side-by-side action buttons.
Owns all home presentation: structure, schedule data merge, and HTML for dynamic content.
Event modal: single source in events_handler.get_event_form_overlay_html().
"""

import html as html_module
import json
import logging

from . import clock_widget
from . import events_handler

logger = logging.getLogger(__name__)


def build_home_html(
    services, api_url: str, family_circle_id: str = "", kiosk_user_id: str = ""
) -> str:
    """Up Next, today's timeline, (Health lives in footer)."""
    from . import html_primitives as hp

    clock = clock_widget.build_clock_html(services)
    items, now = load_schedule_items(services)
    up_next_html = build_up_next_html(items, now)
    timeline_html = build_timeline_html(items)
    up_next = f'<div class="up-next-card" id="up_next_content">{up_next_html}</div>'
    timeline = f"""<div class="timeline-card">
        <div class="timeline-header">WHAT'S NEXT TODAY</div>
        <div id="timeline_content" class="timeline-list">{timeline_html}</div>
    </div>"""
    inner = (
        clock
        + up_next
        + timeline
        + events_handler.get_event_form_overlay_html()
    )
    return f'<div class="home-screen">{inner}</div>'


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
                items.append(
                    {
                        "type": "prn",
                        "dt": now,
                        "title": m.get("name", "?"),
                        "done": m.get("status") == "taken",
                        "med_id": m.get("id"),
                        "time_slot": "prn",
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
        return (
            '<div class="state-placeholder state-empty">Nothing scheduled today</div>'
        )
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
        if (it.get("type") in ("med", "prn")) and it.get("med_id") is not None:
            mid = html_module.escape(str(it["med_id"]))
            slot = html_module.escape(str(it.get("time_slot", "")), quote=True)
            lbl = "Undo" if done else "Taken"
            extra = f'<span class="timeline-item-actions"><button type="button" class="med-taken-btn timeline-action-btn btn-small" data-med-id="{mid}" data-med-time="{slot}" data-med-done="{str(done).lower()}">{lbl}</button></span>'
        elif it.get("type") == "event" and it.get("event_id"):
            eid = html_module.escape(str(it["event_id"]))
            edata = html_module.escape(json.dumps(it.get("event_data", {})), quote=True)
            extra = f'<span class="timeline-item-actions"><button type="button" class="event-edit-btn timeline-action-btn btn-small" data-event="{edata}">Edit</button><button type="button" class="event-delete-btn timeline-action-btn btn-small" data-event-id="{eid}">Delete</button></span>'
        result.append(
            f'<div class="{cls}"><span class="{bar_class}"></span><span class="timeline-item-main">{time_str} • {title_esc}{check}</span>{extra}</div>'
        )
    return "\n".join(result)
