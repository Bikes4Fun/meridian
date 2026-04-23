(function () {
  if (typeof navigator === 'undefined') return;
  if (!navigator.mediaDevices) navigator.mediaDevices = {};
  if (!navigator.mediaDevices.getUserMedia) {
    var legacyGetUserMedia =
      navigator.getUserMedia ||
      navigator.webkitGetUserMedia ||
      navigator.mozGetUserMedia ||
      navigator.msGetUserMedia;
    if (legacyGetUserMedia) {
      navigator.mediaDevices.getUserMedia = function (constraints) {
        return new Promise(function (resolve, reject) {
          legacyGetUserMedia.call(navigator, constraints, resolve, reject);
        });
      };
    }
  }
  if (!navigator.mediaDevices.enumerateDevices) {
    navigator.mediaDevices.enumerateDevices = function () {
      return Promise.resolve([]);
    };
  }
  if (!navigator.mediaDevices.addEventListener) navigator.mediaDevices.addEventListener = function () {};
  if (!navigator.mediaDevices.removeEventListener) navigator.mediaDevices.removeEventListener = function () {};
})();

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

function updateViewportDebugBadge() {
  var el = document.getElementById('kiosk-debug-viewport');
  if (!el) return;
  var w = window.innerWidth || 0;
  var h = window.innerHeight || 0;
  var ratio = h ? (w / h) : 0;
  el.textContent = 'Debug ' + w + 'x' + h + ' \u2022 AR ' + ratio.toFixed(3);
}
updateViewportDebugBadge();
window.addEventListener('resize', updateViewportDebugBadge);
window.addEventListener('orientationchange', updateViewportDebugBadge);

// Calendar modal: open/prefill in JS; Python bridge only submits/deletes (see app.py).
window.meridianKioskEvents = {
  openAddModal: function() {
    var addTrigger = document.getElementById('addEventBtn');
    if (addTrigger && (addTrigger.disabled || addTrigger.classList.contains('add-event-btn--disabled'))) {
      return;
    }
    var idEl = document.getElementById('eventEditingId');
    if (idEl) idEl.value = '';
    var tt = document.getElementById('eventFormTitle');
    if (tt) tt.textContent = 'Add Event';
    var title = document.getElementById('eventTitle');
    if (title) title.value = '';
    var d = document.getElementById('eventDate');
    if (d) {
      var today = new Date();
      var y = today.getFullYear();
      var m = String(today.getMonth() + 1).padStart(2, '0');
      var day = String(today.getDate()).padStart(2, '0');
      d.value = y + '-' + m + '-' + day;
    }
    var s = document.getElementById('eventStartTime');
    if (s) s.value = '';
    var en = document.getElementById('eventEndTime');
    if (en) en.value = '';
    var l = document.getElementById('eventLocation');
    if (l) l.value = '';
    var r = document.getElementById('eventDescription');
    if (r) r.value = '';
    var o = document.getElementById('eventFormOverlay');
    if (o) o.style.display = 'flex';
  },
  openEditModal: function(eventDataJson) {
    var data;
    try {
      data = JSON.parse(eventDataJson);
    } catch (e) {
      alert('Could not load event');
      return;
    }
    var idEl = document.getElementById('eventEditingId');
    if (idEl) idEl.value = data.id != null && data.id !== '' ? String(data.id) : '';
    var t = document.getElementById('eventFormTitle');
    if (t) t.textContent = 'Edit Event';
    var st = data.start_time || '';
    var et = data.end_time || '';
    var today = new Date();
    var y = today.getFullYear();
    var mo = String(today.getMonth() + 1).padStart(2, '0');
    var day = String(today.getDate()).padStart(2, '0');
    var dateStr = y + '-' + mo + '-' + day;
    if (st.length >= 10) dateStr = st.slice(0, 10);
    var startTime = st.length >= 16 ? st.slice(11, 16) : '09:00';
    var endTime = et.length >= 16 ? et.slice(11, 16) : '';
    var titleEl = document.getElementById('eventTitle');
    if (titleEl) titleEl.value = data.title || '';
    var d = document.getElementById('eventDate');
    if (d) d.value = dateStr;
    var s = document.getElementById('eventStartTime');
    if (s) s.value = startTime;
    var e = document.getElementById('eventEndTime');
    if (e) e.value = endTime;
    var l = document.getElementById('eventLocation');
    if (l) l.value = data.location || '';
    var r = document.getElementById('eventDescription');
    if (r) r.value = data.description || '';
    var o = document.getElementById('eventFormOverlay');
    if (o) o.style.display = 'flex';
  },
  refreshScheduleIfShown: function() {
    if (document.body && document.body.dataset.screen === 'schedule' && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.navigate) {
      pywebview.api.navigate('schedule');
    }
  }
};

