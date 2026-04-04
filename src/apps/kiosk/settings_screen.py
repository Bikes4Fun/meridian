"""
Kiosk Settings: monitors section HTML, link into Medications screen, static kiosk copy.

Scope: composition of primitives + monitor rows (stove id for live updates).
Not here: live temperature polling (app + TemperatureSensor), or medication row editing.
"""

from . import html_primitives as hp
from .monitors_screen import build_monitor_reading_row_html, build_monitors_section_html
from .temperature_sensor import STOVE_SNOOZE_MINUTES


def build_settings_html(services, api_url: str) -> str:
    header = hp.kiosk_header("Settings")
    stove_row = build_monitor_reading_row_html(
        "🌡 Stove:",
        "stove-temp",
        action_button_text=f"Ignore stove ({STOVE_SNOOZE_MINUTES}m)",
        action_onclick_js="pywebview.api.snooze_stove_temp()",
        row_class="temp-widget-row monitors-stove-row",
    )
    widgets = build_monitors_section_html("Monitors", stove_row)
    meds = (
        hp.spacer(16)
        + hp.kiosk_subheader("Medications")
        + hp.kiosk_caption(
            "Change the medication list on the Medications screen (same as the web dashboard). "
            "Mark doses from Home or Health."
        )
        + hp.spacer(8)
        + '<button type="button" class="add-event-btn btn-large" data-screen="medications">Edit medications</button>'
    )
    body = hp.kiosk_body(
        "Display and account options are managed by your caregiver in the Meridian web dashboard."
    )
    inner = header + hp.spacer(16) + widgets + meds + hp.spacer(32) + body
    return hp.panel(inner, class_name="settings-panel")
