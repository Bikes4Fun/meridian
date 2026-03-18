"""
Schedule screen: full merged timeline for today (meds + events).
"""

import html as html_module
import json

from . import html_primitives as hp


def build_schedule_html(services, api_url: str) -> str:
    """Build schedule screen HTML: full chronological timeline for today."""
    med_svc = services.get("medication_service")
    cal_svc = services.get("calendar_service")

    items = []
    today = ""
    group_times = {}
    if med_svc:
        import datetime

        today = datetime.datetime.now().strftime("%Y-%m-%d")
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
                    dt = datetime.datetime.now()
                items.append({
                    "type": "med",
                    "dt": dt,
                    "title": m.get("name", "?"),
                    "done": m.get("status") == "done",
                })
    if cal_svc:
        import datetime

        if not today:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
        now = datetime.datetime.now()
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
                    "title": e.get("display", e.get("title", "?")),
                    "done": False,
                    "event_id": e.get("id"),
                    "event_data": e,
                })
    items.sort(key=lambda x: x["dt"])

    parts = [hp.kiosk_header("Full Schedule"), hp.spacer(16)]
    if not items:
        parts.append(hp.empty_state("Nothing scheduled today"))
    else:
        for it in items:
            done = it.get("done")
            bar_class = "timeline-bar-med" if it["type"] == "med" else "timeline-bar-event"
            time_str = it["dt"].strftime("%I:%M %p")
            check = " ✓" if done else ""
            cls = "timeline-item timeline-item-done" if done else "timeline-item"
            title_esc = html_module.escape(str(it.get("title", "?")))
            extra = ""
            if it.get("type") == "event" and it.get("event_id"):
                eid = html_module.escape(str(it["event_id"]))
                edata = html_module.escape(json.dumps(it.get("event_data", {})), quote=True)
                extra = f' <button type="button" class="event-edit-btn" data-event-id="{eid}" data-event="{edata}" style="font-size:11px;padding:2px 6px;">Edit</button> <button type="button" class="event-delete-btn" data-event-id="{eid}" style="font-size:11px;padding:2px 6px;">Delete</button>'
            parts.append(
                f'<div class="{cls}"><span class="{bar_class}"></span><span>{time_str} • {title_esc}{check}</span>{extra}</div>'
            )
    parts.append(
        '''<div class="home-action-row" style="margin-top:16px;">
        <button type="button" class="add-event-btn" id="addEventBtn">+ Add Event</button>
        </div>
        <div id="eventFormOverlay" class="event-overlay" style="display:none;">
        <div class="event-modal" onclick="event.stopPropagation()">
        <h3 id="eventFormTitle" class="event-modal-title">Add Event</h3>
        <form id="eventForm">
        <input type="text" id="eventTitle" placeholder="Title" required class="event-input">
        <input type="date" id="eventDate" required class="event-input">
        <input type="time" id="eventStartTime" required class="event-input">
        <input type="time" id="eventEndTime" placeholder="End (optional)" class="event-input">
        <input type="text" id="eventLocation" placeholder="Location (optional)" class="event-input">
        <textarea id="eventDescription" placeholder="Notes (optional)" rows="2" class="event-input"></textarea>
        <div class="event-form-actions">
        <button type="submit" class="event-btn event-btn-primary">Save</button>
        <button type="button" id="eventFormCancel" class="event-btn event-btn-secondary">Cancel</button>
        </div></form></div></div>'''
    )
    return "".join(parts)
