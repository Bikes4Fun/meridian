/**
 * Map widget: initializes Leaflet map with markers.
 * Called from Python: initMap(markersJson)
 */
function initMap(markersJson) {
  try {
    var mapEl = document.getElementById('map');
    if (!mapEl) return;
    if (typeof L === 'undefined') {
      mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable (offline)</div>';
      return;
    }
    var markers = JSON.parse(markersJson);
    if (!markers || markers.length === 0) return;
    var map = L.map('map').setView([markers[0].lat, markers[0].lon], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    markers.forEach(function(m) {
      var marker;
      var popupText = m.is_patient
        ? '<strong>You are home at ' + (m.home_place_name || 'Home') + '</strong>'
        : (m.name || '');
      if (m.photo_src) {
        var photoClass = m.is_patient ? 'map-marker-photo map-marker-photo--patient' : 'map-marker-photo';
        var html = '<div class="' + photoClass + '">' +
          '<img src="' + m.photo_src.replace(/"/g, '&quot;') + '" alt=""/>' +
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
      marker.bindPopup(popupText).addTo(map);
    });
  } catch (e) {
    var mapEl = document.getElementById('map');
    if (mapEl) mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable</div>';
  }
}
