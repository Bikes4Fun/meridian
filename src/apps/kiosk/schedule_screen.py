"""
Kiosk Schedule screen: merged meds + events timeline, Add Event button, event modal overlay markup.

Scope: HTML string builders only (initial paint). Live modal open/edit/prefill lives in kiosk.js (meridianKioskEvents).
Not here: calendar API calls (app / api_client), home layout.
"""

import datetime
import html as html_module
import json

from . import html_primitives as hp

# When False, kiosk users cannot create new calendar events (edits still allowed).
# Shown in UI as a family manager admin-permissions choice.
KIOSK_CALENDAR_ALLOW_CREATE_EVENTS = False
# When False, kiosk users cannot delete calendar events from the schedule screen.
KIOSK_CALENDAR_ALLOW_DELETE_EVENTS = False


class ScheduleHandler:
    """Handler for Schedule screen bridge methods."""

    def __init__(self, app):
        self._app = app

    def submit_event_form(self, payload_json: str) -> str:
        """POST/PUT calendar event via remote service. Payload may include id for update."""
        try:
            data = json.loads(payload_json)
        except json.JSONDecodeError as e:
            return str(e)
        if not data.get("title") or not data.get("start_time"):
            return "title and start_time required"
        cal = self._app.services.get_calendar_service()
        if not cal:
            return "calendar service unavailable"
        event_id = data.pop("id", None)
        if not event_id and not KIOSK_CALENDAR_ALLOW_CREATE_EVENTS:
            return (
                "Adding events from this kiosk is disabled by your family manager "
                "(admin permissions)."
            )
        if event_id:
            r = cal.update_event(str(event_id), data)
        else:
            r = cal.add_event(data)
        if r.success:
            self._app._load_home_schedule()
            self._app._refresh_schedule_if_shown()
            return "ok"
        return r.error or "failed"

    def delete_event(self, event_id: str) -> str:
        if not KIOSK_CALENDAR_ALLOW_DELETE_EVENTS:
            return (
                "Deleting events from this kiosk is disabled by your family manager "
                "(admin permissions)."
            )
        cal = self._app.services.get_calendar_service()
        if not cal:
            return "calendar service unavailable"
        r = cal.delete_event(event_id)
        if r.success:
            self._app._load_home_schedule()
            self._app._refresh_schedule_if_shown()
            return "ok"
        return r.error or "failed"


def get_event_form_overlay_html() -> str:
    """Event add/edit modal overlay only. Home adds its own Add Event button."""
    return """<div id="eventFormOverlay" class="event-overlay" style="display:none;">
<div class="event-modal" onclick="event.stopPropagation()">
<h3 id="eventFormTitle" class="event-modal-title">Add Event</h3>
<form id="eventForm">
<input type="hidden" id="eventEditingId" value="">
<input type="text" id="eventTitle" placeholder="Title" required class="event-input">
<input type="date" id="eventDate" required class="event-input">
<input type="time" id="eventStartTime" required class="event-input">
<input type="time" id="eventEndTime" placeholder="End (optional)" class="event-input">
<input type="text" id="eventLocation" placeholder="Location (optional)" class="event-input">
<textarea id="eventDescription" placeholder="Notes (optional)" rows="2" class="event-input"></textarea>
<div class="event-form-actions">
<button type="submit" class="event-btn btn-small event-btn-primary">Save</button>
<button type="button" id="eventFormCancel" class="event-btn btn-small event-btn-secondary">Cancel</button>
</div></form></div></div>"""


def get_event_modal_html() -> str:
    """Add Event button + overlay (included in Schedule nav HTML from build_schedule_html)."""
    if KIOSK_CALENDAR_ALLOW_CREATE_EVENTS:
        row = """<div class="home-action-row" style="margin-top:16px;">
<button type="button" class="add-event-btn btn-large" id="addEventBtn">+ Add Event</button>
</div>"""
    else:
        cap = html_module.escape(
            "Adding events is turned off for this kiosk. "
            "Your family manager disabled this feature in admin permissions."
        )
        row = f"""<div class="home-action-row kiosk-event-create-row kiosk-event-create-row--disabled" style="margin-top:16px;">
<button type="button" class="add-event-btn btn-large add-event-btn--disabled" id="addEventBtn" disabled aria-disabled="true">+ Add Event</button>
<p class="kiosk-event-create-disabled-caption">{cap}</p>
</div>"""
    return row + get_event_form_overlay_html()


_SVG_WK_PREV = (
    '<svg class="kiosk-schedule-week-nav-btn__icon" xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    "<polyline points=\"15 18 9 12 15 6\"/></svg>"
)
_SVG_WK_NEXT = (
    '<svg class="kiosk-schedule-week-nav-btn__icon" xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    "<polyline points=\"9 18 15 12 9 6\"/></svg>"
)


