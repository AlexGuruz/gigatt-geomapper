/**
 * Driver portal: fetch assignment, show card with nav link, location batch upload with offline queue.
 * Plan Phase 4: assignment card, navigation link, batch with event_id, ~30s when moving, offline queue.
 */
(function() {
  var API_BASE = (typeof window !== 'undefined' && window.GEOMAPPER_API_BASE) ? window.GEOMAPPER_API_BASE : '';
  var LOCATION_QUEUE_KEY = 'geomapper_driver_location_queue';
  var DRIVER_PROFILE_KEY = 'geomapper_driver_profile';
  var INTERVAL_MOVING_MS = 30000;
  var INTERVAL_STATIONARY_MS = 60000;
  var MIN_MOVEMENT_METERS = 15;
  var lastLat = null, lastLng = null, lastSentAt = 0, lastFixAt = 0, lastUploadAt = 0;
  var watchId = null, flushTimer = null;
  var lastBatchResult = null;
  var driverProfile = null;
  var driverId = null;
  var isMoving = true;
  var usingNative = false;

  function statusEl() {
    return document.getElementById('locationStatus');
  }

  function fmtTime(ms) {
    if (!ms) return '—';
    var d = new Date(ms);
    return isNaN(d.getTime()) ? '—' : d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  function updateStatus(text) {
    var el = statusEl();
    if (!el) return;
    el.textContent = text;
  }

  function updateStatusFromState() {
    var q = getQueue();
    var parts = [];
    parts.push('Tracking: ' + (usingNative ? 'native' : 'web'));
    parts.push('Queue: ' + q.length);
    parts.push('Last fix: ' + fmtTime(lastFixAt));
    parts.push('Last upload: ' + fmtTime(lastUploadAt));
    if (lastBatchResult) parts.push(lastBatchResult);
    updateStatus(parts.join(' · '));
  }

  function haversineMeters(lat1, lng1, lat2, lng2) {
    function toRad(x) { return x * Math.PI / 180; }
    var R = 6371000;
    var dLat = toRad(lat2 - lat1);
    var dLng = toRad(lng2 - lng1);
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
      Math.sin(dLng / 2) * Math.sin(dLng / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function getQueue() {
    try {
      var raw = localStorage.getItem(LOCATION_QUEUE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function setQueue(arr) {
    try {
      localStorage.setItem(LOCATION_QUEUE_KEY, JSON.stringify(arr));
    } catch (e) {}
  }

  function generateEventId() {
    return 'ev_' + Date.now() + '_' + Math.random().toString(36).slice(2, 11);
  }

  function pushToQueue(lat, lng, timestamp, speed, heading) {
    var q = getQueue();
    q.push({
      event_id: generateEventId(),
      lat: lat,
      lng: lng,
      timestamp: typeof timestamp === 'string' ? timestamp : new Date(timestamp).toISOString(),
      speed: speed != null ? speed : undefined,
      heading: heading != null ? heading : undefined
    });
    setQueue(q);
    updateStatusFromState();
  }

  function sendBatch(events, token) {
    if (!events.length || !driverId) return Promise.resolve();
    var url = API_BASE + '/api/driver-locations/batch';
    var headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({ driver_id: driverId, events: events })
    }).then(function(r) {
      if (r.ok) return r.json();
      throw new Error('Batch ' + r.status);
    });
  }

  function flushQueue(token) {
    var q = getQueue();
    if (!q.length) return Promise.resolve();
    return sendBatch(q, token).then(function() {
      setQueue([]);
      lastUploadAt = Date.now();
      lastBatchResult = 'Upload: ok';
      updateStatusFromState();
    }).catch(function() {
      // keep in queue for next reconnect
      lastBatchResult = 'Upload: failed (queued)';
      updateStatusFromState();
    });
  }

  function scheduleFlush(token) {
    if (flushTimer) clearTimeout(flushTimer);
    flushTimer = setTimeout(function() {
      flushTimer = null;
      if (navigator.onLine !== false && token) flushQueue(token);
      scheduleFlush(token);
    }, isMoving ? INTERVAL_MOVING_MS : INTERVAL_STATIONARY_MS);
  }

  function onPosition(position, token) {
    var lat = position.coords.latitude;
    var lng = position.coords.longitude;
    var ts = position.timestamp ? new Date(position.timestamp) : new Date();
    var speed = position.coords.speed != null ? position.coords.speed * 3.6 : null;
    var heading = position.coords.heading;
    lastFixAt = Date.now();
    var moved = true;
    if (lastLat != null && lastLng != null) {
      try {
        moved = haversineMeters(lastLat, lastLng, lat, lng) >= MIN_MOVEMENT_METERS;
      } catch (e) {
        moved = true;
      }
    }
    isMoving = !!moved;
    var now = Date.now();
    var interval = isMoving ? INTERVAL_MOVING_MS : INTERVAL_STATIONARY_MS;
    if (!moved && lastSentAt && (now - lastSentAt) < interval) {
      updateStatusFromState();
      return;
    }
    pushToQueue(lat, lng, ts, speed, heading);
    lastLat = lat;
    lastLng = lng;
    lastSentAt = Date.now();
    updateStatusFromState();
  }

  function getNativeGeolocation() {
    try {
      var cap = window.Capacitor;
      if (!cap || !cap.isNativePlatform || !cap.isNativePlatform()) return null;
      var plugins = cap.Plugins || {};
      return plugins.Geolocation || null;
    } catch (e) {
      return null;
    }
  }

  function startLocationTracking(profileId, token) {
    driverId = profileId;
    var nativeGeo = getNativeGeolocation();
    if (nativeGeo) {
      usingNative = true;
      updateStatusFromState();
      Promise.resolve()
        .then(function() { return nativeGeo.checkPermissions ? nativeGeo.checkPermissions() : null; })
        .then(function(p) {
          if (nativeGeo.requestPermissions) return nativeGeo.requestPermissions();
          return p;
        })
        .then(function() {
          watchId = nativeGeo.watchPosition(
            { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 },
            function(pos, err) {
              if (err) {
                lastBatchResult = 'Fix: error ' + (err.code || '');
                updateStatusFromState();
                return;
              }
              if (pos) onPosition(pos, token);
            }
          );
        })
        .catch(function(e) {
          console.warn('Native geolocation init failed:', e);
          usingNative = false;
          updateStatusFromState();
        });
    } else {
      usingNative = false;
      if (!navigator.geolocation) {
        console.warn('Geolocation not available');
        updateStatus('Location: unavailable');
        return;
      }
      var options = { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 };
      watchId = navigator.geolocation.watchPosition(
        function(pos) { onPosition(pos, token); },
        function(err) {
          console.warn('Geolocation error:', err.code);
          lastBatchResult = 'Fix: error ' + (err.code || '');
          updateStatusFromState();
        },
        options
      );
      updateStatusFromState();
    }
    scheduleFlush(token);
    window.addEventListener('online', function() {
      if (token && driverId) flushQueue(token);
    });
  }

  function stopLocationTracking() {
    if (watchId != null) {
      try {
        var nativeGeo = getNativeGeolocation();
        if (nativeGeo && nativeGeo.clearWatch) {
          nativeGeo.clearWatch({ id: watchId });
        } else if (navigator.geolocation && navigator.geolocation.clearWatch) {
          navigator.geolocation.clearWatch(watchId);
        }
      } catch (e) {}
      watchId = null;
    }
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
  }

  function escapeHtml(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function formatIsoTime(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    return isNaN(d.getTime()) ? '—' : d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  function renderAssignment(job) {
    var card = document.getElementById('driverAssignmentCard');
    if (!card) return;
    if (!job) {
      card.innerHTML = '<h2 style="margin:0 0 0.5rem 0; font-size:0.95rem;">Current assignment</h2><p class="placeholder">No active assignment. Assignments appear here when a dispatcher assigns you a job.</p>';
      return;
    }
    var origin = (job.origin || '').trim();
    var dest = (job.destination || '').trim();
    var navUrl = '';
    if (origin && dest) {
      navUrl = 'https://www.google.com/maps/dir/' + encodeURIComponent(origin) + '/' + encodeURIComponent(dest);
    }
    var html = '<h2 style="margin:0 0 0.5rem 0; font-size:0.95rem;">Current assignment</h2>';
    html += '<div class="driver-job-route">' + escapeHtml(origin + ' → ' + dest) + '</div>';
    html += '<div class="driver-job-meta">ETA ' + formatIsoTime(job.projected_completion) + ' · ' + (job.estimated_miles || '—') + ' mi</div>';
    if (navUrl) {
      html += '<a href="' + escapeHtml(navUrl) + '" target="_blank" rel="noopener" class="driver-nav-link">Open in Google Maps</a>';
    }
    card.innerHTML = html;
  }

  function renderProfile(profile) {
    var el = document.getElementById('driverProfileName');
    if (!el) return;
    if (profile && (profile.name || profile.phone)) {
      el.textContent = (profile.name || '').trim() || profile.phone || 'Driver';
    } else {
      el.textContent = '—';
    }
  }

  function loadDriverData(session) {
    var supabase = window.GeomapperAuth && window.GeomapperAuth.supabase;
    if (!supabase || !session || !session.user) return Promise.resolve(null);
    var userId = session.user.id;
    return supabase.from('driver_profiles').select('id, name, phone, status').eq('user_id', userId).maybeSingle()
      .then(function(r) {
        var profile = (r.data && r.data.id) ? r.data : null;
        if (profile) {
          driverProfile = profile;
          renderProfile(profile);
          try { localStorage.setItem(DRIVER_PROFILE_KEY, JSON.stringify(profile)); } catch (e) {}
          return supabase.from('jobs').select('id, origin, destination, estimated_miles, projected_completion, status').eq('assigned_driver_id', profile.id).in('status', ['assigned', 'active']).maybeSingle();
        }
        renderProfile(null);
        return { data: null };
      })
      .then(function(r) {
        var job = (r.data && r.data.id) ? r.data : null;
        renderAssignment(job);
        return driverProfile;
      })
      .catch(function(e) {
        console.warn('Load driver data failed:', e);
        return null;
      });
  }

  window.DriverPortal = {
    init: function(session) {
      updateStatusFromState();
      loadDriverData(session).then(function(profile) {
        if (profile && session && session.access_token) {
          startLocationTracking(profile.id, session.access_token);
        }
      });
    },
    stop: stopLocationTracking,
    getQueue: getQueue,
    flushQueue: flushQueue
  };
})();
