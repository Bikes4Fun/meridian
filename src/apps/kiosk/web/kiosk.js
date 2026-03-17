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
<<<<<<< HEAD
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
=======
      L.marker([m.lat, m.lon]).bindPopup(m.name || '').addTo(map);
>>>>>>> 394e596c47892b56f9c64cb75916bdc12436d778
    });
  } catch (e) {
    var mapEl = document.getElementById('map');
    if (mapEl) mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable</div>';
  }
}