window.meridianKioskScheduleWeek = {
  step: function (deltaWeeks) {
    var strip = document.getElementById('kioskScheduleWeekStrip');
    if (!strip || typeof deltaWeeks !== 'number' || deltaWeeks === 0) return;
    var ws = strip.getAttribute('data-week-start');
    if (!ws) return;
    var p = ws.split('-');
    var y = parseInt(p[0], 10);
    var mo = parseInt(p[1], 10) - 1;
    var da = parseInt(p[2], 10);
    if (isNaN(y) || isNaN(mo) || isNaN(da)) return;
    var base = new Date(y, mo, da);
    base.setDate(base.getDate() + deltaWeeks * 7);
    var ny = base.getFullYear();
    var nmo = String(base.getMonth() + 1).padStart(2, '0');
    var nda = String(base.getDate()).padStart(2, '0');
    var newStart = ny + '-' + nmo + '-' + nda;
    strip.setAttribute('data-week-start', newStart);
    strip.innerHTML = window.meridianKioskScheduleWeek._buildCells(newStart);
  },
  _buildCells: function (weekStartYmd) {
    var letters = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
    var p = weekStartYmd.split('-');
    var y = parseInt(p[0], 10);
    var mo = parseInt(p[1], 10) - 1;
    var da = parseInt(p[2], 10);
    var base = new Date(y, mo, da);
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var parts = [];
    for (var i = 0; i < 7; i++) {
      var d = new Date(base.getFullYear(), base.getMonth(), base.getDate() + i);
      d.setHours(0, 0, 0, 0);
      var letter = letters[i];
      var dayNum = String(d.getDate());
      var iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      var isToday = d.getTime() === today.getTime();
      var cls = 'kiosk-schedule-day-stub' + (isToday ? ' kiosk-schedule-day-stub--today' : '');
      parts.push(
        '<div class="' + cls + '" title="Coming soon" data-stub-date="' + iso + '">' +
          '<span class="kiosk-schedule-day-stub__letter">' + letter + '</span>' +
          '<span class="kiosk-schedule-day-stub__circle">' + dayNum + '</span>' +
        '</div>'
      );
    }
    return parts.join('');
  }
};

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
  if (addBtn && !addBtn.disabled && window.meridianKioskEvents && typeof window.meridianKioskEvents.openAddModal === 'function') {
    window.meridianKioskEvents.openAddModal();
    return;
  }
  var medTakenBtn = e.target.closest('.med-taken-btn');
  if (medTakenBtn && medTakenBtn.dataset.medId && medTakenBtn.dataset.medTime && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.mark_medication_taken) {
    var mid = parseInt(medTakenBtn.dataset.medId, 10);
    var timeSlot = medTakenBtn.dataset.medTime || '';
    var prnAct = medTakenBtn.dataset.prnAction || '';
    var currentlyDone = medTakenBtn.dataset.medDone === 'true';
    var nextIsTaken;
    if (prnAct === 'take') {
      nextIsTaken = true;
    } else if (prnAct === 'undo') {
      nextIsTaken = false;
    } else {
      nextIsTaken = !currentlyDone;
    }
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
  var wkNav = e.target.closest('#kioskScheduleWeekPrev, #kioskScheduleWeekNext');
  if (wkNav && window.meridianKioskScheduleWeek && typeof window.meridianKioskScheduleWeek.step === 'function') {
    e.preventDefault();
    window.meridianKioskScheduleWeek.step(wkNav.id === 'kioskScheduleWeekNext' ? 1 : -1);
    return;
  }
  var editBtn = e.target.closest('.event-edit-btn');
  if (editBtn && editBtn.getAttribute('data-event') && window.meridianKioskEvents && typeof window.meridianKioskEvents.openEditModal === 'function') {
    window.meridianKioskEvents.openEditModal(editBtn.getAttribute('data-event'));
    return;
  }
  var deleteBtn = e.target.closest('.event-delete-btn');
  if (deleteBtn && deleteBtn.dataset.eventId && !deleteBtn.disabled) {
    if (!confirm('Delete this event?')) return;
    var res = (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.delete_event) ? pywebview.api.delete_event(deleteBtn.dataset.eventId) : 'Delete unavailable';
    function done(r) { if (r !== 'ok') alert(r || 'Failed to delete'); }
    (res && res.then) ? res.then(done).catch(function(x){alert(String(x));}) : done(res);
    return;
  }
  // Chat contact call: Twilio Voice JS only for kiosk-embedded calling.
  // Twilio must reach token/TwiML URLs over the public internet (ngrok in dev).
  var callBtn = e.target.closest('.contact-call-btn[data-phone]');
  if (callBtn) {
    e.preventDefault();
    var p = callBtn.dataset.phone || '';
    var n = callBtn.dataset.name || '';
    if (typeof kioskStartTwilioSpeakerCall !== 'function') {
      showToast('Kiosk calling is unavailable');
      return;
    }
    kioskStartTwilioSpeakerCall(p, n);
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
  var idEl = document.getElementById('eventEditingId');
  if (idEl && idEl.value) payload.id = idEl.value;

  var result = (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.submit_event_form) ? pywebview.api.submit_event_form(JSON.stringify(payload)) : 'Submit unavailable';
  function done(res) {
    if (res === 'ok') {
      var o = document.getElementById('eventFormOverlay'); if (o) o.style.display = 'none';
      var f = document.getElementById('eventForm'); if (f) f.reset();
      var hid = document.getElementById('eventEditingId'); if (hid) hid.value = '';
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
    updateViewportDebugBadge();
    if (typeof window.onKioskScreenShown === 'function') {
      window.onKioskScreenShown(name);
    }
  }
}

function setBootLoading(active, message) {
  var overlay = document.getElementById('kiosk-boot-overlay');
  if (!overlay) return;
  var msgEl = document.getElementById('kiosk-boot-overlay-msg');
  if (msgEl && message) msgEl.textContent = message;
  if (active) {
    overlay.classList.remove('kiosk-boot-overlay--hidden');
    return;
  }
  overlay.classList.add('kiosk-boot-overlay--hidden');
}

function setKioskCornerBootLoading(active, message) {
  var root = document.getElementById('kiosk-boot-corner');
  if (!root) return;
  var msgEl = document.getElementById('kiosk-boot-corner-msg');
  if (msgEl && message !== undefined && message !== null) {
    msgEl.textContent = message || '';
  }
  if (active) {
    root.classList.remove('kiosk-boot-corner--hidden');
    root.setAttribute('aria-busy', 'true');
  } else {
    root.classList.add('kiosk-boot-corner--hidden');
    root.removeAttribute('aria-busy');
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

var _kioskActiveTwilioCall = null;

function kioskEnsureInCallBar() {
  var inner =
    '<div class="kiosk-in-call-bar__chrome-full">' +
    '<button type="button" class="kiosk-in-call-bar__minimize" id="kiosk-in-call-minimize" aria-label="Minimize call view">' +
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 9l6 6 6-6"/>' +
    '</svg></button>' +
    '<div class="kiosk-in-call-bar__center">' +
    '<span class="kiosk-in-call-bar__head" id="kiosk-in-call-bar-head"></span>' +
    '<span class="kiosk-in-call-bar__sub" id="kiosk-in-call-bar-sub"></span></div>' +
    '<div class="kiosk-in-call-bar__footer">' +
    '<button type="button" class="kiosk-in-call-bar__hangup" id="kiosk-in-call-hangup" aria-label="End call">' +
    '<svg class="kiosk-in-call-bar__hangup-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.81 19.79 19.79 0 01.04 1.22 2 2 0 012 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 14.92z"/>' +
    '</svg></button></div></div>' +
    '<div class="kiosk-in-call-bar__chrome-mini" role="button" tabindex="0" aria-label="Expand call view">' +
    '<div class="kiosk-in-call-bubble-floater">' +
    '<div class="kiosk-in-call-bubble-ring"></div>' +
    '<div class="kiosk-in-call-bubble-ring"></div>' +
    '<div class="kiosk-in-call-bubble-ring"></div>' +
    '<div class="kiosk-in-call-bubble-disk">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.81 19.79 19.79 0 01.04 1.22 2 2 0 012 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 14.92z"/>' +
    '</svg></div>' +
    '<div class="kiosk-in-call-bubble-label" id="kiosk-in-call-bubble-head"></div>' +
    '<div class="kiosk-in-call-bubble-name" id="kiosk-in-call-bubble-sub"></div>' +
    '</div></div>';
  function wireHangup(b) {
    var btn = b.querySelector('#kiosk-in-call-hangup');
    if (btn && !btn._kioskHangupWired) {
      btn._kioskHangupWired = true;
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        kioskHangupTwilioCall();
      });
    }
  }
  function wireMinimizeExpand(b) {
    var minBtn = b.querySelector('#kiosk-in-call-minimize');
    if (minBtn && !minBtn._kioskMinWired) {
      minBtn._kioskMinWired = true;
      minBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        kioskSetInCallMinimized(true);
      });
    }
    var mini = b.querySelector('.kiosk-in-call-bar__chrome-mini');
    if (mini && !mini._kioskMiniExpandWired) {
      mini._kioskMiniExpandWired = true;
      function expand(e) {
        e.preventDefault();
        kioskSetInCallMinimized(false);
      }
      mini.addEventListener('click', expand);
      mini.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          kioskSetInCallMinimized(false);
        }
      });
    }
  }
  var bar = document.getElementById('kiosk-in-call-bar');
  if (bar) {
    if (!bar.querySelector('.kiosk-in-call-bar__chrome-full')) {
      bar.innerHTML = inner;
      bar.setAttribute('role', 'status');
      bar.setAttribute('aria-live', 'assertive');
      wireHangup(bar);
      wireMinimizeExpand(bar);
    }
    return bar;
  }
  bar = document.createElement('div');
  bar.id = 'kiosk-in-call-bar';
  bar.className = 'kiosk-in-call-bar kiosk-in-call-bar--hidden';
  bar.setAttribute('role', 'status');
  bar.setAttribute('aria-live', 'assertive');
  bar.setAttribute('aria-label', 'Active phone call');
  bar.innerHTML = inner;
  document.body.appendChild(bar);
  wireHangup(bar);
  wireMinimizeExpand(bar);
  return bar;
}

