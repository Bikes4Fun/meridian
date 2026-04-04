// Top nav (#kiosk-nav) and footer (#kiosk-footer): any click on a [data-screen] button calls Python navigate().
function bindScreenNav(container) {
  if (!container) return;
  container.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-screen]');
    if (btn && typeof pywebview !== 'undefined' && pywebview.api) {
      pywebview.api.navigate(btn.dataset.screen);
    }
  });
}
bindScreenNav(document.getElementById('kiosk-nav'));
bindScreenNav(document.getElementById('kiosk-footer'));

// Cancel button: event-modal div has stopPropagation() so clicks inside the modal
// never bubble up to screen-content. Capture phase runs first.
function handleModalCancel(e) {
  var cancelBtn = e.target.closest('#eventFormCancel');
  if (cancelBtn) {
    var ov = document.getElementById('eventFormOverlay');
    if (ov) ov.style.display = 'none';
    e.stopPropagation();
  }
}
document.getElementById('screen-content').addEventListener('click', handleModalCancel, true);

var _kioskMedConfirmTimer = null;
var _kioskMedArmedBtn = null;

function disarmMedTakenBtn(btn) {
  if (!btn) return;
  btn.classList.remove('med-taken-btn--armed');
  if (btn._meridianLabelRestore != null) {
    btn.textContent = btn._meridianLabelRestore;
    btn._meridianLabelRestore = null;
  }
  if (_kioskMedArmedBtn === btn) _kioskMedArmedBtn = null;
}

function clearMedTakenArmTimer() {
  if (_kioskMedConfirmTimer) {
    clearTimeout(_kioskMedConfirmTimer);
    _kioskMedConfirmTimer = null;
  }
}

document.getElementById('screen-content').addEventListener('click', function(e) {
  if (_kioskMedArmedBtn) {
    var clickedMed = e.target.closest('.med-taken-btn');
    if (clickedMed !== _kioskMedArmedBtn) {
      clearMedTakenArmTimer();
      disarmMedTakenBtn(_kioskMedArmedBtn);
    }
  }
  var addBtn = e.target.closest('#addEventBtn');
  if (addBtn && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_add_event_modal) {
    pywebview.api.open_add_event_modal();
    return;
  }
  var medTakenBtn = e.target.closest('.med-taken-btn');
  if (medTakenBtn && medTakenBtn.dataset.medId && medTakenBtn.dataset.medTime && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.mark_medication_taken) {
    var mid = parseInt(medTakenBtn.dataset.medId, 10);
    var timeSlot = medTakenBtn.dataset.medTime || '';
    var currentlyDone = medTakenBtn.dataset.medDone === 'true';
    var nextIsTaken = !currentlyDone;
    if (medTakenBtn === _kioskMedArmedBtn && medTakenBtn.classList.contains('med-taken-btn--armed')) {
      clearMedTakenArmTimer();
      _kioskMedArmedBtn = null;
      medTakenBtn.classList.remove('med-taken-btn--armed');
      var cardEl = medTakenBtn.closest('article.med-card');
      if (cardEl) cardEl.setAttribute('aria-busy', 'true');
      var res = pywebview.api.mark_medication_taken(mid, timeSlot, nextIsTaken);
      function done(r) {
        if (cardEl) cardEl.removeAttribute('aria-busy');
        if (r === 'ok') {
          var screen = (document.body && document.body.dataset.screen) || 'home';
          if (pywebview.api.reload_screen) pywebview.api.reload_screen(screen);
          else if (pywebview.api.refresh_events) pywebview.api.refresh_events();
        } else {
          if (medTakenBtn._meridianLabelRestore != null) {
            medTakenBtn.textContent = medTakenBtn._meridianLabelRestore;
            medTakenBtn._meridianLabelRestore = null;
          }
          if (r) alert(r);
        }
      }
      (res && res.then) ? res.then(done).catch(function (x) {
        if (cardEl) cardEl.removeAttribute('aria-busy');
        if (medTakenBtn._meridianLabelRestore != null) {
          medTakenBtn.textContent = medTakenBtn._meridianLabelRestore;
          medTakenBtn._meridianLabelRestore = null;
        }
        alert(String(x));
      }) : done(res);
      return;
    }
    clearMedTakenArmTimer();
    if (_kioskMedArmedBtn && _kioskMedArmedBtn !== medTakenBtn) {
      disarmMedTakenBtn(_kioskMedArmedBtn);
    }
    _kioskMedArmedBtn = medTakenBtn;
    medTakenBtn._meridianLabelRestore = medTakenBtn.textContent;
    medTakenBtn.textContent = nextIsTaken ? 'Tap again to confirm' : 'Tap again to undo';
    medTakenBtn.classList.add('med-taken-btn--armed');
    _kioskMedConfirmTimer = setTimeout(function () {
      _kioskMedConfirmTimer = null;
      disarmMedTakenBtn(medTakenBtn);
    }, 10000);
    return;
  }
  var editBtn = e.target.closest('.event-edit-btn');
  if (editBtn && editBtn.getAttribute('data-event') && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.edit_event) {
    pywebview.api.edit_event(editBtn.getAttribute('data-event'));
    return;
  }
  var deleteBtn = e.target.closest('.event-delete-btn');
  if (deleteBtn && deleteBtn.dataset.eventId) {
    if (!confirm('Delete this event?')) return;
    var res = (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.delete_event) ? pywebview.api.delete_event(deleteBtn.dataset.eventId) : 'Delete unavailable';
    function done(r) { if (r !== 'ok') alert(r || 'Failed to delete'); }
    (res && res.then) ? res.then(done).catch(function(x){alert(String(x));}) : done(res);
    return;
  }
  var callBtn = e.target.closest('.contact-call-btn[data-sb-uid]');
  if (callBtn && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_chat_with_call) {
    pywebview.api.open_chat_with_call(callBtn.dataset.sbUid || '', callBtn.dataset.name || '');
    return;
  }
  var tile = e.target.closest('.contact-tile[data-sb-uid]');
  if (tile && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_chat) {
    pywebview.api.open_chat(tile.dataset.sbUid || '', tile.dataset.name || '');
    return;
  }
  // Must not use closest('[data-screen]') alone: body has data-screen from showScreen() and would
  // match every click (inputs, checkboxes) and re-navigate → flash, no focus.
  var screenBtn = e.target.closest('button[data-screen]');
  if (screenBtn && typeof pywebview !== 'undefined' && pywebview.api) {
    pywebview.api.navigate(screenBtn.dataset.screen);
    return;
  }
  if (e.target.id === 'eventFormOverlay') {
    e.target.style.display = 'none';
    return;
  }
});


