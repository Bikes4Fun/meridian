"""
Events: schedule screen (Full Schedule view) + modal/form handler.
Builds schedule HTML (meds + events timeline) and handles add/edit/delete modal behavior.
"""

import datetime
import html as html_module
import json
import logging

from . import html_primitives as hp

logger = logging.getLogger(__name__)


def get_event_form_overlay_html() -> str:
    """Event add/edit modal overlay only. Home adds its own Add Event button."""
    return """<div id="eventFormOverlay" class="event-overlay" style="display:none;">
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
</div></form></div></div>"""


def get_event_modal_html() -> str:
    """Add Event button + overlay (for schedule screen)."""
    return """<div class="home-action-row" style="margin-top:16px;">
<button type="button" class="add-event-btn" id="addEventBtn">+ Add Event</button>
</div>""" + get_event_form_overlay_html()


def build_schedule_html(services, api_url: str) -> str:
    """Full Schedule screen: merged meds + events timeline for today."""
    med_svc = services.get("medication_service")
    cal_svc = services.get("calendar_service")
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

    parts = [hp.kiosk_header("Full Schedule"), hp.spacer(16)]
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
                extra = f' <button type="button" class="event-edit-btn" data-event-id="{eid}" data-event="{edata}" style="font-size:11px;padding:2px 6px;">Edit</button> <button type="button" class="event-delete-btn" data-event-id="{eid}" style="font-size:11px;padding:2px 6px;">Delete</button>'
            parts.append(
                f'<div class="{cls}"><span class="{bar_class}"></span><span>{time_str} • {title_esc}{check}</span>{extra}</div>'
            )
    parts.append(get_event_modal_html())
    return "".join(parts)


class EventsHandler:
    """Event modal and form logic. Manipulates DOM via app._eval; calls calendar service."""

    def __init__(self, app):
        self._app = app
        self._editing_event_id = None

    def open_add_event_modal(self) -> None:
        """Show Add Event modal with today. Python manipulates DOM."""
        self._editing_event_id = None
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        js = (
            f"var t=document.getElementById('eventFormTitle');if(t)t.textContent='Add Event';"
            f"var d=document.getElementById('eventDate');if(d)d.value='{today}';"
            "var o=document.getElementById('eventFormOverlay');if(o)o.style.display='flex';"
        )
        self._app._eval(js)

    def edit_event(self, event_data_json: str) -> None:
        """Prefill modal for edit. Python manipulates DOM."""
        try:
            data = json.loads(event_data_json)
        except json.JSONDecodeError:
            self._app._eval("alert('Could not load event');")
            return
        self._editing_event_id = data.get("id")
        st = data.get("start_time") or ""
        et = data.get("end_time") or ""
        date = (
            st[:10] if len(st) >= 10 else datetime.datetime.now().strftime("%Y-%m-%d")
        )
        start_time = st[11:16] if len(st) >= 16 else "09:00"
        end_time = et[11:16] if len(et) >= 16 else ""
        title = json.dumps(data.get("title") or "")
        loc = json.dumps(data.get("location") or "")
        desc = json.dumps(data.get("description") or "")
        js = (
            f"var t=document.getElementById('eventFormTitle');if(t)t.textContent='Edit Event';"
            f"var el=document.getElementById('eventTitle');if(el)el.value={title};"
            f"var d=document.getElementById('eventDate');if(d)d.value='{date}';"
            f"var s=document.getElementById('eventStartTime');if(s)s.value='{start_time}';"
            f"var e=document.getElementById('eventEndTime');if(e)e.value='{end_time}';"
            f"var l=document.getElementById('eventLocation');if(l)l.value={loc};"
            f"var r=document.getElementById('eventDescription');if(r)r.value={desc};"
            "var o=document.getElementById('eventFormOverlay');if(o)o.style.display='flex';"
        )
        self._app._eval(js)

    def submit_event_form(self, payload_json: str) -> str:
        """Add or update event via calendar service. Returns 'ok' or error."""
        try:
            data = json.loads(payload_json)
        except json.JSONDecodeError as e:
            return str(e)
        if not data.get("title") or not data.get("start_time"):
            return "title and start_time required"
        cal = self._app.services.get("calendar_service")
        if not cal:
            return "calendar service unavailable"
        if self._editing_event_id:
            r = cal.update_event(self._editing_event_id, data)
            self._editing_event_id = None
        else:
            r = cal.add_event(data)
        if r.success:
            self._app._load_home_schedule()
            self._refresh_schedule_if_shown()
            return "ok"
        return r.error or "failed"

    def add_event(self, payload_json: str) -> str:
        """POST event. Kept for backward compat."""
        return self.submit_event_form(payload_json)

    def update_event(self, event_id: str, payload_json: str) -> str:
        """PUT event."""
        self._editing_event_id = event_id
        return self.submit_event_form(payload_json)

    def delete_event(self, event_id: str) -> str:
        """DELETE event via calendar service."""
        cal = self._app.services.get("calendar_service")
        if not cal:
            return "calendar service unavailable"
        r = cal.delete_event(event_id)
        if r.success:
            self._app._load_home_schedule()
            self._refresh_schedule_if_shown()
            return "ok"
        return r.error or "failed"

    def _refresh_schedule_if_shown(self) -> None:
        """If schedule screen is shown, re-navigate to refresh."""
        self._app._eval(
            "if(document.body.dataset.screen==='schedule'&&typeof pywebview!=='undefined'&&pywebview.api&&pywebview.api.navigate)pywebview.api.navigate('schedule');"
        )
