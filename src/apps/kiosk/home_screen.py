"""
Home screen: Option 5 - Up Next, What's Next Today, side-by-side action buttons.
Clock kept for now; will be redesigned later.
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

    up_next = '<div class="up-next-card" id="up_next_content"><div class="up-next-loading">Loading…</div></div>'
    timeline = '''<div class="timeline-card">
        <div class="timeline-header">WHAT'S NEXT TODAY</div>
        <div id="timeline_content" class="timeline-list state-placeholder">Loading…</div>
        <button type="button" class="timeline-view-btn" data-screen="schedule">View Full Schedule</button>
    </div>'''
    actions = '''<div class="home-action-row">
        <button type="button" class="add-event-btn" id="addEventBtn">+ Add Event</button>
        <button type="button" class="manage-meds-btn" data-screen="medications">Manage Medications</button>
    </div>'''
    modal_html = '''
    <div id="eventFormOverlay" class="event-overlay" style="display:none;">
        <div class="event-modal">
            <h3 class="event-modal-title">Add Event</h3>
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
                </div>
            </form>
        </div>
    </div>
    '''
    return clock + hp.spacer(24) + up_next + hp.spacer(16) + timeline + hp.spacer(16) + actions + modal_html
