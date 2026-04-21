"""
Kiosk Settings: monitors section HTML, static kiosk copy.

Scope: composition of primitives + monitor rows (stove id for live updates).
Not here: live temperature polling (app + TemperatureSensor), medication editing (Health screen).
"""

import html as html_module
from . import html_primitives as hp
from .sensor_widgets import STOVE_SNOOZE_MINUTES


def build_monitor_reading_row_html(
    label: str,
    value_element_id: str,
    *,
    initial_value: str = "—",
    action_button_text: str | None = None,
    action_onclick_js: str | None = None,
    row_class: str = "temp-widget-row",
) -> str:
    """Single reading line: label, live value span (id for updateEl), optional small action button."""
    id_attr = html_module.escape(str(value_element_id), quote=True)
    val = html_module.escape(str(initial_value))
    lbl = html_module.escape(str(label))
    cls = html_module.escape(str(row_class), quote=True)
    inner = f'<div class="temp-widget">{lbl} <span id="{id_attr}">{val}</span></div>'
    btn = ""
    if action_button_text and action_onclick_js:
        btn = hp.kiosk_button(action_button_text, action_onclick_js, small=True)
    return f'<div class="{cls}">{inner}{btn}</div>'


def build_medications_html(services, api_url: str) -> str:
    inner = (
        hp.kiosk_header("Medications")
        + hp.spacer(12)
        + '<div class="kiosk-settings">'
        + '<section class="kiosk-settings-card">'
        + '<div class="kiosk-settings-card__body">'
        + hp.kiosk_caption(
            "Same editor as the web dashboard. Confirmed removals save right away. "
            "For other edits, tap Save medications or turn on Save as you go."
        )
        + hp.spacer(10)
        + '<div id="kioskMedsEditorRoot"></div>'
        + hp.spacer(14)
        + '<button type="button" class="add-event-btn btn-large kiosk-settings-back-btn kiosk-meds-panel-back" data-screen="health">Back to Health</button>'
        + "</div></section></div>"
    )
    return hp.panel(inner, class_name="settings-panel kiosk-meds-panel")


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
        + foot
        + "</div>"
    )
    return hp.panel(inner, class_name="settings-panel")
