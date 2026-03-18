document.getElementById('kiosk-nav').addEventListener('click', function(e) {
  var btn = e.target.closest('[data-screen]');
  if (btn && typeof pywebview !== 'undefined' && pywebview.api) {
    pywebview.api.navigate(btn.dataset.screen);
  }
});

document.getElementById('screen-content').addEventListener('click', function(e) {
  var addBtn = e.target.closest('#addEventBtn');
  if (addBtn && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_add_event_modal) {
    pywebview.api.open_add_event_modal();
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
  var screenBtn = e.target.closest('[data-screen]');
  if (screenBtn && typeof pywebview !== 'undefined' && pywebview.api) {
    pywebview.api.navigate(screenBtn.dataset.screen);
    return;
  }
  var tile = e.target.closest('.contact-tile[data-sb-uid]');
  if (tile && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_chat) {
    pywebview.api.open_chat(tile.dataset.sbUid || '', tile.dataset.name || '');
    return;
  }
  var cancelBtn = e.target.closest('#eventFormCancel');
  if (cancelBtn) {
    var ov = document.getElementById('eventFormOverlay');
    if (ov) ov.style.display = 'none';
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

function initMap(markersJson) {
  try {
    if (typeof L === 'undefined') {
      document.getElementById('map').innerHTML = '<div class="state-placeholder state-error">Map unavailable (offline)</div>';
      return;
    }
    var markers = JSON.parse(markersJson);
    if (!markers || markers.length === 0) return;
    var map = L.map('map').setView([markers[0].lat, markers[0].lon], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    markers.forEach(function(m) {
      var marker;
      if (m.photo_src) {
        var html = '<div class="map-marker-photo" style="width:48px;height:48px;border-radius:50%;overflow:hidden;border:3px solid #4080c0;background:#4080c0">' +
          '<img src="' + m.photo_src.replace(/"/g, '&quot;') + '" alt="" style="width:100%;height:100%;object-fit:cover"/>' +
          '</div>';
        marker = L.marker([m.lat, m.lon], {
          icon: L.divIcon({
            html: html,
            className: 'map-marker-div',
            iconSize: [48, 48],
            iconAnchor: [24, 48],
            popupAnchor: [0, -48]
          })
        });
      } else {
        marker = L.marker([m.lat, m.lon]);
      }
      marker.bindPopup(m.name || '').addTo(map);
    });
  } catch (e) {
    var mapEl = document.getElementById('map');
    if (mapEl) mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable</div>';
  }
}
