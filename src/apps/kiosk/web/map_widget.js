/**
 * Map widget: initializes Leaflet map with markers.
 * Called from Python: initMap(markersJson, placesJson)
 * Find My-style: clusters at same location show pill callout; zoom in to see individuals.
 *
 * Structure: MAP is the container. MARKERS are created in a series of identical steps,
 * then placed on the map.
 */

var CLUSTER_TOLERANCE = 0.0001;
var CLUSTER_ZOOM_THRESHOLD = 14;
var EXPAND_RADIUS = 0.00045;

// -----------------------------------------------------------------------------
// Utilities (shared)
// -----------------------------------------------------------------------------

function escapeHtml(s) {
  if (!s) return '';
  var div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function getInitials(name) {
  if (!name) return '?';
  var parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (name[0] || '?').toUpperCase();
}

// -----------------------------------------------------------------------------
// MARKERS: MarkerCreator and ClusterCreator classes (used repeatedly)
// -----------------------------------------------------------------------------

function groupNearbyMarkers(markers) {
  var groups = [];
  var used = {};
  markers.forEach(function(m, idx) {
    if (used[idx]) return;
    var group = [m];
    used[idx] = true;
    for (var j = idx + 1; j < markers.length; j++) {
      if (used[j]) continue;
      var o = markers[j];
      var dLat = Math.abs(m.lat - o.lat);
      var dLon = Math.abs(m.lon - o.lon) * Math.cos(m.lat * Math.PI / 180);
      if (dLat <= CLUSTER_TOLERANCE && dLon <= CLUSTER_TOLERANCE) {
        group.push(o);
        used[j] = true;
      }
    }
    groups.push(group);
  });
  return groups;
}

function expandGroup(group) {
  if (group.length <= 1) return group;
  var lat = group[0].lat;
  var lon = group[0].lon;
  return group.map(function(m, i) {
    var angle = (2 * Math.PI * i) / group.length;
    return Object.assign({}, m, {
      lat: lat + EXPAND_RADIUS * Math.cos(angle),
      lon: lon + EXPAND_RADIUS * Math.sin(angle) / Math.cos(lat * Math.PI / 180)
    });
  });
}

/** Creates single-person markers. Used repeatedly for each family member. */
class MarkerCreator {
  create(m) {
    var hasPhoto = !!m.photo_src;
    var baseClass = m.is_patient ? 'map-marker-photo map-marker-photo--patient' : 'map-marker-photo';
    var iconHtml;
    if (hasPhoto) {
      iconHtml = '<div class="' + baseClass + '">' +
        '<img src="' + m.photo_src.replace(/"/g, '&quot;') + '" alt=""/>' +
        '</div>';
    } else {
      iconHtml = '<div class="map-marker-initials-pin">' +
        escapeHtml(getInitials(m.name || (m.is_patient ? 'You' : '?'))) + '</div>';
    }
    var size = hasPhoto ? [48, 48] : [32, 40];
    var anchor = hasPhoto ? [24, 48] : [16, 40];
    return L.marker([m.lat, m.lon], {
      icon: L.divIcon({
        html: iconHtml,
        className: 'map-marker-div',
        iconSize: size,
        iconAnchor: anchor,
        popupAnchor: [0, -anchor[1]]
      })
    });
  }

  buildPopup(m) {
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
}

/** Creates cluster markers for multiple people at same location. Used repeatedly per cluster. */
class ClusterCreator {
  _avatarHtml(m) {
    if (m.photo_src) {
      return '<div class="map-cluster-avatar"><img src="' + m.photo_src.replace(/"/g, '&quot;') + '" alt=""/></div>';
    }
    return '<div class="map-cluster-avatar map-cluster-avatar-initials">' + escapeHtml(getInitials(m.name || (m.is_patient ? 'You' : '?'))) + '</div>';
  }

  _calloutHtml(group) {
    var visible = group.slice(0, 3);
    var extra = group.length - 3;
    var html = '<div class="map-cluster-callout">';
    visible.forEach(function(m) {
      html += this._avatarHtml(m);
    }, this);
    if (extra > 0) {
      html += '<div class="map-cluster-badge">+' + extra + '</div>';
    }
    html += '</div>';
    return html;
  }

  create(group) {
    var lat = group[0].lat;
    var lon = group[0].lon;
    var callout = this._calloutHtml(group);
    var icon = L.divIcon({
      html: '<div class="map-cluster-marker">' +
        callout +
        '<div class="map-cluster-pin"></div>' +
        '</div>',
      className: 'map-marker-div map-cluster-div',
      iconSize: [90, 100],
      iconAnchor: [45, 100],
      popupAnchor: [0, -75]
    });
    return L.marker([lat, lon], { icon: icon });
  }

  buildPopup(group) {
    var loc = group[0].location_name || group[0].home_place_name || '';
    var html = loc ? '<div class="map-popup-place">' + escapeHtml(loc) + '</div>' : '';
    html += '<div class="map-cluster-popup-list">';
    group.forEach(function(m) {
      var name = m.is_patient ? 'You' : (m.name || '');
      html += '<div class="map-cluster-popup-item">' + escapeHtml(name) + '</div>';
    });
    html += '</div>';
    return html;
  }
}

/** Build a layer of markers from raw data. Each marker: create -> bind popup -> add to layer. */
function buildMarkerLayer(markers, useClusters) {
  var markerCreator = new MarkerCreator();
  var clusterCreator = new ClusterCreator();
  var groups = groupNearbyMarkers(markers);
  var layer = L.layerGroup();
  groups.forEach(function(group) {
    if (useClusters && group.length > 1) {
      var cluster = clusterCreator.create(group);
      cluster.bindPopup(clusterCreator.buildPopup(group)).addTo(layer);
    } else {
      var toAdd = useClusters ? group : expandGroup(group);
      toAdd.forEach(function(m) {
        var marker = markerCreator.create(m);
        marker.bindPopup(markerCreator.buildPopup(m)).addTo(layer);
      });
    }
  });
  return layer;
}

// -----------------------------------------------------------------------------
// MAP: container setup, tiles, places, and marker placement
// -----------------------------------------------------------------------------

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

function initMap(markersJson, placesJson) {
  function run() {
    try {
      // Remove previous map instance before re-init (e.g. after Refresh)
      if (window._meridianMap) {
        try { window._meridianMap.remove(); } catch (e) {}
        window._meridianMap = null;
      }
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
      window._meridianMap = map;
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
      drawPlaceCircles(map, places);
      var markerLayer = null;
      function placeMarkers() {
        if (markerLayer) map.removeLayer(markerLayer);
        var useClusters = map.getZoom() < CLUSTER_ZOOM_THRESHOLD;
        markerLayer = buildMarkerLayer(markers, useClusters);
        markerLayer.addTo(map);
      }
      placeMarkers();
      map.on('zoomend', placeMarkers);
      map.invalidateSize();
    } catch (e) {
      var mapEl = document.getElementById('map');
      if (mapEl) mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable</div>';
    }
  }
  requestAnimationFrame(function() { requestAnimationFrame(run); });
}
