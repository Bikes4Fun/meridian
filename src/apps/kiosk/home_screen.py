"""
Home screen: clock, medications, events.
"""

from .screen_primitives import KioskWidget, KioskLabel, KioskButton, apply_debug_border
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
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


def build_home_screen(services):
    """Build home screen content: clock, medications, events. Returns (content_widget, clock_widget, med_widget, events_widget)."""
    home_screen_top_bottom_split = 0.35
    med_events_split = 0.5

    clock_widget = _create_clock_widget(services)
    clock_widget.size_hint = (1, home_screen_top_bottom_split)

    med_widget = _create_medication_widget()
    med_widget.size_hint = (med_events_split, 1)

    events_widget = _create_events_widget()
    events_widget.size_hint = (1 - med_events_split, 1)

    bottom_section = BoxLayout(
        orientation="horizontal", size_hint=(1, 1 - home_screen_top_bottom_split)
    )
    bottom_section.add_widget(med_widget)
    bottom_section.add_widget(events_widget)

    content = BoxLayout(orientation="vertical")
    content.add_widget(clock_widget)
    content.add_widget(bottom_section)
    return content, clock_widget, med_widget, events_widget


def _create_clock_widget(services):
    # Widget-specific tokens (clock, med, events)
    CLOCK_ICON_SIZE = 100
    CLOCK_DAY_HEIGHT = 60
    CLOCK_TEXT_HEIGHT = 50
    CLOCK_TIME_HEIGHT = 120
    CLOCK_DATE_HEIGHT = 60
    CLOCK_SPACING = 0
    CLOCK_PADDING = [15, 10]
    text_color = (0.1, 0.1, 0.1, 1)

    clock = KioskWidget()
    clock.spacing = CLOCK_SPACING
    clock.padding = CLOCK_PADDING
    apply_debug_border(clock)

    top_section = BoxLayout(orientation="horizontal")
    top_section.size_hint = (1, None)
    top_section.height = CLOCK_DAY_HEIGHT + CLOCK_TEXT_HEIGHT
    apply_debug_border(top_section)

    left_stack = BoxLayout(orientation="vertical")
    left_stack.size_hint = (0.7, 1)

    day_label = KioskLabel(type="header", text="")
    day_label.color = text_color
    day_label.size_hint = (1, 0.5)
    apply_debug_border(day_label)
    left_stack.add_widget(day_label)

    time_of_day_label = KioskLabel(type="subheader", text="")
    time_of_day_label.color = text_color
    time_of_day_label.halign = "left"
    time_of_day_label.valign = "top"
    time_of_day_label.size_hint = (1, 0.5)
    apply_debug_border(time_of_day_label)
    left_stack.add_widget(time_of_day_label)

    top_section.add_widget(left_stack)

    icon_container = AnchorLayout(anchor_x="center", anchor_y="center")
    icon_container.size_hint = (0.3, 1)
    apply_debug_border(icon_container)

    time_of_day_icon = Image()
    time_of_day_icon.size_hint = (None, None)
    time_of_day_icon.width = CLOCK_ICON_SIZE
    time_of_day_icon.height = CLOCK_ICON_SIZE
    time_svc = services.get("time_service")
    initial_time_of_day = time_svc.get_am_pm() if time_svc else "Morning"
    time_of_day_icon.source = get_time_of_day_icon(initial_time_of_day)
    icon_container.add_widget(time_of_day_icon)

    top_section.add_widget(icon_container)
    clock.add_widget(top_section)

    time_label = KioskLabel(type="hero", text="")
    time_label.color = text_color
    time_label.halign = "center"
    time_label.valign = "middle"
    time_label.size_hint = (1, None)
    time_label.height = CLOCK_TIME_HEIGHT
    apply_debug_border(time_label)
    clock.add_widget(time_label)

    bottom_section = BoxLayout(orientation="horizontal")
    bottom_section.size_hint = (1, None)
    bottom_section.height = CLOCK_DATE_HEIGHT
    apply_debug_border(bottom_section)

    date_label = KioskLabel(type="subheader", text="")
    date_label.color = text_color
    date_label.halign = "left"
    date_label.valign = "middle"
    date_label.size_hint = (0.6, 1)
    apply_debug_border(date_label)
    bottom_section.add_widget(date_label)

    year_label = KioskLabel(type="subheader", text="")
    year_label.color = text_color
    year_label.halign = "right"
    year_label.valign = "middle"
    year_label.size_hint = (0.4, 1)
    apply_debug_border(year_label)
    bottom_section.add_widget(year_label)

    clock.add_widget(bottom_section)

    clock.day_label = day_label
    clock.time_of_day_icon = time_of_day_icon
    clock.time_of_day_label = time_of_day_label
    clock.time_label = time_label
    clock.date_label = date_label
    clock.year_label = year_label

    return clock


def _create_medication_widget():
    light_blue = (0.94, 0.96, 0.98, 1)
    med = KioskWidget(background_color=light_blue)

    title = KioskLabel(type="header", text="Medications")
    med.add_widget(title)

    med_content = KioskLabel(type="body", text="Loading medications...")
    med.add_widget(med_content)
    med.medication_content = med_content

    def update(data):
        time_groups = {}
        for m in data.get("timed_medications") or []:
            t = m.get("time", "Unknown")
            time_groups.setdefault(t, []).append(m)
        group_times = data.get("medication_time_groups", {})
        sorted_times = sorted(
            time_groups.keys(), key=lambda x: group_times.get(x, "23:59:59")
        )
        meds_text = []
        for t in sorted_times:
            meds = time_groups[t]
            if meds:
                meds_text.append(f"{t}:")
                for m in meds:
                    status = "Done" if m["status"] == "done" else "Not Done"
                    meds_text.append(f"  • {m['name']}: {status}")
        prn_meds = data.get("prn_medications") or []
        if prn_meds:
            meds_text.append("PRN (As Needed):")
            for m in prn_meds:
                last = (
                    f"Last: {m['last_taken']}" if m["last_taken"] else "Not taken today"
                )
                meds_text.append(f"  • {m['name']}: {last}")
        med_content.text = "\n".join(meds_text) if meds_text else "No medications"

    med.update = update
    return med


def _create_events_widget():
    EVENTS_BG = (0.96, 0.98, 0.94, 1)
    events = KioskWidget(orientation="vertical", background_color=EVENTS_BG)

    title = KioskLabel(type="header", text="Today's Events")
    events.add_widget(title)

    events_content = KioskLabel(type="body", text="Loading events...")
    events.add_widget(events_content)
    events.events_content = events_content

    def update(data):
        events_content.text = (
            "\n".join(f"• {e}" for e in data) if data else "No events today"
        )

    events.update = update
    return events