document.getElementById('screen-content').addEventListener('submit', function(e) {
  if (e.target.id !== 'eventForm') return;
  e.preventDefault();
  var title = (document.getElementById('eventTitle') || {}).value || '';
  var date = (document.getElementById('eventDate') || {}).value || '';
  var startTime = (document.getElementById('eventStartTime') || {}).value || '';
  var endTime = (document.getElementById('eventEndTime') || {}).value || '';
  var location = (document.getElementById('eventLocation') || {}).value || '';
  var description = (document.getElementById('eventDescription') || {}).value || '';
  if (!title || !date || !startTime) return;
  var payload = { title: title, start_time: date + 'T' + startTime + ':00', location: location || undefined, description: description || undefined };
  if (endTime) payload.end_time = date + 'T' + endTime + ':00';

  var result = (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.submit_event_form) ? pywebview.api.submit_event_form(JSON.stringify(payload)) : 'Submit unavailable';
  function done(res) {
    if (res === 'ok') {
      var o = document.getElementById('eventFormOverlay'); if (o) o.style.display = 'none';
      var f = document.getElementById('eventForm'); if (f) f.reset();
    } else { alert(res || 'Failed'); }
  }
  (result && result.then) ? result.then(done).catch(function(x){alert(String(x));}) : done(result);
});

function updateNavActiveState(screenName) {
  var tabs = document.querySelectorAll('#kiosk-nav [data-screen], #kiosk-footer [data-screen]');
  tabs.forEach(function(btn) {
    btn.classList.remove('nav-tab--active');
    btn.removeAttribute('aria-current');
    if (btn.dataset.screen === screenName) {
      btn.classList.add('nav-tab--active');
      btn.setAttribute('aria-current', 'page');
    }
  });
}

function showScreen(name, html) {
  var el = document.getElementById('screen-content');
  if (el) {
    el.innerHTML = html;
    document.body.dataset.screen = name;
    updateNavActiveState(name);
    if (typeof window.onKioskScreenShown === 'function') {
      window.onKioskScreenShown(name);
    }
  }
}

function updateEl(id, content) {
  var el = document.getElementById(id);
  if (el) el.innerHTML = content;
}

function updateClockPeriod(periodUpper, spritePeriod) {
  updateEl('clock-period', periodUpper);
  var sp = document.querySelector('.clock-period-sprite');
  if (sp) sp.setAttribute('data-period', spritePeriod);
}

