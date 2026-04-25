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

/**
 * @param {boolean} [forPopup] if true, add .map-cluster-popup-avatar (Leaflet popup list only).
 */
function mapClusterAvatarCellHtml(m, forPopup) {
  var pCls = forPopup ? ' map-cluster-popup-avatar' : '';
  if (m && m.photo_src) {
    return (
      '<div class="map-cluster-avatar' +
      pCls +
      '"><img src="' +
      m.photo_src.replace(/"/g, '&quot;') +
      '" alt=""/></div>'
    );
  }
  var n = m ? m.name : '';
  if (m && m.is_patient) n = 'You';
  return (
    '<div class="map-cluster-avatar map-cluster-avatar-initials' +
    pCls +
    '">' +
    escapeHtml(getInitials(n || '?')) +
    '</div>'
  );
}

/** List row: avatar + name (+ optional subline for patient home); opens family detail when detail_key set. */
function mapClusterPopupItemHtml(m) {
  var name = m && m.is_patient ? 'You' : (m && m.name) || '';
  var nameHtml = '<div class="map-cluster-popup-name-text">' + escapeHtml(name) + '</div>';
  var dk = m && m.detail_key != null && String(m.detail_key).length ? m.detail_key : '';
  var rowInner =
    mapClusterAvatarCellHtml(m, true) +
    '<div class="map-cluster-popup-text-wrap">' +
    nameHtml +
    '</div>';
  if (dk) {
    return (
      '<div class="map-cluster-popup-item map-cluster-popup-item--action" data-detail-key-enc="' +
      encodeURIComponent(dk) +
      '" role="button" tabindex="0"><div class="map-cluster-popup-item-inner">' +
      rowInner +
      '</div></div>'
    );
  }
  return (
    '<div class="map-cluster-popup-item"><div class="map-cluster-popup-item-inner">' + rowInner + '</div></div>'
  );
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
      var ph = '<div class="map-popup-patient-below">';
      if (m.home_place_name) {
        ph += '<div class="map-popup-place">' + escapeHtml(m.home_place_name) + '</div>';
      }
      ph += '<div class="map-cluster-popup-list">' + mapClusterPopupItemHtml(m) + '</div></div>';
      return ph;
    }
    var h = '';
    if (m.location_name) {
      h += '<div class="map-popup-place">' + escapeHtml(m.location_name) + '</div>';
    }
    h += '<div class="map-cluster-popup-list map-popup-single-below">' + mapClusterPopupItemHtml(m) + '</div>';
    return h;
  }
}

/** Creates cluster markers for multiple people at same location. Used repeatedly per cluster. */
class ClusterCreator {
  _avatarHtml(m) {
    return mapClusterAvatarCellHtml(m, false);
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
      html += mapClusterPopupItemHtml(m);
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
        if (m.detail_key && typeof window.meridianOpenFamilyMemberDetail === 'function') {
          marker.on('click', function() {
            window.meridianOpenFamilyMemberDetail(m.detail_key);
          });
        }
      });
    }
  });
  return layer;
}

// -----------------------------------------------------------------------------
// MAP: container setup, tiles, places, and marker placement
// -----------------------------------------------------------------------------

/** Family screen: pan map so geographic center sits at viewport center of the band above the open panel (no zoom change). */
function applyKioskFamilyMapViewOffset(map) {
  try {
    if (typeof document === 'undefined' || !document.body) return;
    if (document.body.dataset.screen !== 'family') return;
    var panel = document.querySelector('.family-locations-layout .family-panel');
    var container = map.getContainer();
    if (!panel || !container) return;
    var mapSize = map.getSize();
    if (!mapSize || mapSize.x < 80 || mapSize.y < 80) return;
    var mapRect = container.getBoundingClientRect();
    var wasMin = panel.classList.contains('family-panel--minimized');
    if (wasMin) panel.classList.remove('family-panel--minimized');
    void panel.offsetHeight;
    var panelRect = panel.getBoundingClientRect();
    if (wasMin) panel.classList.add('family-panel--minimized');
    var panelTopRel = panelRect.top - mapRect.top;
    if (panelTopRel < 24 || panelTopRel > mapSize.y - 8) return;
    var cx = mapSize.x / 2;
    var cy = panelTopRel / 2;
    var ll = map.getCenter();
    var cur = map.latLngToContainerPoint(ll);
    var dx = cx - cur.x;
    var dy = cy - cur.y;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
    map.panBy(L.point(dx, dy), { animate: false });
  } catch (e) {}
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

function initMap(markersJson, placesJson) {
  function run() {
    try {
      // Remove previous map instance before re-init (e.g. after Refresh)
      if (window._meridianMap) {
        try { window._meridianMap.remove(); } catch (e) {}
        window._meridianMap = null;
        window._familyMap = null;
      }
      var mapEl = document.getElementById('map');
      if (!mapEl) return;
      if (typeof L === 'undefined') {
        mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable (offline)</div>';
        return;
      }
      var markers = JSON.parse(markersJson) || [];
      var places = placesJson ? JSON.parse(placesJson) : [];
      var center, zoom = 11;
      if (markers.length > 0) {
        var latlngs = markers.map(function(m) {
          return [m.lat, m.lon];
        });
        center = L.latLngBounds(latlngs).getCenter();
      } else if (places.length > 0 && places[0].gps_latitude != null && places[0].gps_longitude != null) {
        center = [places[0].gps_latitude, places[0].gps_longitude];
      } else {
        center = [37.7749, -122.4194];
        zoom = 4;
      }

      var map = L.map('map').setView(center, zoom);
      window._meridianMap = map;
      window._familyMap = map;
      var origin = (typeof window !== 'undefined' && window.location && window.location.origin) ? window.location.origin : '';
      var isHttpOrigin = origin && /^https?:\/\//i.test(origin);
      var osmRemote = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
      var tileUrl = isHttpOrigin ? (origin + '/kiosk/osm-tiles/{z}/{x}/{y}.png') : osmRemote;
      var tileOpts = {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      };
      if (tileUrl.indexOf('openstreetmap') >= 0) {
        tileOpts.subdomains = 'abc';
      }
      L.tileLayer(tileUrl, tileOpts).addTo(map);
      drawPlaceCircles(map, places);
      var markerLayer = null;
      function placeMarkers() {
        if (markerLayer) map.removeLayer(markerLayer);
        if (markers.length === 0) return;
        var useClusters = map.getZoom() < CLUSTER_ZOOM_THRESHOLD;
        markerLayer = buildMarkerLayer(markers, useClusters);
        markerLayer.addTo(map);
      }
      placeMarkers();
      if (markers.length > 0) map.on('zoomend', placeMarkers);
      map.invalidateSize();
      requestAnimationFrame(function() {
        map.invalidateSize();
      });
    } catch (e) {
      var mapEl = document.getElementById('map');
      if (mapEl) mapEl.innerHTML = '<div class="state-placeholder state-error">Map unavailable</div>';
    }
  }
  requestAnimationFrame(function() { requestAnimationFrame(run); });
}
