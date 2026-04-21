"""
Kiosk Settings: monitors section HTML, static kiosk copy.

Scope: composition of primitives + monitor rows (stove id for live updates, tilt ids for bottle sensors).
Not here: live temperature polling (app + TemperatureSensor/TiltSensorHandler), medication editing (Health screen).
"""

import html as html_module
import os
from . import html_primitives as hp
from .sensor_widgets import STOVE_SNOOZE_MINUTES


# ── Tilt sensor names from env (same source as TiltSensorHandler) ──────────────
def _tilt_name(slot: int) -> str:
    return os.environ.get(f"TILT_SENSOR_{slot}_NAME", f"Sensor {slot}")


def build_stove_sensor_card_html() -> str:
    """
    Stove sensor card.
    Live elements updated by app.py push loop via _eval_el:
      - #stove-temp          : current reading string e.g. "82.4°F"
      - #stove-status-dot    : CSS class toggled between dot-online / dot-alert / dot-offline
      - #stove-status-text   : text e.g. "Online" / "Alert active" / "Offline"
      - #stove-last-read     : text e.g. "Last read 30 sec ago"
      - #stove-alert-time    : text e.g. "Triggered 2:14 PM" (hidden when no alert)
      - #stove-offline-warn  : shown/hidden via display:block/none
      - #stove-snooze-label  : text e.g. "Snooze 30 min" / "Snoozed — 14 min left"
      - #stove-bar-fill      : width% updated to reflect temp vs threshold
    """
    snooze_label = html_module.escape(f"Snooze {STOVE_SNOOZE_MINUTES} min")

    return f'''
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
        <span id="stove-last-read">Connecting…</span>
      </div>
    </div>
    <div class="sensor-status-badge" id="stove-status-text">
      <div class="sensor-status-dot" id="stove-status-dot"></div>
      <span id="stove-status-label">Unknown</span>
    </div>
  </div>

  <div class="sensor-temp-bar">
    <div class="sensor-temp-bar__fill" id="stove-bar-fill" style="width:0%"></div>
  </div>

  <div class="sensor-card__footer">
    <span class="sensor-card__alert-time" id="stove-alert-time" style="display:none"></span>
    <button
      class="sensor-snooze-btn"
      id="stove-snooze-btn"
      type="button"
      onclick="pywebview.api.snooze_stove_temp()"
    >
      <span id="stove-snooze-label">{snooze_label}</span>
    </button>
  </div>

  <div class="sensor-offline-warn" id="stove-offline-warn" style="display:none">
    <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
    Stove sensor not reporting — check USB connection
  </div>
</div>
'''


def build_tilt_sensor_row_html(slot: int) -> str:
    """
    One row for a single tilt sensor bottle slot.
    Live elements:
      - #tilt-{slot}-dot     : CSS class dot-online / dot-alert / dot-offline
      - #tilt-{slot}-state   : text UPRIGHT / MOVED / Offline
      - #tilt-{slot}-state-badge : CSS class ts-up / ts-tilt / ts-off
      - #tilt-{slot}-time    : text e.g. "8:32 AM" / "just now" / "—"
    """
    name = html_module.escape(_tilt_name(slot))
    return f'''
<div class="tilt-row" id="tilt-row-{slot}">
  <div class="tilt-dot dot-offline" id="tilt-{slot}-dot"></div>
  <div class="tilt-name">{name}</div>
  <div class="tilt-state-badge ts-off" id="tilt-{slot}-state-badge">
    <span id="tilt-{slot}-state">Offline</span>
  </div>
  <div class="tilt-time" id="tilt-{slot}-time">—</div>
</div>
'''


def build_tilt_sensors_card_html() -> str:
    """
    Full medication bottle tilt sensors card (4 slots).
    The "not accessed today" warning row is shown/hidden by JS:
      - #tilt-warn-row      : shown when any sensor triggers a missed-dose alert
      - #tilt-warn-text     : e.g. "Evening medications — still upright at 9:00 PM"
    """
    rows = "".join(build_tilt_sensor_row_html(i) for i in range(1, 5))

    return f'''
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
      <div class="sensor-card__reading">4 sensors configured</div>
    </div>
  </div>

  <div class="tilt-rows">
    {rows}
  </div>

  <div class="sensor-missed-warn" id="tilt-warn-row" style="display:none">
    <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
    <span id="tilt-warn-text">Not accessed today</span>
  </div>
</div>
'''


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

    monitors_section = f'''
<div class="kiosk-settings-card">
  <div class="kiosk-settings-card__title">Monitors</div>
  <div class="kiosk-settings-card__body kiosk-settings-card__body--monitor">
    <div class="sensor-section-label">Stove</div>
    {build_stove_sensor_card_html()}
    <div class="sensor-section-label" style="margin-top:20px">Medication Bottles</div>
    {build_tilt_sensors_card_html()}
  </div>
</div>
'''
    refinement_preview = """
<div class="kiosk-refinement-preview">
  <div class="kiosk-refinement-preview__title">Final 3 Refinements</div>
  <div class="kiosk-refinement-preview__chips">
    <span class="kiosk-refinement-chip">ICE / Emergency Profile</span>
    <span class="kiosk-refinement-chip">Stove + Sensor Safety</span>
    <span class="kiosk-refinement-chip">Where Is Everyone?</span>
  </div>
</div>
"""

    foot = (
        '<p class="kiosk-settings-footnote">'
        + html_module.escape(
            "Display and sensor configuration are managed by your caregiver in the Meridian web dashboard."
        )
        + "</p>"
    )

    inner = (
        header
        + hp.spacer(16)
        + '<div class="kiosk-settings">'
        + monitors_section
        + refinement_preview
        + foot
        + "</div>"
    )
    return hp.panel(inner, class_name="settings-panel")