function kioskSyncInCallBubbleLabels() {
  var head = document.getElementById('kiosk-in-call-bar-head');
  var sub = document.getElementById('kiosk-in-call-bar-sub');
  var bh = document.getElementById('kiosk-in-call-bubble-head');
  var bs = document.getElementById('kiosk-in-call-bubble-sub');
  if (bh && head) bh.textContent = head.textContent || '';
  if (bs && sub) bs.textContent = sub.textContent || '';
}

function kioskSetInCallMinimized(minimized) {
  var bar = document.getElementById('kiosk-in-call-bar');
  if (!bar || bar.classList.contains('kiosk-in-call-bar--hidden')) return;
  if (minimized) {
    bar.classList.add('kiosk-in-call-bar--minimized');
  } else {
    bar.classList.remove('kiosk-in-call-bar--minimized');
  }
}

function kioskShowInCallBar(headText, subText, keepMinimized) {
  var bar = kioskEnsureInCallBar();
  var head = document.getElementById('kiosk-in-call-bar-head');
  var sub = document.getElementById('kiosk-in-call-bar-sub');
  if (head) head.textContent = headText || '';
  if (sub) sub.textContent = subText || '';
  kioskSyncInCallBubbleLabels();
  if (!keepMinimized) {
    bar.classList.remove('kiosk-in-call-bar--minimized');
  }
  bar.classList.remove('kiosk-in-call-bar--hidden');
}