function showToast(msg) {
  if (!msg) return;
  var toast = document.getElementById('kiosk-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'kiosk-toast';
    toast.className = 'kiosk-toast kiosk-toast--hidden';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.remove('kiosk-toast--hidden');
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(function() {
    toast.classList.add('kiosk-toast--hidden');
  }, 3500);
}

var _kioskCallSocketReady = false;
var _kioskCallSocketStarted = false;
var _kioskLastRingingCallId = '';
var _kioskClientDeviceId = '';

function _ensureKioskClientDeviceId() {
  if (_kioskClientDeviceId) return _kioskClientDeviceId;
  var key = 'meridian_kiosk_device_id';
  try {
    var existing = window.localStorage ? window.localStorage.getItem(key) : '';
    if (existing) {
      _kioskClientDeviceId = existing;
      return _kioskClientDeviceId;
    }
    var id = 'kiosk-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
    if (window.localStorage) window.localStorage.setItem(key, id);
    _kioskClientDeviceId = id;
    return _kioskClientDeviceId;
  } catch (_err) {
    _kioskClientDeviceId = 'kiosk-ephemeral';
    return _kioskClientDeviceId;
  }
}

function logKioskCallSocket(eventName, details) {
  var payload = {
    event: eventName,
    ts: new Date().toISOString(),
    page: window.location.pathname + window.location.search,
    visibility: document.visibilityState,
    online: !!navigator.onLine,
    client_source: 'kiosk',
    client_device_id: _ensureKioskClientDeviceId()
  };
  if (details && typeof details === 'object') {
    for (var k in details) {
      if (Object.prototype.hasOwnProperty.call(details, k)) payload[k] = details[k];
    }
  }
  try { console.info('[MeridianKioskCall]', JSON.stringify(payload)); } catch (_err) {}
  try {
    fetch('/api/calls/socket-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload)
    });
  } catch (_err2) {}
}

function initKioskCallSocket() {
  if (_kioskCallSocketStarted) return;
  _kioskCallSocketStarted = true;
  var SendBirdCall = window.SendBirdCall;
  if (!SendBirdCall) {
    logKioskCallSocket('kiosk_calls_sdk_missing', {
      sdk_script: 'https://cdn.jsdelivr.net/npm/sendbird-calls@1.12.2/SendBirdCall.min.js'
    });
    return;
  }
  logKioskCallSocket('kiosk_calls_init_start', {});
  fetch('/api/chat/config', { credentials: 'include' })
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      if (!cfg || !cfg.app_id) throw new Error('No app_id in config.');
      return fetch('/api/chat/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: '{}'
      }).then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error((d && (d.detail || d.error)) || 'Token request failed');
          return { cfg: cfg, token: d };
        });
      });
    })
    .then(function (bundle) {
      var cfg = bundle.cfg;
      var token = bundle.token || {};
      var userId = token.sendbird_user_id || '';
      var sessionToken = token.session_token || '';
      if (!userId) throw new Error('No sendbird_user_id in token response.');

      logKioskCallSocket('kiosk_sendbird_call_init', { app_id: cfg.app_id, self_sendbird_user_id: userId });
      SendBirdCall.init(cfg.app_id);
      return SendBirdCall.useMedia().then(function () {
        logKioskCallSocket('kiosk_sendbird_call_authenticate_start', { app_id: cfg.app_id, self_sendbird_user_id: userId });
        return new Promise(function (resolve, reject) {
          SendBirdCall.authenticate(
            { userId: userId, accessToken: sessionToken },
            function (_result, error) {
              if (error) reject(error);
              else resolve({ cfg: cfg, userId: userId });
            }
          );
        });
      });
    })
    .then(function (bundle) {
      var cfg = bundle.cfg;
      var userId = bundle.userId;
      logKioskCallSocket('kiosk_sendbird_websocket_connect_start', {
        app_id: cfg.app_id,
        self_sendbird_user_id: userId,
        transport: 'wss',
        remote_port_hint: 443
      });
      return window.SendBirdCall.connectWebSocket().then(function () {
        _kioskCallSocketReady = true;
        logKioskCallSocket('kiosk_sendbird_websocket_connected', {
          app_id: cfg.app_id,
          self_sendbird_user_id: userId,
          transport: 'wss',
          remote_port_hint: 443,
          local_port_note: 'managed by SDK/OS (ephemeral)'
        });
        window.SendBirdCall.addListener('kiosk-call-socket-listener', {
          onRinging: function (call) {
            var callId = (call && (call.callId || call.id) || '').toString();
            if (callId && callId === _kioskLastRingingCallId) return;
            _kioskLastRingingCallId = callId;
            var callerId = (call && call.caller && (call.caller.userId || call.caller.user_id) || '').toString();
            var callerName = (call && call.caller && (call.caller.nickname || call.caller.userId || call.caller.user_id) || 'Family').toString();
            logKioskCallSocket('kiosk_sendbird_on_ringing', {
              call_id: callId,
              from_sendbird_user_id: callerId
            });
            if (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_chat && callerId) {
              pywebview.api.open_chat(callerId, callerName);
            }
          }
        });
      });
    })
    .catch(function (err) {
      _kioskCallSocketStarted = false;
      logKioskCallSocket('kiosk_sendbird_call_setup_failed', {
        error: (err && err.message) || String(err)
      });
    });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initKioskCallSocket);
} else {
  initKioskCallSocket();
}
