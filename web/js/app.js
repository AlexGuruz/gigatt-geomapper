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
  let selectedDriverId = null;
  let driverMarkers = [];
  const DRIVER_POLL_MS = 8000;
  let jobs = [];
  let permitCandidates = [];
  let driverRoutePolyline = null;
  let driverRouteMarkers = [];
  let driverJobSummaryEl = null;

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

  /** Turn API/network errors into short, user-friendly messages. */
  function friendlyError(err) {
    if (!err || !err.message) return 'Something went wrong. Please try again.';
    var msg = String(err.message);
    if (msg.indexOf('Server 403') !== -1) return 'You don\'t have permission to do that.';
    if (msg.indexOf('Server 404') !== -1) return 'That item was not found. It may have been removed.';
    if (msg.indexOf('Server 500') !== -1 || msg.indexOf('Server 503') !== -1) return 'Server error. Please try again in a moment.';
    if (msg.indexOf('AbortError') !== -1 || msg.indexOf('Failed to fetch') !== -1 || msg.indexOf('NetworkError') !== -1) return 'Connection problem. Check your network and try again.';
    return msg.length > 80 ? msg.slice(0, 77) + '…' : msg;
  }

  function postJson(path, body) {
    return fetchWithTimeout(API_BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (r) {
      if (!r.ok) throw new Error('Server ' + r.status);
      return r.json();
    });
  }

  function authHeaders() {
    return window.GeomapperAuth && window.GeomapperAuth.getToken
      ? window.GeomapperAuth.getToken().then(function (token) {
          var h = { 'Content-Type': 'application/json' };
          if (token) h['Authorization'] = 'Bearer ' + token;
          return h;
        })
      : Promise.resolve({});
  }

  function getWithAuth(path) {
    return authHeaders().then(function (headers) {
      var opt = { headers: headers };
      if (headers['Content-Type'] === undefined) opt.headers = Object.assign({}, headers, { 'Content-Type': 'application/json' });
      return fetchWithTimeout(API_BASE + path, opt).then(function (r) {
        if (!r.ok) throw new Error('Server ' + r.status);
        return r.json();
      });
    });
  }

  function patchWithAuth(path, body) {
    return authHeaders().then(function (headers) {
      headers['Content-Type'] = 'application/json';
      return fetchWithTimeout(API_BASE + path, {
        method: 'PATCH',
        headers: headers,
        body: JSON.stringify(body),
      }).then(function (r) {
        if (!r.ok) throw new Error('Server ' + r.status);
        return r.json();
      });
    });
  }

  function putWithAuth(path, body) {
    return authHeaders().then(function (headers) {
      headers['Content-Type'] = 'application/json';
      return fetchWithTimeout(API_BASE + path, {
        method: 'PUT',
        headers: headers,
        body: JSON.stringify(body),
      }).then(function (r) {
        if (!r.ok) throw new Error('Server ' + r.status);
        return r.json();
      });
    });
  }

  var currentUser = null;

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

  function getDriverFreshness(driver) {
    var seen = driver.last_seen_at || driver.timestamp;
    if (!seen) return 'off';
    var t = new Date(seen).getTime();
    if (isNaN(t)) return 'off';
    var minAgo = (Date.now() - t) / (60 * 1000);
    if (minAgo < 5) return 'fresh';
    if (minAgo < 30) return 'stale';
    return 'off';
  }

  function updateDriverMarkers() {
    if (!map || !window.google) return;
    driverMarkers.forEach(function (m) {
      m.setMap(null);
    });
    driverMarkers = [];
    var driverIcon = {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 8,
      fillColor: '#58a6ff',
      fillOpacity: 0.9,
      strokeColor: '#1a3646',
      strokeWeight: 2,
    };
    drivers.forEach(function (d) {
      var lat = d.lat != null ? Number(d.lat) : (d.lat_lng && d.lat_lng.lat);
      var lng = d.lng != null ? Number(d.lng) : (d.lat_lng && d.lat_lng.lng);
      if (typeof lat !== 'number' || typeof lng !== 'number' || !isFinite(lat) || !isFinite(lng)) return;
      var m = new google.maps.Marker({
        position: { lat: lat, lng: lng },
        map: map,
        icon: driverIcon,
        title: d.name || d.email || 'Driver',
      });
      m.driver = d;
      m.addListener('click', function () {
        focusDriver(d);
      });
      driverMarkers.push(m);
    });
  }

  function formatJobEta(isoStr) {
    if (!isoStr) return '—';
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  function formatJobAvail(isoStr) {
    if (!isoStr) return '—';
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  }

  function renderDriverList() {
    var el = document.getElementById('driverList');
    if (!el) return;
    if (!drivers.length) {
      el.innerHTML = '<p class="empty-state">No drivers</p>';
      return;
    }
    el.innerHTML = '';
    drivers.forEach(function (d) {
      var card = document.createElement('div');
      card.className = 'driver-card' + (selectedDriverId === (d.id || d.user_id) ? ' selected' : '');
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      var freshness = getDriverFreshness(d);
      var name = (d.name && d.name.trim()) || d.email || 'Driver';
      var status = (d.status || 'off_duty').replace('_', ' ');
      var html = '<span class="driver-freshness ' + freshness + '" aria-hidden="true"></span>' +
        '<div class="driver-name">' + escapeHtml(name) + '</div>' +
        '<div class="driver-meta">' + escapeHtml(status) + '</div>';
      var job = d.assigned_job;
      if (job) {
        html += '<div class="driver-assigned-job">';
        html += '<div class="driver-job-route">' + escapeHtml((job.origin || '') + ' \u2192 ' + (job.destination || '')) + '</div>';
        html += '<div class="driver-job-meta">ETA ' + formatJobEta(job.projected_completion) + ' \u00B7 ' + (job.estimated_miles || '—') + ' mi</div>';
        html += '<div class="driver-job-meta">Avail. ' + formatJobAvail(job.projected_available_at) + '</div>';
        if (job.projected_available_location && job.projected_available_location.address) {
          html += '<div class="driver-job-meta">Next: ' + escapeHtml(job.projected_available_location.address) + '</div>';
        }
        html += '</div>';
      }
      card.innerHTML = html;
      card.addEventListener('click', function () {
        focusDriver(d);
      });
      el.appendChild(card);
    });
  }

  function renderPermitCandidates() {
    var el = document.getElementById('permitCandidatesList');
    if (!el) return;
    var needReview = permitCandidates.filter(function (c) { return (c.review_status || '') === 'needs_review' || (c.review_status || '') === 'insufficient_data'; });
    var approved = permitCandidates.filter(function (c) { return (c.review_status || '') === 'approved'; });
    var list = needReview.concat(approved);
    if (!list.length) {
      el.innerHTML = '<p class="empty-state">No permits to review</p>';
      return;
    }
    el.innerHTML = '';
    list.forEach(function (c) {
      var card = document.createElement('div');
      card.className = 'job-card permit-candidate-card';
      var routeLine = (c.origin_text || '') + ' \u2192 ' + (c.destination_text || '');
      if (!routeLine.trim() || routeLine === ' \u2192 ') routeLine = 'No origin/destination';
      var status = (c.review_status || '').replace('_', ' ');
      card.innerHTML = '<div class="job-card-route">' + escapeHtml(routeLine) + '</div>' +
        '<div class="job-card-meta">' + (c.estimated_miles || '—') + ' mi \u00B7 ' + escapeHtml(status) + '</div>' +
        '<button type="button" class="permit-review-btn">Review</button>';
      card.querySelector('.permit-review-btn').addEventListener('click', function (e) {
        e.stopPropagation();
        openReviewPermitModal(c);
      });
      el.appendChild(card);
    });
  }

  function openReviewPermitModal(candidate) {
    var modal = document.getElementById('reviewPermitModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'reviewPermitModal';
      modal.className = 'modal-overlay';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-label', 'Review permit');
      modal.innerHTML = '<div class="modal-content modal-review"><h3>Review permit</h3><div class="review-fields"></div><div class="review-actions"></div><button type="button" class="modal-close">Close</button></div>';
      document.body.appendChild(modal);
      modal.querySelector('.modal-close').addEventListener('click', function () { modal.classList.remove('open'); });
      modal.addEventListener('click', function (e) { if (e.target === modal) modal.classList.remove('open'); });
    }
    var fields = modal.querySelector('.review-fields');
    var actions = modal.querySelector('.review-actions');
    fields.innerHTML = '<label>Origin <input type="text" id="reviewOrigin" class="review-input"></label>' +
      '<label>Destination <input type="text" id="reviewDest" class="review-input"></label>' +
      '<label>Miles <input type="number" id="reviewMiles" class="review-input" min="0"></label>' +
      '<label>Duration (min) <input type="number" id="reviewDuration" class="review-input" min="0"></label>';
    document.getElementById('reviewOrigin').value = candidate.origin_text || '';
    document.getElementById('reviewDest').value = candidate.destination_text || '';
    document.getElementById('reviewMiles').value = candidate.estimated_miles != null ? candidate.estimated_miles : '';
    document.getElementById('reviewDuration').value = candidate.estimated_duration_minutes != null ? candidate.estimated_duration_minutes : '';
    actions.innerHTML = '';
    if (candidate.review_status !== 'approved' && candidate.review_status !== 'rejected') {
      var approveBtn = document.createElement('button');
      approveBtn.type = 'button';
      approveBtn.className = 'candidate-assign-btn';
      approveBtn.textContent = 'Approve';
      approveBtn.addEventListener('click', function () {
        var payload = getReviewFieldsPayload();
        patch('/api/permit-candidates/' + encodeURIComponent(candidate.id), payload).then(function () {
          return postJson('/api/permit-candidates/' + encodeURIComponent(candidate.id) + '/approve');
        }).then(function () {
          modal.classList.remove('open');
          get('/api/permit-candidates').then(function (r) { permitCandidates = r || []; renderPermitCandidates(); });
        }).catch(function (err) { alert(friendlyError(err)); });
      });
      actions.appendChild(approveBtn);
      var rejectBtn = document.createElement('button');
      rejectBtn.type = 'button';
      rejectBtn.className = 'modal-close';
      rejectBtn.textContent = 'Reject';
      rejectBtn.style.marginLeft = '0.5rem';
      rejectBtn.addEventListener('click', function () {
        postJson('/api/permit-candidates/' + encodeURIComponent(candidate.id) + '/reject').then(function () {
          modal.classList.remove('open');
          get('/api/permit-candidates').then(function (r) { permitCandidates = r || []; renderPermitCandidates(); });
        }).catch(function (err) { alert(friendlyError(err)); });
      });
      actions.appendChild(rejectBtn);
    }
    if (candidate.review_status === 'approved') {
      var createJobBtn = document.createElement('button');
      createJobBtn.type = 'button';
      createJobBtn.className = 'candidate-assign-btn';
      createJobBtn.textContent = 'Create job';
      createJobBtn.addEventListener('click', function () {
        var payload = getReviewFieldsPayload();
        patch('/api/permit-candidates/' + encodeURIComponent(candidate.id), payload).then(function () {
          return postJson('/api/permit-candidates/' + encodeURIComponent(candidate.id) + '/create-job');
        }).then(function (job) {
          modal.classList.remove('open');
          get('/api/jobs').then(function (j) { jobs = j || []; renderUnassignedJobs(); });
          get('/api/permit-candidates').then(function (r) { permitCandidates = r || []; renderPermitCandidates(); });
        }).catch(function (err) { alert(friendlyError(err)); });
      });
      actions.appendChild(createJobBtn);
    }
    modal.classList.add('open');
  }

  function getReviewFieldsPayload() {
    var originEl = document.getElementById('reviewOrigin');
    var destEl = document.getElementById('reviewDest');
    var milesEl = document.getElementById('reviewMiles');
    var durationEl = document.getElementById('reviewDuration');
    var payload = {};
    if (originEl) payload.origin_text = originEl.value;
    if (destEl) payload.destination_text = destEl.value;
    if (milesEl && milesEl.value !== '') payload.estimated_miles = parseInt(milesEl.value, 10);
    if (durationEl && durationEl.value !== '') payload.estimated_duration_minutes = parseInt(durationEl.value, 10);
    return payload;
  }

  function renderJobsNearDriverSelect() {
    var sel = document.getElementById('jobsNearDriverSelect');
    if (!sel) return;
    var first = sel.options[0];
    sel.innerHTML = '';
    if (first) sel.appendChild(first);
    (drivers || []).forEach(function (d) {
      var opt = document.createElement('option');
      opt.value = d.id || d.user_id || '';
      var name = (d.name && d.name.trim()) || d.email || 'Driver';
      opt.textContent = name;
      sel.appendChild(opt);
    });
  }

  function showJobsNearDriver() {
    var sel = document.getElementById('jobsNearDriverSelect');
    var minEl = document.getElementById('jobsNearMinMi');
    var maxEl = document.getElementById('jobsNearMaxMi');
    var listEl = document.getElementById('jobsNearList');
    if (!sel || !listEl) return;
    var driverId = (sel.value || '').trim();
    if (!driverId) {
      listEl.innerHTML = '<p class="empty-state">Select a driver first.</p>';
      return;
    }
    var driver = (drivers || []).filter(function (d) { return (d.id || d.user_id) === driverId; })[0];
    var minMi = (minEl && minEl.value !== '') ? parseInt(minEl.value, 10) : 150;
    var maxMi = (maxEl && maxEl.value !== '') ? parseInt(maxEl.value, 10) : 300;
    if (isNaN(minMi)) minMi = 150;
    if (isNaN(maxMi)) maxMi = 300;
    function doFetch(nearLat, nearLng) {
      var q = 'status=unassigned&near_lat=' + encodeURIComponent(nearLat) + '&near_lng=' + encodeURIComponent(nearLng) + '&min_mi=' + encodeURIComponent(minMi) + '&max_mi=' + encodeURIComponent(maxMi);
      get('/api/jobs?' + q).then(function (jobList) {
        if (!Array.isArray(jobList)) jobList = [];
        listEl.innerHTML = '';
        if (jobList.length === 0) {
          listEl.innerHTML = '<p class="empty-state">No unassigned jobs in that range (jobs need origin_lat/lng).</p>';
          return;
        }
        jobList.forEach(function (job) {
          var card = document.createElement('div');
          card.className = 'job-card job-card-unassigned';
          var routeLine = (job.origin || '') + ' \u2192 ' + (job.destination || '');
          var meta = (job.estimated_miles || '—') + ' mi';
          if (typeof job.distance_mi === 'number') meta += ' \u00B7 ' + job.distance_mi + ' mi from next location';
          card.innerHTML = '<div class="job-card-route">' + escapeHtml(routeLine) + '</div><div class="job-card-meta">' + escapeHtml(meta) + '</div><button type="button" class="job-card-assign-btn">Assign driver</button>';
          var btn = card.querySelector('.job-card-assign-btn');
          if (btn) btn.addEventListener('click', function (e) { e.stopPropagation(); openAssignDriverModal(job); });
          listEl.appendChild(card);
        });
      }).catch(function () {
        listEl.innerHTML = '<p class="empty-state">Failed to load jobs.</p>';
      });
    }
    var loc = driver && driver.assigned_job && driver.assigned_job.projected_available_location;
    var lat = loc && (loc.lat != null) ? Number(loc.lat) : null;
    var lng = loc && (loc.lng != null) ? Number(loc.lng) : null;
    if (typeof lat === 'number' && typeof lng === 'number' && isFinite(lat) && isFinite(lng)) {
      doFetch(lat, lng);
      return;
    }
    var addr = loc && (loc.address || '').trim();
    if (!addr && driver && (driver.lat != null && driver.lng != null)) {
      doFetch(Number(driver.lat), Number(driver.lng));
      return;
    }
    if (!addr) addr = (driver && driver.assigned_job && driver.assigned_job.destination) ? driver.assigned_job.destination : '';
    if (!addr) {
      listEl.innerHTML = '<p class="empty-state">Driver has no next location (assign a job or use current location).</p>';
      return;
    }
    if (!window.google || !window.google.maps || !window.google.maps.Geocoder) {
      listEl.innerHTML = '<p class="empty-state">Geocoder not available.</p>';
      return;
    }
    listEl.innerHTML = '<p class="empty-state">Geocoding…</p>';
    var geocoder = new google.maps.Geocoder();
    geocoder.geocode({ address: addr }, function (results, status) {
      if (status === google.maps.GeocoderStatus.OK && results && results[0] && results[0].geometry) {
        var loc2 = results[0].geometry.location;
        doFetch(loc2.lat(), loc2.lng());
      } else {
        listEl.innerHTML = '<p class="empty-state">Could not geocode address. Use a driver with current location.</p>';
      }
    });
  }

  function renderUnassignedJobs() {
    var el = document.getElementById('unassignedJobsList');
    if (!el) return;
    var unassigned = (jobs || []).filter(function (j) { return (j.status || '') === 'unassigned'; });
    if (!unassigned.length) {
      el.innerHTML = '<p class="empty-state">No unassigned jobs</p>';
      return;
    }
    el.innerHTML = '';
    unassigned.forEach(function (job) {
      var card = document.createElement('div');
      card.className = 'job-card job-card-unassigned';
      var routeLine = (job.origin || '') + ' \u2192 ' + (job.destination || '');
      card.innerHTML = '<div class="job-card-route">' + escapeHtml(routeLine) + '</div>' +
        '<div class="job-card-meta">' + (job.estimated_miles || '—') + ' mi</div>' +
        '<button type="button" class="job-card-assign-btn">Assign driver</button>';
      var btn = card.querySelector('.job-card-assign-btn');
      if (btn) {
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          openAssignDriverModal(job);
        });
      }
      el.appendChild(card);
    });
  }

  function openAssignDriverModal(job) {
    get('/api/jobs/' + encodeURIComponent(job.id) + '/candidate-drivers').then(function (data) {
      var candidates = data.candidates || [];
      var modal = document.getElementById('assignDriverModal');
      if (!modal) {
        modal = document.createElement('div');
        modal.id = 'assignDriverModal';
        modal.className = 'modal-overlay';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-label', 'Assign driver');
        modal.innerHTML = '<div class="modal-content"><h3>Assign driver</h3><p class="modal-job-route"></p><div class="modal-candidates"></div><button type="button" class="modal-close">Close</button></div>';
        document.body.appendChild(modal);
        modal.querySelector('.modal-close').addEventListener('click', function () {
          modal.classList.remove('open');
        });
        modal.addEventListener('click', function (e) {
          if (e.target === modal) modal.classList.remove('open');
        });
      }
      modal.querySelector('.modal-job-route').textContent = (job.origin || '') + ' \u2192 ' + (job.destination || '');
      var list = modal.querySelector('.modal-candidates');
      list.innerHTML = '';
      candidates.forEach(function (c) {
        var d = c.driver || {};
        var row = document.createElement('div');
        row.className = 'modal-candidate' + (c.allowed ? '' : ' blocked');
        var name = (d.name && d.name.trim()) || d.email || 'Driver';
        var badge = c.allowed ? 'Eligible' : ('Blocked: ' + (c.reasons && c.reasons.length ? c.reasons.map(function (r) { return r.message; }).join('; ') : ''));
        row.innerHTML = '<span class="candidate-name">' + escapeHtml(name) + '</span> <span class="candidate-badge">' + escapeHtml(badge) + '</span>';
        if (c.allowed) {
          var assignBtn = document.createElement('button');
          assignBtn.type = 'button';
          assignBtn.className = 'candidate-assign-btn';
          assignBtn.textContent = 'Assign';
          assignBtn.addEventListener('click', function () {
            fetchWithTimeout(API_BASE + '/api/jobs/' + encodeURIComponent(job.id) + '/assign', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ driver_id: d.id }),
            }).then(function (r) {
              return r.json().then(function (body) {
                if (r.ok) {
                  modal.classList.remove('open');
                  get('/api/jobs').then(function (j) { jobs = j || []; renderUnassignedJobs(); });
                  get('/api/drivers').then(function (dr) { drivers = dr || []; renderDriverList(); updateDriverMarkers(); });
                } else {
                  var msg = body.error || ('Server ' + r.status);
                  if (body.reasons && body.reasons.length) {
                    msg += '\n' + body.reasons.map(function (x) { return x.message; }).join('\n');
                  }
                  alert('Assign failed: ' + msg);
                }
              });
            }).catch(function (err) {
              alert('Assign failed: ' + (err && err.message ? err.message : 'Unknown error'));
            });
          });
          row.appendChild(assignBtn);
        }
        list.appendChild(row);
      });
      modal.classList.add('open');
    }).catch(function () {
      alert('Could not load drivers');
    });
  }

  function clearDriverRoute() {
    if (driverRoutePolyline) {
      driverRoutePolyline.setMap(null);
      driverRoutePolyline = null;
    }
    driverRouteMarkers.forEach(function (m) { if (m && m.setMap) m.setMap(null); });
    driverRouteMarkers = [];
    if (driverJobSummaryEl) {
      driverJobSummaryEl.style.display = 'none';
      driverJobSummaryEl.textContent = '';
    }
  }

  function focusDriver(driver) {
    deselectRoute();
    clearDriverRoute();
    selectedDriverId = driver.id || driver.user_id || null;
    renderDriverList();
    var lat = driver.lat != null ? Number(driver.lat) : (driver.lat_lng && driver.lat_lng.lat);
    var lng = driver.lng != null ? Number(driver.lng) : (driver.lat_lng && driver.lat_lng.lng);
    if (map && typeof lat === 'number' && typeof lng === 'number' && isFinite(lat) && isFinite(lng)) {
      map.panTo({ lat: lat, lng: lng });
      map.setZoom(Math.max(map.getZoom(), 10));
    }
    var job = driver.assigned_job;
    if (!job || !map || !window.google) return;
    var originAddr = (job.origin || '').trim();
    var destAddr = (job.destination || '').trim();
    if (!originAddr || !destAddr) return;
    if (!driverJobSummaryEl) {
      driverJobSummaryEl = document.getElementById('driverJobSummary');
      if (!driverJobSummaryEl) {
        driverJobSummaryEl = document.createElement('div');
        driverJobSummaryEl.id = 'driverJobSummary';
        driverJobSummaryEl.className = 'driver-job-summary';
        var rightHeader = document.querySelector('.right-sidebar-header');
        if (rightHeader && rightHeader.nextSibling) {
          rightHeader.parentNode.insertBefore(driverJobSummaryEl, rightHeader.nextSibling);
        } else {
          document.getElementById('driverList').parentNode.insertBefore(driverJobSummaryEl, document.getElementById('driverList'));
        }
      }
    }
    driverJobSummaryEl.innerHTML = '<div class="driver-job-summary-title">Assigned job</div>' +
      '<div class="driver-job-summary-route">' + escapeHtml(originAddr + ' \u2192 ' + destAddr) + '</div>' +
      '<div class="driver-job-summary-meta">ETA ' + formatJobEta(job.projected_completion) + ' \u00B7 ' + (job.estimated_miles || '—') + ' mi \u00B7 Avail. ' + formatJobAvail(job.projected_available_at) + '</div>';
    driverJobSummaryEl.style.display = 'block';
    var geocoder = new google.maps.Geocoder();
    function geocode(addr, cb) {
      if (!addr) { cb(null); return; }
      geocoder.geocode({ address: addr }, function (results, status) {
        if (status === google.maps.GeocoderStatus.OK && results && results[0] && results[0].geometry) {
          var loc = results[0].geometry.location;
          cb({ lat: loc.lat(), lng: loc.lng() });
        } else { cb(null); }
      });
    }
    geocode(originAddr, function (originLatLng) {
      geocode(destAddr, function (destLatLng) {
        if (!originLatLng || !destLatLng) return;
        var startIcon = { path: google.maps.SymbolPath.CIRCLE, scale: 6, fillColor: '#2ea043', fillOpacity: 0.9, strokeColor: '#1a3646', strokeWeight: 1 };
        var stopIcon = { path: google.maps.SymbolPath.CIRCLE, scale: 6, fillColor: '#f85149', fillOpacity: 0.9, strokeColor: '#1a3646', strokeWeight: 1 };
        driverRouteMarkers.push(new google.maps.Marker({ position: originLatLng, map: map, icon: startIcon, title: job.origin }));
        driverRouteMarkers.push(new google.maps.Marker({ position: destLatLng, map: map, icon: stopIcon, title: job.destination }));
        if (!directionsService) directionsService = new google.maps.DirectionsService();
        directionsService.route({
          origin: originLatLng,
          destination: destLatLng,
          travelMode: google.maps.TravelMode.DRIVING,
        }, function (result, status) {
          if (status === google.maps.DirectionsStatus.OK && result.routes && result.routes[0]) {
            var r = result.routes[0];
            var path = r.overview_path || [];
            if (path.length === 0 && r.legs && r.legs[0]) {
              r.legs[0].steps.forEach(function (step) { path = path.concat(step.path); });
            }
            if (path.length > 0) {
              driverRoutePolyline = new google.maps.Polyline({
                path: path,
                geodesic: true,
                strokeColor: '#58a6ff',
                strokeOpacity: 0.9,
                strokeWeight: 4,
                map: map,
              });
              var bounds = new google.maps.LatLngBounds();
              path.forEach(function (p) { bounds.extend(p); });
              if (typeof lat === 'number' && typeof lng === 'number') bounds.extend({ lat: lat, lng: lng });
              fitBoundsWithMaxZoom(bounds, 80, 12);
            }
          }
        });
      });
    });
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
    selectedDriverId = null;
    clearFocus();
    clearDriverRoute();
    renderDriverList();
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
    selectedDriverId = null;
    renderDriverList();
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

  var adminUsers = [];
  var adminStatePerms = [];
  var adminConfig = {};

  function initAdmin() {
    var section = document.getElementById('adminSection');
    if (!section) return;
    section.style.display = 'block';
    var tabs = section.querySelectorAll('.admin-tab');
    var panels = section.querySelectorAll('.admin-panel');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        var t = tab.getAttribute('data-tab');
        tabs.forEach(function (x) { x.classList.remove('active'); });
        panels.forEach(function (p) { p.style.display = 'none'; });
        tab.classList.add('active');
        if (t === 'users') {
          document.getElementById('adminUsersPanel').style.display = 'block';
          loadAdminUsers();
        } else if (t === 'state-permissions') {
          document.getElementById('adminStatePanel').style.display = 'block';
          renderAdminDriverSelect();
          var sel = document.getElementById('adminDriverSelect');
          if (sel) sel.addEventListener('change', function () { loadAdminStatePerms(sel.value); });
          loadAdminStatePerms(sel && sel.value);
        } else if (t === 'config') {
          document.getElementById('adminConfigPanel').style.display = 'block';
          loadAdminConfig();
        }
      });
    });
    document.getElementById('adminStatePermsSave').addEventListener('click', saveAdminStatePerms);
    document.getElementById('adminConfigSave').addEventListener('click', saveAdminConfig);
    loadAdminUsers();
  }

  function loadAdminUsers() {
    getWithAuth('/api/admin/users').then(function (list) {
      adminUsers = list || [];
      var el = document.getElementById('adminUsersList');
      if (!el) return;
      if (!adminUsers.length) { el.innerHTML = '<p class="empty-state">No users</p>'; return; }
      el.innerHTML = '';
      adminUsers.forEach(function (u) {
        var row = document.createElement('div');
        row.className = 'admin-user-row';
        var roleSel = '<select class="admin-user-role" data-id="' + escapeHtml(u.id) + '">' +
          '<option value="driver"' + (u.role === 'driver' ? ' selected' : '') + '>Driver</option>' +
          '<option value="dispatcher"' + (u.role === 'dispatcher' ? ' selected' : '') + '>Dispatcher</option>' +
          '<option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>Admin</option></select>';
        var activeChk = '<input type="checkbox" class="admin-user-active" data-id="' + escapeHtml(u.id) + '"' + (u.active !== false ? ' checked' : '') + '> Active';
        row.innerHTML = '<div class="admin-user-email">' + escapeHtml(u.email || u.id) + '</div><div class="admin-user-edit">' + roleSel + ' ' + activeChk + '</div>';
        el.appendChild(row);
      });
      el.querySelectorAll('.admin-user-role').forEach(function (sel) {
        sel.addEventListener('change', function () {
          var id = sel.getAttribute('data-id');
          patchWithAuth('/api/admin/users/' + encodeURIComponent(id), { role: sel.value }).then(function () { loadAdminUsers(); }).catch(function (e) { alert(e.message || 'Failed'); });
        });
      });
      el.querySelectorAll('.admin-user-active').forEach(function (chk) {
        chk.addEventListener('change', function () {
          var id = chk.getAttribute('data-id');
          patchWithAuth('/api/admin/users/' + encodeURIComponent(id), { active: chk.checked }).then(function () { loadAdminUsers(); }).catch(function (e) { alert(e.message || 'Failed'); });
        });
      });
    }).catch(function (e) {
      var el = document.getElementById('adminUsersList');
      if (el) el.innerHTML = '<p class="empty-state">Failed to load users</p>';
    });
  }

  function renderAdminDriverSelect() {
    var sel = document.getElementById('adminDriverSelect');
    if (!sel) return;
    var first = sel.options[0];
    sel.innerHTML = first ? first.outerHTML : '';
    (drivers || []).forEach(function (d) {
      var opt = document.createElement('option');
      opt.value = d.id || d.user_id || '';
      opt.textContent = (d.name && d.name.trim()) || d.email || 'Driver';
      sel.appendChild(opt);
    });
  }

  function loadAdminStatePerms(driverId) {
    if (!driverId) {
      document.getElementById('adminStatePermsList').innerHTML = '<p class="empty-state">Select a driver</p>';
      return;
    }
    getWithAuth('/api/admin/drivers/' + encodeURIComponent(driverId) + '/state-permissions').then(function (list) {
      adminStatePerms = list || [];
      var el = document.getElementById('adminStatePermsList');
      var states = ['AL','AR','AZ','CA','CO','FL','GA','IA','IL','IN','KS','KY','LA','MO','MS','NE','NM','OK','TN','TX','UT','WV','WY'];
      el.innerHTML = '';
      states.forEach(function (sc) {
        var rec = adminStatePerms.find(function (p) { return (p.state_code || '').trim().toUpperCase() === sc; });
        var allowed = rec ? rec.allowed !== false : false;
        var label = document.createElement('label');
        label.className = 'admin-state-check';
        label.innerHTML = '<input type="checkbox" data-state="' + sc + '"' + (allowed ? ' checked' : '') + '> ' + sc;
        el.appendChild(label);
      });
    }).catch(function () {
      document.getElementById('adminStatePermsList').innerHTML = '<p class="empty-state">Failed to load</p>';
    });
  }

  function saveAdminStatePerms() {
    var sel = document.getElementById('adminDriverSelect');
    var driverId = (sel && sel.value) || '';
    if (!driverId) { alert('Select a driver'); return; }
    var list = document.getElementById('adminStatePermsList');
    var permissions = [];
    if (list) list.querySelectorAll('input[type=checkbox][data-state]').forEach(function (chk) {
      if (chk.checked) permissions.push({ state_code: chk.getAttribute('data-state'), allowed: true });
    });
    putWithAuth('/api/admin/drivers/' + encodeURIComponent(driverId) + '/state-permissions', { permissions: permissions }).then(function () {
      loadAdminStatePerms(driverId);
    }).catch(function (e) { alert(e.message || 'Failed'); });
  }

  function loadAdminConfig() {
    getWithAuth('/api/admin/config').then(function (cfg) {
      adminConfig = cfg || {};
      var el = document.getElementById('adminConfigList');
      el.innerHTML = '';
      var keys = ['dispatch_day_cutoff_time', 'dispatch_next_day_start_time', 'availability_buffer_minutes'];
      keys.forEach(function (k) {
        var v = adminConfig[k];
        if (typeof v === 'string' && v.length >= 2 && v[0] === '"') v = v.slice(1, -1);
        var row = document.createElement('div');
        row.className = 'admin-config-row';
        row.innerHTML = '<label>' + escapeHtml(k) + '</label><input type="text" class="admin-config-value" data-key="' + escapeHtml(k) + '" value="' + escapeHtml(String(v != null ? v : '')) + '">';
        el.appendChild(row);
      });
    }).catch(function () {
      document.getElementById('adminConfigList').innerHTML = '<p class="empty-state">Failed to load config</p>';
    });
  }

  function saveAdminConfig() {
    var updates = {};
    document.querySelectorAll('.admin-config-value').forEach(function (inp) {
      var k = inp.getAttribute('data-key');
      if (k) updates[k] = inp.value;
    });
    patchWithAuth('/api/admin/config', { updates: updates }).then(function () {
      loadAdminConfig();
    }).catch(function (e) { alert(e.message || 'Failed'); });
  }

  function loadData() {
    Promise.all([
      get('/api/routes'),
      get('/api/drivers'),
      get('/api/jobs').catch(function () { return []; }),
      get('/api/permit-candidates').catch(function () { return []; }),
      getWithAuth('/api/me').catch(function () { return null; })
    ]).then(function (results) {
      routes = results[0] || [];
      drivers = results[1] || [];
      jobs = results[2] || [];
      permitCandidates = results[3] || [];
      currentUser = results[4] || null;
      lastUpdated = new Date();
      updateLastUpdatedLabel();
      if (currentUser && currentUser.role === 'admin') initAdmin();
      document.getElementById('timeFilter').addEventListener('change', renderCards);
      document.getElementById('routeTypeFilter').addEventListener('change', renderCards);
      var locationFilterEl = document.getElementById('locationFilter');
      if (locationFilterEl) locationFilterEl.addEventListener('change', renderCards);
      var refreshBtn = document.getElementById('refreshBtn');
      if (refreshBtn) refreshBtn.addEventListener('click', refreshRoutes);
      var clearRouteBtn = document.getElementById('clearRouteBtn');
      if (clearRouteBtn) clearRouteBtn.addEventListener('click', deselectRoute);
      var uploadBtn = document.getElementById('uploadPermitBtn');
      var uploadInput = document.getElementById('uploadPermitInput');
      if (uploadBtn && uploadInput) {
        uploadBtn.addEventListener('click', function () { uploadInput.click(); });
        uploadInput.addEventListener('change', function () {
          var file = uploadInput.files && uploadInput.files[0];
          if (!file) return;
          var fd = new FormData();
          fd.append('file', file);
          fd.append('source_type', 'manual_upload');
          fetch(API_BASE + '/api/ingestion-documents', { method: 'POST', body: fd }).then(function (r) {
            if (!r.ok) return r.json().then(function (b) { throw new Error(b.error || r.status); });
            return r.json();
          }).then(function (doc) {
            return fetch(API_BASE + '/api/ingestion-documents/' + encodeURIComponent(doc.id) + '/parse', { method: 'POST' }).then(function (r2) {
              if (!r2.ok) throw new Error('Parse failed');
              return r2.json();
            });
          }).then(function () {
            uploadInput.value = '';
            get('/api/permit-candidates').then(function (r) { permitCandidates = r || []; renderPermitCandidates(); });
          }).catch(function (err) { alert('Upload/parse failed: ' + (err && err.message ? err.message : err)); });
        });
      }
      renderCards();
      renderPermitCandidates();
      renderJobsNearDriverSelect();
      renderUnassignedJobs();
      renderDriverList();
      updateDriverMarkers();
      var jobsNearShowBtn = document.getElementById('jobsNearShowBtn');
      if (jobsNearShowBtn) jobsNearShowBtn.addEventListener('click', showJobsNearDriver);
      setupZoneTool();
      setupSidebarZone();
    });
  }

  function pollDrivers() {
    get('/api/drivers').then(function (data) {
      drivers = data || [];
      renderDriverList();
      updateDriverMarkers();
    }).catch(function () {});
    get('/api/jobs').then(function (data) {
      jobs = data || [];
      renderUnassignedJobs();
    }).catch(function () {});
    get('/api/permit-candidates').then(function (data) {
      permitCandidates = data || [];
      renderPermitCandidates();
    }).catch(function () {});
    renderJobsNearDriverSelect();
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
  setInterval(pollDrivers, DRIVER_POLL_MS);
})();