function kioskHideInCallBar() {
  var bar = document.getElementById('kiosk-in-call-bar');
  if (bar) {
    bar.classList.add('kiosk-in-call-bar--hidden');
    bar.classList.remove('kiosk-in-call-bar--minimized');
  }
}

function kioskHangupTwilioCall() {
  if (_kioskActiveTwilioCall) {
    try {
      _kioskActiveTwilioCall.disconnect();
    } catch (_e) {}
  }
}

function _kioskTwilioCallUiEnded() {
  _kioskActiveTwilioCall = null;
  kioskHideInCallBar();
}

var _kioskTwilioDevice = null;
var _kioskTwilioCallerId = '';
var _kioskTwilioSdkLoadPromise = null;
var _kioskTwilioSdkSources = [
  'https://sdk.twilio.com/js/voice/releases/2.11.0/twilio.min.js?ts=',
  'https://media.twiliocdn.com/sdk/js/voice/latest/twilio.min.js?ts=',
  'https://cdn.jsdelivr.net/npm/@twilio/voice-sdk@2.11.0/dist/twilio.min.js?ts=',
  'https://unpkg.com/@twilio/voice-sdk@2.11.0/dist/twilio.min.js?ts='
];

function _kioskTryLoadTwilioSdk(index, resolve, reject) {
  if (typeof Twilio !== 'undefined' && Twilio.Device) {
    window.__twilioSdkLoadState = 'loaded-before-fallback';
    resolve(true);
    return;
  }
  if (index >= _kioskTwilioSdkSources.length) {
    reject(new Error('Twilio SDK fallback sources exhausted'));
    return;
  }
  var src = _kioskTwilioSdkSources[index] + Date.now();
  var script = document.createElement('script');
  script.src = src;
  script.async = true;
  script.onload = function () {
    if (typeof Twilio !== 'undefined' && Twilio.Device) {
      window.__twilioSdkLoadState = 'fallback-loaded-' + index;
      resolve(true);
      return;
    }
    _kioskTryLoadTwilioSdk(index + 1, resolve, reject);
  };
  script.onerror = function () {
    _kioskTryLoadTwilioSdk(index + 1, resolve, reject);
  };
  document.head.appendChild(script);
}

