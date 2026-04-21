"""
Kiosk Settings: monitors section HTML, static kiosk copy.

Scope: composition of primitives + monitor rows (stove id for live updates).
Not here: live temperature polling (app + TemperatureSensor), medication editing (Medications screen from Settings).
"""

import html as html_module
import os
from . import html_primitives as hp
from .sensor_widgets import STOVE_SNOOZE_MINUTES


def _tilt_name(slot: int) -> str:
    return os.environ.get(f"TILT_SENSOR_{slot}_NAME", f"Bottle {slot}")


def build_stove_sensor_card_html() -> str:
    snooze_label = html_module.escape(f"Snooze {STOVE_SNOOZE_MINUTES} min")
    return f"""
<div class="sensor-card" id="stove-sensor-card">
  <div class="sensor-card__header">
    <div class="sensor-icon sensor-icon--stove">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="22" height="22">
        <path d="M12 2a5 5 0 0 1 5 5c0 3-5 10-5 10S7 10 7 7a5 5 0 0 1 5-5z"/>
        <circle cx="12" cy="7" r="2"/>
      </svg>
    </div>
    <div class="sensor-card__meta">
      <div class="sensor-card__name">Stove Temperature</div>
      <div class="sensor-card__reading">
        <span id="stove-temp">—</span>
        <span class="sensor-reading-sep">·</span>
        <span id="stove-last-read">Live monitor view</span>
      </div>
    </div>
    <div class="sensor-status-badge">
      <div class="sensor-status-dot dot-online"></div>
      <span>Online</span>
    </div>
  </div>

  <div class="sensor-temp-bar">
    <div class="sensor-temp-bar__fill" style="width:42%"></div>
  </div>

  <div class="sensor-card__footer">
    <span class="sensor-card__alert-time">Alert lifecycle timeline preview</span>
    <button class="sensor-snooze-btn" id="stove-snooze-btn" type="button" onclick="pywebview.api.snooze_stove_temp()">
      <span id="stove-snooze-label">{snooze_label}</span>
    </button>
  </div>
</div>
"""


def build_tilt_sensor_row_html(slot: int) -> str:
    name = html_module.escape(_tilt_name(slot))
    return f"""
<div class="tilt-row">
  <div class="tilt-dot dot-online"></div>
  <div class="tilt-name">{name}</div>
  <div class="tilt-state-badge ts-up"><span>Ready</span></div>
  <div class="tilt-time">Live</div>
</div>
"""


def build_tilt_sensors_card_html() -> str:
    rows = "".join(build_tilt_sensor_row_html(i) for i in range(1, 5))
    return f"""
<div class="sensor-card" id="tilt-sensor-card">
  <div class="sensor-card__header">
    <div class="sensor-icon sensor-icon--pill">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="22" height="22">
        <rect x="4" y="2" width="16" height="20" rx="8"/>
        <line x1="4" y1="12" x2="20" y2="12"/>
      </svg>
    </div>
    <div class="sensor-card__meta">
      <div class="sensor-card__name">Medication Bottles</div>
      <div class="sensor-card__reading">4 sensor slots configured</div>
    </div>
  </div>
  <div class="tilt-rows">
    {rows}
  </div>
</div>
"""


def build_refinement_preview_html() -> str:
    return """
<div class="kiosk-refinement-preview">
  <div class="kiosk-refinement-preview__title">Final 3 Refinements</div>
  <div class="kiosk-refinement-preview__chips">
    <span class="kiosk-refinement-chip">ICE / Emergency Profile</span>
    <span class="kiosk-refinement-chip">Stove + Sensor Safety</span>
    <span class="kiosk-refinement-chip">Where Is Everyone?</span>
  </div>
</div>
"""


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
        + '<button type="button" class="add-event-btn btn-large kiosk-settings-back-btn kiosk-meds-panel-back" data-screen="settings">Back to Settings</button>'
        + "</div></section></div>"
    )
    return hp.panel(inner, class_name="settings-panel kiosk-meds-panel")


def build_settings_html(services, api_url: str) -> str:
    header = hp.kiosk_header("Settings")
    monitors_section = f"""
<div class="kiosk-settings-card">
  <div class="kiosk-settings-card__title">Monitors</div>
  <div class="kiosk-settings-card__body kiosk-settings-card__body--monitor">
    <div class="sensor-section-label">Stove Sensor</div>
    {build_stove_sensor_card_html()}
    <div class="sensor-section-label" style="margin-top:20px">Medication Bottle Sensors</div>
    {build_tilt_sensors_card_html()}
  </div>
</div>
"""
    foot = (
        '<p class="kiosk-settings-footnote">'
        + html_module.escape(
            "Configuration and thresholds are managed in the Meridian caregiver dashboard."
        )
        + "</p>"
    )
    inner = (
        header
        + hp.spacer(12)
        + '<div class="kiosk-settings">'
        + monitors_section
        + foot
        + "</div>"
    )
    return hp.panel(inner, class_name="settings-panel")