def get_schedule_week_day_cells_html(week_start: datetime.date) -> str:
    """Sun–Sat day letters + date circles for the week beginning Sunday ``week_start``."""
    today = datetime.date.today()
    letters = ("S", "M", "T", "W", "T", "F", "S")
    parts = []
    for i in range(7):
        d = week_start + datetime.timedelta(days=i)
        letter = letters[i]
        day_num = str(d.day)
        cls = "kiosk-schedule-day-stub"
        if d == today:
            cls += " kiosk-schedule-day-stub--today"
        iso = d.isoformat()
        parts.append(
            f'<div class="{cls}" title="Coming soon" data-stub-date="{html_module.escape(iso)}">'
            f'<span class="kiosk-schedule-day-stub__letter">{html_module.escape(letter)}</span>'
            f'<span class="kiosk-schedule-day-stub__circle">{html_module.escape(day_num)}</span>'
            f"</div>"
        )
    return "".join(parts)


def get_schedule_week_nav_html(week_start: datetime.date) -> str:
    """Week strip with prev/next controls (strip updates in JS; list still loads today only)."""
    ws_esc = html_module.escape(week_start.isoformat())
    cells = get_schedule_week_day_cells_html(week_start)
    return (
        '<div class="kiosk-schedule-week-nav" role="toolbar" aria-label="Change week">'
        f'<button type="button" class="kiosk-schedule-week-nav-btn" id="kioskScheduleWeekPrev" '
        f'aria-label="Previous week">{_SVG_WK_PREV}</button>'
        '<div class="kiosk-schedule-week-nav__strip-host">'
        f'<div id="kioskScheduleWeekStrip" class="kiosk-schedule-week-strip" '
        f'data-week-start="{ws_esc}" role="group" aria-label="Week preview">'
        f"{cells}</div></div>"
        f'<button type="button" class="kiosk-schedule-week-nav-btn" id="kioskScheduleWeekNext" '
        f'aria-label="Next week">{_SVG_WK_NEXT}</button>'
        "</div>"
    )


def build_schedule_html(services, api_url: str) -> str:
    """Full Schedule screen: merged meds + events timeline for today."""
    med_svc = services.get_medication_service()
    cal_svc = services.get_calendar_service()
    items = []
    today = ""
    group_times = {}
    if med_svc:
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
                items.append(
                    {
                        "type": "med",
                        "dt": dt,
                        "title": m.get("name", "?"),
                        "done": m.get("status") == "done",
                    }
                )
    if cal_svc:
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
                        "title": e.get("display", e.get("title", "?")),
                        "done": False,
                        "event_id": e.get("id"),
                        "event_data": e,
                    }
                )
    items.sort(key=lambda x: x["dt"])

    _today_nav = datetime.date.today()
    nav_week_sun = _today_nav - datetime.timedelta(days=(_today_nav.weekday() + 1) % 7)
    parts = [
        hp.kiosk_header("Full Schedule"),
        get_schedule_week_nav_html(nav_week_sun),
        hp.spacer(12),
        '<div class="kiosk-schedule-list-scroll">',
    ]
    if not items:
        parts.append(hp.empty_state("Nothing scheduled today"))
    else:
        for it in items:
            done = it.get("done")
            bar_class = (
                "timeline-bar-med" if it["type"] == "med" else "timeline-bar-event"
            )
            time_str = it["dt"].strftime("%I:%M %p")
            check = " ✓" if done else ""
            cls = "timeline-item timeline-item-done" if done else "timeline-item"
            title_esc = html_module.escape(str(it.get("title", "?")))
            extra = ""
            if it.get("type") == "event" and it.get("event_id"):
                eid = html_module.escape(str(it["event_id"]))
                edata = html_module.escape(
                    json.dumps(it.get("event_data", {})), quote=True
                )
                del_btn = ""
                if KIOSK_CALENDAR_ALLOW_DELETE_EVENTS:
                    del_btn = f' <button type="button" class="event-delete-btn" data-event-id="{eid}" style="font-size:11px;padding:2px 6px;">Delete</button>'
                extra = f' <button type="button" class="event-edit-btn" data-event-id="{eid}" data-event="{edata}" style="font-size:11px;padding:2px 6px;">Edit</button>{del_btn}'
            parts.append(
                f'<div class="{cls}"><span class="{bar_class}"></span><span>{time_str} • {title_esc}{check}</span>{extra}</div>'
            )
    parts.append("</div>")
    parts.append(get_event_modal_html())
    inner = "".join(parts)
    return f'<div class="schedule-screen">{inner}</div>'