function kioskEnsureTwilioSdk() {
  if (typeof Twilio !== 'undefined' && Twilio.Device) return Promise.resolve(true);
  if (_kioskTwilioSdkLoadPromise) return _kioskTwilioSdkLoadPromise;
  _kioskTwilioSdkLoadPromise = new Promise(function (resolve, reject) {
    _kioskTryLoadTwilioSdk(0, resolve, function (err) {
      window.__twilioSdkLoadState = 'fallback-failed';
      reject(err);
    });
  }).finally(function () {
    _kioskTwilioSdkLoadPromise = null;
  });
  return _kioskTwilioSdkLoadPromise;
}

function kioskEnsureTwilioDevice() {
  if (_kioskTwilioDevice) return Promise.resolve(_kioskTwilioDevice);
  return kioskEnsureTwilioSdk()
    .catch(function () {
      return true;
    })
    .then(function () {
      if (!(typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.get_voice_token)) {
        throw new Error('Voice token bridge unavailable');
      }
      return pywebview.api.get_voice_token();
    })
    .then(function (data) {
      if (typeof data === 'string') {
        try { data = JSON.parse(data || '{}'); } catch (_e) { data = { error: data }; }
      }
      var token = (data && data.token) || '';
      _kioskTwilioCallerId = (data && data.caller_id) || '';
      if (!token) throw new Error((data && data.error) || 'Missing Twilio token');
      if (typeof Twilio === 'undefined' || !Twilio.Device) {
        throw new Error('Twilio Voice SDK unavailable in kiosk (state=' + (window.__twilioSdkLoadState || 'unknown') + ')');
      }
      _kioskTwilioDevice = new Twilio.Device(token, {
        logLevel: 1,
        closeProtection: false,
        codecPreferences: ['opus', 'pcmu']
      });
      return _kioskTwilioDevice.register().then(function () {
        return _kioskTwilioDevice;
      });
    });
}

