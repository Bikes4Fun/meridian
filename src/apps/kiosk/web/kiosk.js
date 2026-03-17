document.getElementById('kiosk-nav').addEventListener('click', function(e) {
  var btn = e.target.closest('[data-screen]');
  if (btn && typeof pywebview !== 'undefined' && pywebview.api) {
    pywebview.api.navigate(btn.dataset.screen);
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
      L.marker([m.lat, m.lon]).bindPopup(m.name || '').addTo(map);
    });
  } catch (e) {
    var mapEl = document.getElementById('map');
    if (mapEl) mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable</div>';
  }
}
