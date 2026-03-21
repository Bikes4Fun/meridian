/**
 * Map widget: initializes Leaflet map with markers.
 * Called from Python: initMap(markersJson, placesJson)
 */

function escapeHtml(s) {
  if (!s) return '';
  var div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function drawPlaceCircles(map, places) {
  places.forEach(function(p) {
    if (p.gps_latitude != null && p.gps_longitude != null) {
      L.circle([p.gps_latitude, p.gps_longitude], {
        radius: p.radius_metres || 150,
        fillOpacity: 0.08,
        fillColor: '#4080c0',
        color: '#4080c0',
        weight: 1
      }).addTo(map);
    }
  });
}

function applyMarkerJitter(markers, jitter) {
  jitter = jitter || 0.00015;
  var byPos = {};
  markers.forEach(function(m) {
    var key = m.lat + ',' + m.lon;
    if (!byPos[key]) byPos[key] = [];
    byPos[key].push(m);
  });
  Object.keys(byPos).forEach(function(key) {
    var group = byPos[key];
    group.forEach(function(m, i) {
      if (i > 0) {
        m.lat = m.lat + (Math.random() - 0.5) * 2 * jitter;
        m.lon = m.lon + (Math.random() - 0.5) * 2 * jitter;
      }
    });
  });
}

function buildPopupHtml(m) {
  if (m.is_patient) {
    return '<strong>You are home at ' + escapeHtml(m.home_place_name || 'Home') + '</strong>';
  }
  var html = '';
  if (m.location_name) {
    html += '<div class="map-popup-place">' + escapeHtml(m.location_name) + '</div>';
  }
  html += '<div class="map-popup-name">' + escapeHtml(m.name || '') + '</div>';
  return html;
}

function createMarker(m) {
  if (m.photo_src) {
    var photoClass = m.is_patient ? 'map-marker-photo map-marker-photo--patient' : 'map-marker-photo';
    var iconHtml = '<div class="' + photoClass + '">' +
      '<img src="' + m.photo_src.replace(/"/g, '&quot;') + '" alt=""/>' +
      '</div>';
    return L.marker([m.lat, m.lon], {
      icon: L.divIcon({
        html: iconHtml,
        className: 'map-marker-div',
        iconSize: [48, 48],
        iconAnchor: [24, 48],
        popupAnchor: [0, -48]
      })
    });
  }
  return L.marker([m.lat, m.lon]);
}

function addMarkersToMap(map, markers) {
  markers.forEach(function(m) {
    var marker = createMarker(m);
    marker.bindPopup(buildPopupHtml(m)).addTo(map);
  });
}

function initMap(markersJson, placesJson) {
  try {
    var mapEl = document.getElementById('map');
    if (!mapEl) return;
    if (typeof L === 'undefined') {
      mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable (offline)</div>';
      return;
    }
    var markers = JSON.parse(markersJson);
    var places = placesJson ? JSON.parse(placesJson) : [];
    if (!markers || markers.length === 0) return;

    var map = L.map('map').setView([markers[0].lat, markers[0].lon], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    drawPlaceCircles(map, places);
    applyMarkerJitter(markers);
    addMarkersToMap(map, markers);
  } catch (e) {
    var mapEl = document.getElementById('map');
    if (mapEl) mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable</div>';
  }
}