function kioskStartTwilioSpeakerCall(phone, displayName) {
  var to = (phone || '').trim();
  var who = (displayName || to || 'contact').trim();
  if (!to) {
    showToast('No phone number for this contact');
    return;
  }
  if (_kioskActiveTwilioCall) {
    showToast('End the current call first');
    return;
  }
  kioskEnsureTwilioDevice()
    .then(function (device) {
      return device.connect({ params: { To: to, callerId: _kioskTwilioCallerId } });
    })
    .then(function (call) {
      _kioskActiveTwilioCall = call;
      kioskShowInCallBar('Calling', who);
      showToast('Calling ' + who);
      call.on('accept', function () {
        var b = document.getElementById('kiosk-in-call-bar');
        var keepMini = !!(b && b.classList.contains('kiosk-in-call-bar--minimized'));
        kioskShowInCallBar('ON A CALL', who, keepMini);
        showToast('Connected to ' + who);
      });
      call.on('disconnect', function () {
        showToast('Call ended');
        _kioskTwilioCallUiEnded();
      });
      call.on('error', function (err) {
        var msg = err && err.message ? String(err.message) : err ? String(err) : '';
        msg = msg.slice(0, 72);
        _kioskTwilioCallUiEnded();
        showToast(msg ? 'Call error: ' + msg : 'Call error');
      });
    })
    .catch(function (err) {
      _kioskTwilioCallUiEnded();
      showToast('Call failed: ' + ((((err && err.message) || err || '') + '').slice(0, 80) || 'unknown error'));
    });
}

// Call socket bootstrap removed; voice calls are triggered directly per contact button.
/**
 * Kiosk Medications screen: same inline editor as the webapp (bundled in webapp medications.js).
 * Runs after each showScreen via window.onKioskScreenShown (scripts in injected HTML do not run).
 */
