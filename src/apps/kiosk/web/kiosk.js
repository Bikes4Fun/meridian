document.getElementById('kiosk-nav').addEventListener('click', function(e) {
  var btn = e.target.closest('[data-screen]');
  if (btn && typeof pywebview !== 'undefined' && pywebview.api) {
    pywebview.api.navigate(btn.dataset.screen);
  }
});

document.getElementById('screen-content').addEventListener('click', function(e) {
  var tile = e.target.closest('.contact-tile[data-sb-uid]');
  if (tile && typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.open_chat) {
    pywebview.api.open_chat(tile.dataset.sbUid || '', tile.dataset.name || '');
    return;
  }
  var addBtn = e.target.closest('#addEventBtn');
  if (addBtn) {
    var overlay = document.getElementById('eventFormOverlay');
    if (overlay) {
      var today = new Date().toISOString().slice(0, 10);
      var dateEl = document.getElementById('eventDate');
      if (dateEl) dateEl.value = today;
      overlay.style.display = 'flex';
    }
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
  }
});

document.getElementById('screen-content').addEventListener('submit', function(e) {
  if (e.target.id !== 'eventForm') return;
  e.preventDefault();
  var overlay = document.getElementById('eventFormOverlay');
  if (!overlay) return;
  var title = (document.getElementById('eventTitle') || {}).value || '';
  var date = (document.getElementById('eventDate') || {}).value || '';
  var startTime = (document.getElementById('eventStartTime') || {}).value || '';
  var endTime = (document.getElementById('eventEndTime') || {}).value || '';
  var location = (document.getElementById('eventLocation') || {}).value || '';
  var description = (document.getElementById('eventDescription') || {}).value || '';
  if (!title || !date || !startTime) return;
  var startDateTime = date + 'T' + startTime + ':00';
  var payload = { title: title, start_time: startDateTime, location: location || undefined, description: description || undefined };
  if (endTime) payload.end_time = date + 'T' + endTime + ':00';

  if (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.add_event) {
    var result = pywebview.api.add_event(JSON.stringify(payload));
    function handleResult(res) {
      if (res === 'ok') {
        overlay.style.display = 'none';
      } else {
        alert(res || 'Failed to add event');
      }
    }
    if (result && typeof result.then === 'function') {
      result.then(handleResult).catch(function(e) { alert(String(e)); });
    } else {
      handleResult(result);
    }
  } else {
    alert('Add event unavailable');
  }
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
