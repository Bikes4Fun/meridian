document.getElementById('kiosk-nav').addEventListener('click', function(e) {
  var btn = e.target.closest('[data-screen]');
  if (btn && typeof pywebview !== 'undefined' && pywebview.api) {
    pywebview.api.navigate(btn.dataset.screen);
  }
});

// Cancel button: event-modal div has stopPropagation() so clicks inside the modal
// (Cancel, form, etc.) never bubble up to screen-content. Capture phase runs first.
function handleModalCancel(e) {
  var cancelBtn = e.target.closest('#eventFormCancel, #medFormCancel');
  if (cancelBtn) {
    var ov = document.getElementById(cancelBtn.id === 'eventFormCancel' ? 'eventFormOverlay' : 'medFormOverlay');
    if (ov) ov.style.display = 'none';
    e.stopPropagation();
  }
}
document.getElementById('screen-content').addEventListener('click', handleModalCancel, true);

document.getElementById('screen-content').addEventListener('click', function(e) {
  var addBtn = e.target.closest('#addEventBtn');
  if (addBtn && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_add_event_modal) {
    pywebview.api.open_add_event_modal();
    return;
  }
  var addMedBtn = e.target.closest('#addMedicationBtn');
  if (addMedBtn && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_add_medication_modal) {
    pywebview.api.open_add_medication_modal();
    return;
  }
  var medEditBtn = e.target.closest('.med-edit-btn');
  if (medEditBtn && medEditBtn.dataset.med && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_edit_medication_modal) {
    var m = JSON.parse(medEditBtn.dataset.med);
    if (m && m.id != null) pywebview.api.open_edit_medication_modal(m.id);
    return;
  }
  var medDeleteBtn = e.target.closest('.med-delete-btn');
  if (medDeleteBtn && medDeleteBtn.dataset.medId) {
    if (!confirm('Delete this medication?')) return;
    var mid = parseInt(medDeleteBtn.dataset.medId, 10);
    var res = (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.delete_medication) ? pywebview.api.delete_medication(mid) : 'Delete unavailable';
    function done(r) { if (r !== 'ok') alert(r || 'Failed'); }
    (res && res.then) ? res.then(done).catch(function(x){alert(String(x));}) : done(res);
    return;
  }
  var medTakenBtn = e.target.closest('.med-taken-btn');
  if (medTakenBtn && medTakenBtn.dataset.medId && medTakenBtn.dataset.medTime && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.mark_medication_taken) {
    var mid = parseInt(medTakenBtn.dataset.medId, 10);
    var timeSlot = medTakenBtn.dataset.medTime || '';
    var currentlyDone = medTakenBtn.dataset.medDone === 'true';
    var res = pywebview.api.mark_medication_taken(mid, timeSlot, !currentlyDone);
    function done(r) {
      if (r === 'ok') {
        var screen = (document.body && document.body.dataset.screen) || 'home';
        if (pywebview.api.refresh_screen) pywebview.api.refresh_screen(screen);
        else pywebview.api.refresh_events();
      } else if (r) alert(r);
    }
    (res && res.then) ? res.then(done).catch(function(x){alert(String(x));}) : done(res);
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
  var tile = e.target.closest('.contact-tile[data-sb-uid]');
  if (tile && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_chat) {
    pywebview.api.open_chat(tile.dataset.sbUid || '', tile.dataset.name || '');
    return;
  }
  var screenBtn = e.target.closest('[data-screen]');
  if (screenBtn && typeof pywebview !== 'undefined' && pywebview.api) {
    pywebview.api.navigate(screenBtn.dataset.screen);
    return;
  }
  if (e.target.id === 'eventFormOverlay') {
    e.target.style.display = 'none';
    return;
  }
  if (e.target.id === 'medFormOverlay') {
    e.target.style.display = 'none';
    return;
  }
});


document.getElementById('screen-content').addEventListener('submit', function(e) {
  if (e.target.id === 'medForm') {
    e.preventDefault();
    var name = (document.getElementById('medName') || {}).value || '';
    var dosage = (document.getElementById('medDosage') || {}).value || '';
    var medIdEl = document.getElementById('medId');
    var medId = medIdEl && medIdEl.value ? parseInt(medIdEl.value, 10) : 0;
    var times = [];
    (document.querySelectorAll('#medForm input[name="med_time"]:checked') || []).forEach(function(cb) {
      if (cb.value) times.push(cb.value);
    });
    if (!name || times.length === 0) {
      alert('Name and at least one time required');
      return;
    }
    var payload = { name: name, medication_times: times };
    if (dosage) payload.dosage = dosage;
    var result;
    if (medId) {
      result = (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.update_medication) ? pywebview.api.update_medication(medId, JSON.stringify(payload)) : 'Submit unavailable';
    } else {
      result = (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.add_medication) ? pywebview.api.add_medication(JSON.stringify(payload)) : 'Submit unavailable';
    }
    function done(res) {
      if (res === 'ok') {
        var o = document.getElementById('medFormOverlay');
        if (o) o.style.display = 'none';
        var f = document.getElementById('medForm');
        if (f) f.reset();
      } else { alert(res || 'Failed'); }
    }
    (result && result.then) ? result.then(done).catch(function(x){alert(String(x));}) : done(result);
    return;
  }
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

function showScreen(name, html) {
  var el = document.getElementById('screen-content');
  if (el) {
    el.innerHTML = html;
    document.body.dataset.screen = name;
  }
}

function updateEl(id, content) {
  var el = document.getElementById(id);
  if (el) el.innerHTML = content;
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