(function () {
  'use strict';

  var _inlineSnapshot = [];
  var _kioskMedAutosave = null;

  function kioskMedicationNamesUnique(rows) {
    var seen = {};
    for (var i = 0; i < rows.length; i++) {
      var n = (rows[i].name || '').trim();
      if (!n) continue;
      var k = n.toLowerCase();
      if (seen[k]) return 'Each medication name must be unique.';
      seen[k] = true;
    }
    return null;
  }

  var SAVE_MEDS_DISK_SVG =
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><line x1="7" y1="3" x2="17" y2="3"/></svg>';

  function statusMsg(msg) {
      if (typeof showToast === 'function') {
          showToast(msg);
      } else {
          alert(msg);
      }
  }

  function loadInlineMeds(inlineList) {
      if (!(typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.get_medications_editor_rows)) {
          statusMsg('Medication editor bridge unavailable');
          return;
      }
      if (_kioskMedAutosave) _kioskMedAutosave.cancel();
      var result = pywebview.api.get_medications_editor_rows();
      function done(raw) {
          var meds = [];
          if (Array.isArray(raw)) meds = raw;
          else if (typeof raw === 'string') {
              try { meds = JSON.parse(raw) || []; } catch (_e) { meds = []; }
          }
          if (!Array.isArray(meds)) meds = [];
          meds = meds.filter(function (m) { return m && typeof m === 'object'; });
              _inlineSnapshot = MeridianMedicationsInline.cloneSnapshot(meds);
              MeridianMedicationsInline.renderRows(inlineList, meds);
      }
      if (result && result.then) result.then(done).catch(function () {
          statusMsg('Could not load medications for editing');
      });
      else done(result);
  }

  function mountMedicationsEditor() {
      var root = document.getElementById('kioskMedsEditorRoot');
      if (!root) return;
      if (typeof MeridianMedicationsInline === 'undefined') {
          root.innerHTML = '<p class="kiosk-caption">Editor failed to load. Reload or use the web dashboard.</p>';
          return;
      }
      var trash = MeridianMedicationsInline.TRASH_SVG;
      root.innerHTML =
          '<div class="ice-med-toolbar-top">' +
          '<button type="button" id="kioskMedsSelectAllBtn" class="btn-inline ice-med-select-all-btn">Select all</button>' +
          '<label class="ice-med-autosave-label">' +
          '<input type="checkbox" id="kioskMedsAutoSave" class="ice-med-autosave-cb">' +
          'Save as you go</label>' +
          '</div>' +
          '<div class="ice-medications-editor" id="kioskMedsInlineList"></div>' +
          '<div class="ice-med-editor-actions kiosk-meds-actions">' +
          '<button type="button" id="kioskMedsAddBtn" class="btn-add">Add medication</button>' +
          '<button type="button" id="kioskMedsDeleteSelectedBtn" class="btn-inline btn-delete ice-med-delete-selected-btn">' +
          '<span class="ice-med-delete-selected-btn__icon" aria-hidden="true">' + trash + '</span>' +
          '<span>Delete selected</span></button>' +
          '<button type="button" id="kioskMedsSaveBtn" class="ice-med-save-btn">' +
          '<span class="ice-med-save-btn__icon" aria-hidden="true">' + SAVE_MEDS_DISK_SVG + '</span>' +
          'Save medications</button>' +
          '</div>';

      var inlineList = document.getElementById('kioskMedsInlineList');
      var addBtn = document.getElementById('kioskMedsAddBtn');
      var selAllBtn = document.getElementById('kioskMedsSelectAllBtn');
      var delBtn = document.getElementById('kioskMedsDeleteSelectedBtn');
      var saveBtn = document.getElementById('kioskMedsSaveBtn');

      function persistMedications(silent) {
          if (!(typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.save_medications_editor_rows)) {
              if (!silent) statusMsg('Medication save bridge unavailable');
              return;
          }
          var rows = MeridianMedicationsInline.collectRows(inlineList);
          var dupErr =
              typeof MeridianMedicationsInline.validateUniqueMedicationNames === 'function'
                  ? MeridianMedicationsInline.validateUniqueMedicationNames(rows)
                  : kioskMedicationNamesUnique(rows);
          if (dupErr) {
              if (!silent) statusMsg(dupErr);
              return;
          }
          var result = pywebview.api.save_medications_editor_rows(
              JSON.stringify(rows),
              JSON.stringify(_inlineSnapshot)
          );
          function afterSave(reply) {
              if (reply !== 'ok') {
                  if (!silent) statusMsg(reply || 'Save failed');
                  return;
              }
              if (!silent) statusMsg('Medications saved');
              loadInlineMeds(inlineList);
          }
          if (result && result.then) return result.then(afterSave).catch(function (err) {
              statusMsg((err && err.message) ? err.message : 'Save failed');
          });
          afterSave(result);
      }

      _kioskMedAutosave = MeridianMedicationsInline.wireAutoSave(inlineList, {
          isEnabled: function () {
              var c = document.getElementById('kioskMedsAutoSave');
              return !!(c && c.checked);
          },
          debounceMs: 1000,
          save: function () {
              return persistMedications(true);
          }
      });

      MeridianMedicationsInline.wireList(inlineList, addBtn, delBtn, selAllBtn, {
          onListMutate: function () {
              if (_kioskMedAutosave) _kioskMedAutosave.schedule();
          },
          onRowsDeleted: function () {
              if (_kioskMedAutosave) _kioskMedAutosave.cancel();
              persistMedications(false);
          }
      });

      var kioskAuto = document.getElementById('kioskMedsAutoSave');
      if (kioskAuto) {
          kioskAuto.addEventListener('change', function () {
              if (this.checked && _kioskMedAutosave) _kioskMedAutosave.schedule();
          });
      }

      if (saveBtn) {
          saveBtn.addEventListener('click', function () {
              persistMedications(false);
          });
      }

      loadInlineMeds(inlineList);
  }

  window.onKioskScreenShown = function (name) {
      if (name === 'medications') {
          mountMedicationsEditor();
      }
  };
})();
