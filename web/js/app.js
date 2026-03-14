(function () {
  var API_BASE = (typeof window !== 'undefined' && window.GEOMAPPER_API_BASE) ? window.GEOMAPPER_API_BASE : '';
  const POLL_INTERVAL_MS = 20000;
  const FETCH_TIMEOUT_MS = 15000;
  var DAY_MS = 24 * 60 * 60 * 1000;
  var TIME_FILTERS = {
    '1': 1 * DAY_MS,
    '2': 2 * DAY_MS,
    '5': 5 * DAY_MS,
    '14': 14 * DAY_MS,
    '30': 30 * DAY_MS,
    '45': 45 * DAY_MS,
    '60': 60 * DAY_MS,
    '90': 90 * DAY_MS,
    '180': 180 * DAY_MS,
    '365': 365 * DAY_MS,
  };

  let map = null;
  let heatmap = null;
  let routes = [];
  let drivers = [];
  let selectedRouteId = null;
  let routeMarkers = [];
  let focusPolyline = null;
  let directionsService = null;
  let focusRouteSummaryEl = null;
  const MILE_TOLERANCE = 25;
  let mapsApiKey = '';
  let zoneActive = false;
  let zoneCenter = null;
  let zoneRadiusMiles = 50;
  let zoneCircle = null;
  let zoneCenterMarker = null;
  let lastUpdated = null;
  let endpointMarkers = [];

  function fetchWithTimeout(url, options, timeoutMs) {
    timeoutMs = timeoutMs || FETCH_TIMEOUT_MS;
    var ctrl = new AbortController();
    var tid = setTimeout(function () { ctrl.abort(); }, timeoutMs);
    options = options || {};
    options.signal = ctrl.signal;
    return fetch(url, options).then(function (r) {
      clearTimeout(tid);
      return r;
    }, function (err) {
      clearTimeout(tid);
      throw err;
    });
  }

  function get(path) {
    return fetchWithTimeout(API_BASE + path).then(function (r) {
      if (!r.ok) throw new Error('Server ' + r.status);
      return r.json();
    });
  }

  function patch(path, body) {
    return fetchWithTimeout(API_BASE + path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (r) {
      if (!r.ok) throw new Error('Server ' + r.status);
      return r.json();
    });
  }

  function post(path) {
    return fetchWithTimeout(API_BASE + path, { method: 'POST' }).then(function (r) {
      if (!r.ok) throw new Error('Server ' + r.status);
      return r.json();
    });
  }

  function initMap() {
    get('/api/config').then(function (config) {
      mapsApiKey = config.mapsApiKey || '';
      function createMap() {
        if (map) return;
        var naBounds = new google.maps.LatLngBounds(
          new google.maps.LatLng(14.0, -130.0),
          new google.maps.LatLng(72.0, -50.0)
        );
        map = new google.maps.Map(document.getElementById('mapContainer'), {
          center: { lat: 39.5, lng: -98.35 },
          zoom: 4,
          styles: darkMapStyles(),
          restriction: { latLngBounds: naBounds, strictBounds: false },
        });
        loadData();
      }
      if (window.google && window.google.maps) {
        createMap();
        return;
      }
      window.__mapsReady = createMap;
      const script = document.createElement('script');
      script.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(mapsApiKey) + '&libraries=visualization,geometry&callback=window.__mapsReady';
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    });
  }

  function darkMapStyles() {
    return [
      { elementType: 'geometry', stylers: [{ color: '#1d2c4d' }] },
      { elementType: 'labels.text.fill', stylers: [{ color: '#8ec3b9' }] },
      { elementType: 'labels.text.stroke', stylers: [{ color: '#1a3646' }] },
      { featureType: 'administrative.country', elementType: 'geometry.stroke', stylers: [{ color: '#4b6878' }] },
      { featureType: 'administrative.land_parcel', elementType: 'labels.text.fill', stylers: [{ color: '#64779e' }] },
      { featureType: 'administrative.province', elementType: 'geometry.stroke', stylers: [{ color: '#4b6878' }] },
      { featureType: 'landscape.man_made', elementType: 'geometry.stroke', stylers: [{ color: '#334e87' }] },
      { featureType: 'landscape.natural', elementType: 'geometry', stylers: [{ color: '#023e58' }] },
      { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#283d6a' }] },
      { featureType: 'poi', elementType: 'labels.text.fill', stylers: [{ color: '#6f9ba5' }] },
      { featureType: 'poi', elementType: 'labels.text.stroke', stylers: [{ color: '#1d2c4d' }] },
      { featureType: 'road', elementType: 'geometry.fill', stylers: [{ color: '#304a7d' }] },
      { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#255763' }] },
      { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#98a5be' }] },
      { featureType: 'road', elementType: 'labels.text.stroke', stylers: [{ color: '#1d2c4d' }] },
      { featureType: 'road.highway', elementType: 'geometry.fill', stylers: [{ color: '#2c6675' }] },
      { featureType: 'road.highway', elementType: 'geometry.stroke', stylers: [{ color: '#255763' }] },
      { featureType: 'transit', elementType: 'labels.text.fill', stylers: [{ color: '#98a5be' }] },
      { featureType: 'transit', elementType: 'labels.text.stroke', stylers: [{ color: '#1d2c4d' }] },
      { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0e1626' }] },
      { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#4e6d70' }] },
    ];
  }

  function updateLastUpdatedLabel() {
    var el = document.getElementById('lastUpdated');
    if (!el) return;
    if (lastUpdated) {
      var t = lastUpdated;
      var label = 'Last updated: ' + t.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' });
      el.textContent = label;
    } else {
      el.textContent = '—';
    }
  }

  /** Ingestion timestamp (when route was posted/ingested) — for time filter only. */
  function getIngestionTimestamp(r) {
    if (r.posted_at) {
      var t = new Date(r.posted_at).getTime();
      if (!isNaN(t)) return t;
    }
    if (r.ingested_at) {
      var t = new Date(r.ingested_at).getTime();
      if (!isNaN(t)) return t;
    }
    return null;
  }

  /** Route date (when route is needed, e.g. 3/14) — for sort only. */
  function getRouteDateMs(r) {
    if (r.date && typeof r.date === 'string') {
      var parts = r.date.trim().match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/);
      if (parts) {
        var year = parseInt(parts[3], 10);
        if (!parts[3] || isNaN(year)) {
          var y = new Date();
          year = y.getFullYear();
        } else if (year < 100) year += 2000;
        var month = parseInt(parts[1], 10) - 1;
        var day = parseInt(parts[2], 10);
        var d = new Date(year, month, day);
        if (!isNaN(d.getTime())) return d.getTime();
      }
    }
    return Infinity;
  }

  function routeInZone(route) {
    if (!zoneActive || !zoneCenter || !zoneRadiusMiles) return true;
    if (!window.google || !window.google.maps || !window.google.maps.geometry) return true;
    var centerLatLng = new google.maps.LatLng(zoneCenter.lat, zoneCenter.lng);
    var radiusMeters = zoneRadiusMiles * 1609.344;
    if (typeof route.origin_lat === 'number' && typeof route.origin_lng === 'number') {
      var originLatLng = new google.maps.LatLng(route.origin_lat, route.origin_lng);
      if (google.maps.geometry.spherical.computeDistanceBetween(centerLatLng, originLatLng) <= radiusMeters) return true;
    }
    if (typeof route.dest_lat === 'number' && typeof route.dest_lng === 'number') {
      var destLatLng = new google.maps.LatLng(route.dest_lat, route.dest_lng);
      if (google.maps.geometry.spherical.computeDistanceBetween(centerLatLng, destLatLng) <= radiusMeters) return true;
    }
    return false;
  }

  function filterRoutes() {
    var timeVal = document.getElementById('timeFilter').value;
    var routeTypeVal = document.getElementById('routeTypeFilter').value;
    var now = Date.now();
    var filtered = routes.filter(function (r) {
      if (timeVal !== 'all') {
        var ingestionMs = getIngestionTimestamp(r);
        if (ingestionMs == null) return false;
        var ms = TIME_FILTERS[timeVal];
        if (ms != null && (now - ingestionMs) > ms) return false;
      }
      if (routeTypeVal !== 'all') {
        var types = r.route_types || [];
        var match = types.some(function (rt) {
          return String(rt).toLowerCase() === routeTypeVal.toLowerCase();
        });
        if (!match) return false;
      }
      return true;
    });
    if (zoneActive && zoneCenter && zoneRadiusMiles) {
      filtered = filtered.filter(routeInZone);
    }
    return filtered;
  }

  function getLocationFilter() {
    var el = document.getElementById('locationFilter');
    return (el && el.value) ? el.value : 'both';
  }

  function getHeatmapPoints(filtered, locationFilter) {
    if (!locationFilter) locationFilter = getLocationFilter();
    const points = [];
    const showStart = locationFilter === 'both' || locationFilter === 'start';
    const showStop = locationFilter === 'both' || locationFilter === 'stop';
    filtered.forEach(function (r) {
      if (showStart && typeof r.origin_lat === 'number' && typeof r.origin_lng === 'number') {
        points.push(new google.maps.LatLng(r.origin_lat, r.origin_lng));
      }
      if (showStop && typeof r.dest_lat === 'number' && typeof r.dest_lng === 'number') {
        points.push(new google.maps.LatLng(r.dest_lat, r.dest_lng));
      }
    });
    return points;
  }

  function updateHeatmap() {
    if (!map || !window.google) return;
    const filtered = filterRoutes();
    const points = getHeatmapPoints(filtered);
    if (points.length > 0) {
      if (heatmap) {
        heatmap.setData(points);
        heatmap.setMap(map);
      } else {
        heatmap = new google.maps.visualization.HeatmapLayer({ data: points, map: map });
      }
    } else {
      if (heatmap) {
        heatmap.setMap(null);
        heatmap = null;
      }
    }
    updateEndpointMarkers();
  }

  function updateEndpointMarkers() {
    if (!map || !window.google) return;
    endpointMarkers.forEach(function (m) {
      m.setMap(null);
    });
    endpointMarkers = [];
    const filtered = filterRoutes();
    const locFilter = getLocationFilter();
    const showStart = locFilter === 'both' || locFilter === 'start';
    const showStop = locFilter === 'both' || locFilter === 'stop';
    const startIcon = {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 6,
      fillColor: '#2ea043',
      fillOpacity: 0.9,
      strokeColor: '#1a3646',
      strokeWeight: 1,
    };
    const stopIcon = {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 6,
      fillColor: '#f85149',
      fillOpacity: 0.9,
      strokeColor: '#1a3646',
      strokeWeight: 1,
    };
    filtered.forEach(function (r) {
      if (showStart && typeof r.origin_lat === 'number' && typeof r.origin_lng === 'number') {
        var originMarker = new google.maps.Marker({
          position: { lat: r.origin_lat, lng: r.origin_lng },
          map: map,
          icon: startIcon,
          title: r.origin || 'Origin',
        });
        originMarker.route = r;
        originMarker.isOrigin = true;
        endpointMarkers.push(originMarker);
      }
      if (showStop && typeof r.dest_lat === 'number' && typeof r.dest_lng === 'number') {
        var destMarker = new google.maps.Marker({
          position: { lat: r.dest_lat, lng: r.dest_lng },
          map: map,
          icon: stopIcon,
          title: r.destination || 'Destination',
        });
        destMarker.route = r;
        destMarker.isOrigin = false;
        endpointMarkers.push(destMarker);
      }
    });
  }

  function syncZoneUI() {
    var mapToggle = document.getElementById('zoneToggle');
    var mapControls = document.getElementById('zoneControls');
    var mapRadius = document.getElementById('zoneRadius');
    var sideToggle = document.getElementById('zoneToggleSidebar');
    var sideControls = document.getElementById('zoneControlsSidebar');
    var sideRadius = document.getElementById('zoneRadiusSidebar');
    var val = String(zoneRadiusMiles);
    if (mapToggle) mapToggle.setAttribute('aria-pressed', zoneActive ? 'true' : 'false');
    if (mapControls) mapControls.style.display = zoneActive ? 'block' : 'none';
    if (mapRadius && mapRadius.value !== val) mapRadius.value = val;
    if (sideToggle) sideToggle.setAttribute('aria-pressed', zoneActive ? 'true' : 'false');
    if (sideControls) sideControls.style.display = zoneActive ? 'block' : 'none';
    if (sideRadius && sideRadius.value !== val) sideRadius.value = val;
  }

  function clearZone() {
    zoneActive = false;
    zoneCenter = null;
    zoneRadiusMiles = 50;
    if (zoneCircle) {
      zoneCircle.setMap(null);
      zoneCircle = null;
    }
    if (zoneCenterMarker) {
      zoneCenterMarker.setMap(null);
      zoneCenterMarker = null;
    }
    syncZoneUI();
    renderCards();
    updateHeatmap();
  }

  function applyZoneCenterAndCircle() {
    if (!map || !window.google || !zoneCenter) return;
    if (zoneCircle) zoneCircle.setMap(null);
    zoneCircle = new google.maps.Circle({
      center: zoneCenter,
      radius: zoneRadiusMiles * 1609.344,
      map: map,
      fillColor: '#58a6ff',
      fillOpacity: 0.08,
      strokeColor: '#58a6ff',
      strokeWeight: 2,
    });
    if (zoneCenterMarker) zoneCenterMarker.setMap(null);
    zoneCenterMarker = new google.maps.Marker({
      position: zoneCenter,
      map: map,
      draggable: true,
      title: 'Zone center (drag to move)',
    });
    zoneCenterMarker.addListener('dragend', function () {
      var pos = zoneCenterMarker.getPosition();
      zoneCenter = { lat: pos.lat(), lng: pos.lng() };
      if (zoneCircle) zoneCircle.setCenter(zoneCenter);
      renderCards();
      updateHeatmap();
    });
  }

  function setupZoneTool() {
    var zoneToggle = document.getElementById('zoneToggle');
    var zoneControls = document.getElementById('zoneControls');
    var zoneRadius = document.getElementById('zoneRadius');
    var zoneClear = document.getElementById('zoneClear');
    if (!zoneToggle || !zoneControls || !map) return;

    zoneToggle.addEventListener('click', function () {
      if (zoneActive) {
        clearZone();
      } else {
        zoneActive = true;
        zoneRadiusMiles = parseInt(zoneRadius.value, 10) || 50;
        syncZoneUI();
      }
    });

    zoneRadius.addEventListener('change', function () {
      zoneRadiusMiles = parseInt(zoneRadius.value, 10) || 50;
      syncZoneUI();
      if (zoneCircle && zoneCenter) {
        zoneCircle.setRadius(zoneRadiusMiles * 1609.344);
      }
      renderCards();
      updateHeatmap();
    });

    zoneClear.addEventListener('click', function () {
      clearZone();
    });

    map.addListener('click', function (event) {
      if (!zoneActive) return;
      zoneCenter = { lat: event.latLng.lat(), lng: event.latLng.lng() };
      zoneRadiusMiles = parseInt(zoneRadius.value, 10) || 50;
      syncZoneUI();
      applyZoneCenterAndCircle();
      renderCards();
      updateHeatmap();
    });
  }

  function setupSidebarZone() {
    var zoneToggleSidebar = document.getElementById('zoneToggleSidebar');
    var zoneControlsSidebar = document.getElementById('zoneControlsSidebar');
    var zoneRadiusSidebar = document.getElementById('zoneRadiusSidebar');
    var zoneClearSidebar = document.getElementById('zoneClearSidebar');
    if (!zoneToggleSidebar || !zoneControlsSidebar || !zoneRadiusSidebar || !zoneClearSidebar) return;

    zoneToggleSidebar.addEventListener('click', function () {
      if (zoneActive) {
        clearZone();
      } else {
        zoneActive = true;
        zoneRadiusMiles = parseInt(zoneRadiusSidebar.value, 10) || 50;
        syncZoneUI();
      }
    });

    zoneRadiusSidebar.addEventListener('change', function () {
      zoneRadiusMiles = parseInt(zoneRadiusSidebar.value, 10) || 50;
      syncZoneUI();
      if (zoneCircle && zoneCenter) {
        zoneCircle.setRadius(zoneRadiusMiles * 1609.344);
      }
      renderCards();
      updateHeatmap();
    });

    zoneClearSidebar.addEventListener('click', function () {
      clearZone();
    });

    syncZoneUI();
  }

  function clearFocus() {
    routeMarkers.forEach(function (m) { m.setMap(null); });
    routeMarkers = [];
    if (focusPolyline) {
      focusPolyline.setMap(null);
      focusPolyline = null;
    }
    if (focusRouteSummaryEl) {
      focusRouteSummaryEl.textContent = '';
      focusRouteSummaryEl.className = 'route-focus-summary';
      focusRouteSummaryEl.style.display = 'none';
    }
    var clearBtn = document.getElementById('clearRouteBtn');
    if (clearBtn) clearBtn.style.display = 'none';
  }

  function deselectRoute() {
    selectedRouteId = null;
    clearFocus();
    renderCards();
  }

  function showRouteSummary(drivingMiles, estimatedMiles) {
    if (!focusRouteSummaryEl) {
      focusRouteSummaryEl = document.getElementById('routeFocusSummary');
    }
    if (!focusRouteSummaryEl) return;
    var msg = 'Driving route: ' + Math.round(drivingMiles) + ' mi';
    var within = true;
    if (estimatedMiles != null && estimatedMiles > 0) {
      var diff = Math.abs(drivingMiles - estimatedMiles);
      within = diff <= MILE_TOLERANCE;
      msg += ' \u00B7 Est. ' + estimatedMiles + ' mi';
      if (within) {
        msg += ' \u2713 Within range';
      } else {
        msg += ' \u2014 Verify (diff ' + Math.round(diff) + ' mi)';
      }
    }
    focusRouteSummaryEl.textContent = msg;
    focusRouteSummaryEl.className = 'route-focus-summary' + (within ? '' : ' route-focus-summary-warn');
    focusRouteSummaryEl.style.display = 'block';
  }

  function fitBoundsWithMaxZoom(bounds, paddingPx, maxZoom) {
    if (!map || !bounds) return;
    maxZoom = maxZoom != null ? maxZoom : 14;
    paddingPx = paddingPx != null ? paddingPx : 80;
    map.fitBounds(bounds, paddingPx);
    google.maps.event.addListenerOnce(map, 'idle', function () {
      var z = map.getZoom();
      if (typeof z === 'number' && z > maxZoom) map.setZoom(maxZoom);
    });
  }

  function focusRoute(route) {
    clearFocus();
    if (!route || !map || !window.google) return;
    var originLat = route.origin_lat;
    var originLng = route.origin_lng;
    var destLat = route.dest_lat;
    var destLng = route.dest_lng;
    if (typeof originLat !== 'number' || typeof originLng !== 'number' || typeof destLat !== 'number' || typeof destLng !== 'number') {
      return;
    }
    var origin = new google.maps.LatLng(originLat, originLng);
    var dest = new google.maps.LatLng(destLat, destLng);
    routeMarkers.push(new google.maps.Marker({ position: origin, map: map, title: route.origin }));
    routeMarkers.push(new google.maps.Marker({ position: dest, map: map, title: route.destination }));

    if (!directionsService) directionsService = new google.maps.DirectionsService();

    directionsService.route({
      origin: origin,
      destination: dest,
      travelMode: google.maps.TravelMode.DRIVING,
    }, function (result, status) {
      if (status === google.maps.DirectionsStatus.OK && result.routes && result.routes[0]) {
        var r = result.routes[0];
        var path = r.overview_path || [];
        if (path.length === 0 && r.legs && r.legs[0]) {
          r.legs[0].steps.forEach(function (step) {
            path = path.concat(step.path);
          });
        }
        if (path.length > 0) {
          focusPolyline = new google.maps.Polyline({
            path: path,
            geodesic: true,
            strokeColor: '#58a6ff',
            strokeOpacity: 0.9,
            strokeWeight: 4,
            map: map,
          });
          var bounds = new google.maps.LatLngBounds();
          path.forEach(function (p) { bounds.extend(p); });
          fitBoundsWithMaxZoom(bounds, 80, 12);
        }
        var drivingMeters = 0;
        if (r.legs) {
          r.legs.forEach(function (leg) {
            if (leg.distance && leg.distance.value) drivingMeters += leg.distance.value;
          });
        }
        var drivingMiles = drivingMeters / 1609.344;
        showRouteSummary(drivingMiles, route.routed_miles != null ? route.routed_miles : route.miles);
      } else {
        var fallbackPath = [origin, dest];
        focusPolyline = new google.maps.Polyline({
          path: fallbackPath,
          geodesic: true,
          strokeColor: '#58a6ff',
          strokeOpacity: 0.7,
          strokeWeight: 3,
          map: map,
        });
        fitBoundsWithMaxZoom(new google.maps.LatLngBounds(origin, dest), 100, 12);
        if (focusRouteSummaryEl) {
          focusRouteSummaryEl.textContent = 'Driving route unavailable; showing straight line.';
          focusRouteSummaryEl.className = 'route-focus-summary route-focus-summary-warn';
          focusRouteSummaryEl.style.display = 'block';
        }
      }
    });
  }

  function renderCards() {
    var filtered = filterRoutes();
    var container = document.getElementById('routeCards');

    if (filtered.length === 0) {
      container.innerHTML = '<div class="empty-state">No routes in this range. Adjust filters or clear the zone.</div>';
      updateHeatmap();
      return;
    }

    // Sort by route date (when needed, e.g. 3/14) - soonest first, then by route line for stable order
    function routeSortKey(r) {
      var line = (r.chase && r.chase.trim()) ? r.chase : ((r.origin || '') + ' \u2192 ' + (r.destination || ''));
      return (line || '') + '\t' + (r.id || '');
    }
    const sorted = filtered.slice().sort(function (a, b) {
      var dateA = getRouteDateMs(a);
      var dateB = getRouteDateMs(b);
      if (dateA !== dateB) return dateA - dateB;
      return routeSortKey(a).localeCompare(routeSortKey(b));
    });

    container.innerHTML = '';
    sorted.forEach(function (r) {
      const card = document.createElement('div');
      card.className = 'route-card' + (selectedRouteId === r.id ? ' selected' : '');
      card.dataset.routeId = r.id;
      var routeLine = (r.chase && r.chase.trim()) ? r.chase : ((r.origin || '') + ' \u2192 ' + (r.destination || ''));
      var metaParts = [];
      if (r.routed_miles != null) metaParts.push(r.routed_miles + ' routed mi');
      else if (r.miles != null) metaParts.push(r.miles + ' mi');
      if (r.route_types && r.route_types.length) metaParts.push(r.route_types.join(' \u00B7 '));
      if (r.date) metaParts.push(r.date);
      var metaLine = metaParts.join(' \u00B7 ');
      var html = '<div class="route-route">' + escapeHtml(routeLine) + '</div>';
      if (metaLine) html += '<div class="route-meta">' + escapeHtml(metaLine) + '</div>';
      if (r.company && r.company.trim()) html += '<div class="route-company">' + escapeHtml(r.company.trim()) + '</div>';
      if (r.pay && r.pay.trim()) html += '<div class="route-pay">' + escapeHtml(r.pay.trim()) + '</div>';
      if (r.phone) html += '<div class="route-contact">' + escapeHtml(r.phone) + (r.phone_text_only ? ' <span class="route-text-only">(Text only)</span>' : '') + '</div>';
      if (r.dot || r.mc) {
        var lic = [];
        if (r.dot) lic.push('DOT ' + escapeHtml(r.dot));
        if (r.mc) lic.push('MC ' + escapeHtml(r.mc));
        html += '<div class="route-licenses">' + lic.join(' \u00B7 ') + '</div>';
      }
      if (r.origin_detail && r.origin_detail.trim()) html += '<div class="route-detail">' + escapeHtml(r.origin_detail.trim()) + '</div>';
      if (r.dest_detail && r.dest_detail.trim()) html += '<div class="route-detail">' + escapeHtml(r.dest_detail.trim()) + '</div>';
      html += '<div class="route-status"><span class="status-' + (r.status || 'new') + '">' + (r.status === 'viewed' ? 'Viewed' : 'New') + '</span></div>';
      card.innerHTML = html;
      card.addEventListener('click', function () {
        if (r.id === selectedRouteId) {
          deselectRoute();
          return;
        }
        selectedRouteId = r.id;
        if ((r.status || 'new') === 'new') {
          patch('/api/routes/' + encodeURIComponent(r.id), { status: 'viewed' }).then(function (updated) {
            var idx = routes.findIndex(function (x) { return x.id === r.id; });
            if (idx >= 0) {
              routes[idx] = updated;
            }
            renderCards();
          });
        }
        renderCards();
        focusRoute(r);
        var clearBtn = document.getElementById('clearRouteBtn');
        if (clearBtn) clearBtn.style.display = 'inline-block';
      });
      container.appendChild(card);
    });

    updateHeatmap();
  }

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function loadData() {
    Promise.all([get('/api/routes'), get('/api/drivers')]).then(function (results) {
      routes = results[0] || [];
      drivers = results[1] || [];
      lastUpdated = new Date();
      updateLastUpdatedLabel();
      document.getElementById('timeFilter').addEventListener('change', renderCards);
      document.getElementById('routeTypeFilter').addEventListener('change', renderCards);
      var locationFilterEl = document.getElementById('locationFilter');
      if (locationFilterEl) locationFilterEl.addEventListener('change', renderCards);
      var refreshBtn = document.getElementById('refreshBtn');
      if (refreshBtn) refreshBtn.addEventListener('click', refreshRoutes);
      var clearRouteBtn = document.getElementById('clearRouteBtn');
      if (clearRouteBtn) clearRouteBtn.addEventListener('click', deselectRoute);
      renderCards();
      setupZoneTool();
      setupSidebarZone();
    });
  }

  function routesSignature(data) {
    if (!data || !data.length) return '';
    return data.length + '-' + data.slice(0, 50).map(function (r) { return r.id || ''; }).join(',');
  }

  function poll() {
    get('/api/routes').then(function (data) {
      var newRoutes = data || [];
      var prevSig = routesSignature(routes);
      var nextSig = routesSignature(newRoutes);
      routes = newRoutes;
      lastUpdated = new Date();
      updateLastUpdatedLabel();
      if (prevSig !== nextSig) {
        renderCards();
      }
    }).catch(function (err) {
      console.warn('Poll failed:', err);
      showPollStatus('Cannot reach server. Is it still running? Refresh or restart the app.', true);
    });
  }

  function showPollStatus(msg, isError) {
    var el = document.getElementById('pollStatus');
    if (!el) return;
    el.textContent = msg;
    el.className = 'poll-status' + (isError ? ' poll-status-error' : '');
    window.clearTimeout(window._pollStatusTimeout);
    window._pollStatusTimeout = window.setTimeout(function () {
      el.textContent = '';
      el.className = 'poll-status';
    }, 8000);
  }

  function refreshRoutes() {
    var btn = document.getElementById('refreshBtn');
    if (btn) btn.disabled = true;
    post('/api/poll').then(function (res) {
      var msg = '';
      if (res && res.polled === true && res.in_background) {
        showPollStatus('Refreshing… New routes will appear in a few seconds.', false);
        get('/api/routes').then(function (data) {
          routes = data || [];
          lastUpdated = new Date();
          updateLastUpdatedLabel();
          renderCards();
        }).catch(function () {});
        var checkInterval = setInterval(function () {
          get('/api/poll/status').then(function (status) {
            if (!status) return;
            if (status.polled === true || (status.polled === false && status.error)) {
              clearInterval(checkInterval);
              var a = status.added || 0;
              var ss = status.skipped_sender || 0;
              var sp = status.skipped_parse || 0;
              var sd = status.skipped_duplicate || 0;
              if (status.error) showPollStatus('Poll error: ' + status.error, true);
              else if (a > 0) showPollStatus('Poll: ' + a + ' new route(s) added.', false);
              else if (ss + sp + sd > 0) showPollStatus('Poll: 0 new (skipped: ' + ss + ' sender, ' + sp + ' unparsed, ' + sd + ' duplicate).', false);
              else showPollStatus('Poll: no new routes.', false);
              if (btn) btn.disabled = false;
            }
          }).catch(function () {});
          get('/api/routes').then(function (data) {
            routes = data || [];
            lastUpdated = new Date();
            updateLastUpdatedLabel();
            renderCards();
          }).catch(function () {});
        }, 2000);
        setTimeout(function () {
          clearInterval(checkInterval);
          if (btn) btn.disabled = false;
        }, 16000);
        return;
      }
      if (res && res.polled === true) {
        var a = res.added || 0;
        var ss = res.skipped_sender || 0;
        var sp = res.skipped_parse || 0;
        var sd = res.skipped_duplicate || 0;
        if (a > 0) msg = 'Poll: ' + a + ' new route(s) added.';
        else if (ss + sp + sd > 0) msg = 'Poll: 0 new (skipped: ' + ss + ' sender, ' + sp + ' unparsed, ' + sd + ' duplicate).';
        else msg = 'Poll: no new routes.';
      } else if (res && res.polled === false && res.error) {
        msg = 'Poll error: ' + res.error;
        showPollStatus(msg, true);
      }
      if (msg && !res.error) showPollStatus(msg, false);
      return get('/api/routes');
    }).then(function (data) {
      if (data === undefined) return;
      routes = data || [];
      lastUpdated = new Date();
      updateLastUpdatedLabel();
      renderCards();
      if (btn) btn.disabled = false;
    }).catch(function (err) {
      showPollStatus('Poll failed. Check data/poll_log.txt for details.', true);
      if (btn) btn.disabled = false;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMap);
  } else {
    initMap();
  }

  setInterval(poll, POLL_INTERVAL_MS);
})();
