"""
Kiosk Settings: monitors section HTML, link into Medications screen, static kiosk copy.

Scope: composition of primitives + monitor rows (stove id for live updates).
Not here: live temperature polling (app + TemperatureSensor), or medication row editing.
"""

import html as html_module

from . import html_primitives as hp
from .monitors_screen import build_monitor_reading_row_html
from .temperature_sensor import STOVE_SNOOZE_MINUTES


def build_settings_html(services, api_url: str) -> str:
    header = hp.kiosk_header("Settings")
    stove_row = build_monitor_reading_row_html(
        "Stove temperature",
        "stove-temp",
        action_button_text=f"Snooze alerts ({STOVE_SNOOZE_MINUTES} min)",
        action_onclick_js="pywebview.api.snooze_stove_temp()",
        row_class="temp-widget-row monitors-stove-row kiosk-monitor-row",
    )
    foot = (
        '<p class="kiosk-settings-footnote">'
        + html_module.escape(
            "Display and account options are managed by your caregiver in the Meridian web dashboard."
        )
        + "</p>"
    )
    inner = (
        header
        + hp.spacer(12)
        + '<div class="kiosk-settings">'
        + '<section class="kiosk-settings-card" aria-labelledby="settings-monitors-h">'
        + '<h2 class="kiosk-settings-card__title" id="settings-monitors-h">Monitors</h2>'
        + '<div class="kiosk-settings-card__body kiosk-settings-card__body--monitor">'
        + stove_row
        + "</div></section>"
        + '<section class="kiosk-settings-card" aria-labelledby="settings-meds-h">'
        + '<h2 class="kiosk-settings-card__title" id="settings-meds-h">Medications</h2>'
        + '<div class="kiosk-settings-card__body">'
        + hp.kiosk_caption(
            "Update the list on the Medications screen—the same editor as the web dashboard. "
            "Mark today’s doses from Home or Health."
        )
        + hp.spacer(10)
        + '<button type="button" class="add-event-btn btn-large kiosk-settings-primary-btn" data-screen="medications">Edit medications</button>'
        + "</div></section>"
        + foot
        + "</div>"
    )
    return hp.panel(inner, class_name="settings-panel")
