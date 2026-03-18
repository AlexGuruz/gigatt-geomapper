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
  var lastLat = null, lastLng = null, lastSentAt = 0, watchId = null, flushTimer = null;
  var driverProfile = null;
  var driverId = null;

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
    }).catch(function() {
      // keep in queue for next reconnect
    });
  }

  function scheduleFlush(token) {
    if (flushTimer) clearTimeout(flushTimer);
    flushTimer = setTimeout(function() {
      flushTimer = null;
      if (navigator.onLine !== false && token) flushQueue(token);
      scheduleFlush(token);
    }, INTERVAL_MOVING_MS);
  }

  function onPosition(position, token) {
    var lat = position.coords.latitude;
    var lng = position.coords.longitude;
    var ts = position.timestamp ? new Date(position.timestamp) : new Date();
    var speed = position.coords.speed != null ? position.coords.speed * 3.6 : null;
    var heading = position.coords.heading;
    pushToQueue(lat, lng, ts, speed, heading);
    lastLat = lat;
    lastLng = lng;
    lastSentAt = Date.now();
  }

  function startLocationTracking(profileId, token) {
    driverId = profileId;
    if (!navigator.geolocation) {
      console.warn('Geolocation not available');
      return;
    }
    var options = { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 };
    watchId = navigator.geolocation.watchPosition(
      function(pos) { onPosition(pos, token); },
      function(err) { console.warn('Geolocation error:', err.code); },
      options
    );
    scheduleFlush(token);
    window.addEventListener('online', function() {
      if (token && driverId) flushQueue(token);
    });
  }

  function stopLocationTracking() {
    if (watchId != null) {
      navigator.geolocation.clearWatch(watchId);
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
