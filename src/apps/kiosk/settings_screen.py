"""Settings screen: includes monitors widgets plus kiosk-level copy."""

from . import html_primitives as hp
from .health_screen import build_health_management_html
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
    meds = build_health_management_html(services, api_url)
    body = hp.kiosk_body(
        "Display and account options are managed by your caregiver in the Meridian web dashboard."
    )
    inner = header + hp.spacer(16) + widgets + meds + hp.spacer(32) + body
    return hp.panel(inner, class_name="settings-panel")
