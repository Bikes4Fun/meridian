/**
 * meridian_sensors.js
 * Sensor card UI update functions — called from Python via _eval_el / evaluate_js.
 *
 * Python push loop in app.py calls these after receiving serial data:
 *   window.evaluate_js("meridianSensors.updateStove(...)")
 *   window.evaluate_js("meridianSensors.updateTilt(...)")
 *
 * All functions are safe to call even if the settings screen is not visible —
 * they no-op if elements are absent.
 */

window.meridianSensors = (function () {

  function el(id) { return document.getElementById(id); }
  function setText(id, text) { var e = el(id); if (e) e.textContent = text; }
  function setDisplay(id, show) { var e = el(id); if (e) e.style.display = show ? 'flex' : 'none'; }
  function setClass(id, cls) { var e = el(id); if (e) e.className = cls; }

  /**
   * updateStove(opts)
   *
   * opts = {
   *   temp:        "82.4°F",       // display string
   *   lastRead:    "30 sec ago",
   *   status:      "online" | "alert" | "offline" | "unknown",
   *   alertTime:   "Triggered 2:14 PM" | null,
   *   barPct:      42,             // 0–100, temp vs threshold
   *   snoozed:     false,
   *   snoozeLeft:  null | "14 min left",
   *   offline:     false,
   * }
   */
  function updateStove(opts) {
    opts = opts || {};

    setText('stove-temp', opts.temp || '—');
    setText('stove-last-read', opts.lastRead || '');

    // Status dot + label
    var status = opts.status || 'unknown';
    var dotClass = {
      online:  'sensor-status-dot dot-online',
      alert:   'sensor-status-dot dot-alert',
      offline: 'sensor-status-dot dot-offline',
      unknown: 'sensor-status-dot dot-offline',
    }[status] || 'sensor-status-dot dot-offline';
    setClass('stove-status-dot', dotClass);

    var labelMap = { online: 'Online', alert: 'Alert', offline: 'Offline', unknown: 'Unknown' };
    setText('stove-status-label', labelMap[status] || 'Unknown');

    // Alert time
    var alertTime = opts.alertTime || null;
    var alertEl = el('stove-alert-time');
    if (alertEl) {
      alertEl.textContent = alertTime || '';
      alertEl.style.display = alertTime ? 'inline' : 'none';
    }

    // Temperature bar
    var barEl = el('stove-bar-fill');
    if (barEl) {
      var pct = Math.min(100, Math.max(0, opts.barPct || 0));
      barEl.style.width = pct + '%';
      barEl.className = 'sensor-temp-bar__fill' +
        (status === 'alert' ? ' sensor-temp-bar__fill--alert' :
         pct > 60 ? ' sensor-temp-bar__fill--warm' : '');
    }

    // Card border class
    var card = el('stove-sensor-card');
    if (card) {
      card.className = 'sensor-card' +
        (status === 'alert' ? ' sensor-card--alert' :
         status === 'offline' ? ' sensor-card--offline' : '');
    }

    // Snooze button label
    var snoozed = !!opts.snoozed;
    var snoozeBtn = el('stove-snooze-btn');
    if (snoozeBtn) {
      snoozeBtn.className = 'sensor-snooze-btn' + (snoozed ? ' sensor-snooze-btn--active' : '');
    }
    setText('stove-snooze-label',
      snoozed && opts.snoozeLeft ? 'Snoozed — ' + opts.snoozeLeft : 'Snooze 30 min');

    // Offline warning banner
    setDisplay('stove-offline-warn', !!opts.offline);
  }

  /**
   * updateTilt(slot, opts)
   *
   * slot = 1–4
   * opts = {
   *   state:    "upright" | "tilted" | "offline",
   *   time:     "8:32 AM" | "just now" | "yesterday" | "—",
   *   missedWarn: null | "Evening medications — still upright at 9:00 PM",
   * }
   */
  function updateTilt(slot, opts) {
    opts = opts || {};
    var s = opts.state || 'offline';

    // Dot
    var dotClass = {
      upright: 'tilt-dot dot-online',
      tilted:  'tilt-dot dot-alert',
      offline: 'tilt-dot dot-offline',
    }[s] || 'tilt-dot dot-offline';
    setClass('tilt-' + slot + '-dot', dotClass);

    // State badge
    var badgeClass = {
      upright: 'tilt-state-badge ts-up',
      tilted:  'tilt-state-badge ts-tilt',
      offline: 'tilt-state-badge ts-off',
    }[s] || 'tilt-state-badge ts-off';
    setClass('tilt-' + slot + '-state-badge', badgeClass);

    var stateLabel = { upright: 'Upright', tilted: 'Moved', offline: 'Offline' }[s] || 'Offline';
    setText('tilt-' + slot + '-state', stateLabel);

    setText('tilt-' + slot + '-time', opts.time || '—');
  }

  /**
   * updateTiltMissedWarn(text | null)
   * Shows the amber "not accessed today" banner with the given text,
   * or hides it if text is null/empty.
   */
  function updateTiltMissedWarn(text) {
    var row = el('tilt-warn-row');
    if (!row) return;
    if (text) {
      setText('tilt-warn-text', text);
      row.style.display = 'flex';
    } else {
      row.style.display = 'none';
    }
  }

  return { updateStove: updateStove, updateTilt: updateTilt, updateTiltMissedWarn: updateTiltMissedWarn };

})();
