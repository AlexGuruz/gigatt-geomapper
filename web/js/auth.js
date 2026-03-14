/**
 * GIGATT Geomapper - Auth & role-based routing.
 * Plan Section 2.2: driver → /driver, dispatcher → /dispatch, admin → /dispatch.
 */
(function() {
  var supabase = null;
  var config = { supabaseUrl: '', supabaseAnonKey: '' };

  function init() {
    var base = (typeof window !== 'undefined' && window.GEOMAPPER_API_BASE) ? window.GEOMAPPER_API_BASE : '';
    return fetch(base + '/api/config')
      .then(function(r) { return r.ok ? r.json() : {}; })
      .catch(function() { return {}; })
      .then(function(cfg) {
        config.supabaseUrl = cfg.supabaseUrl || cfg.supabase_url || '';
        config.supabaseAnonKey = cfg.supabaseAnonKey || cfg.supabase_anon_key || '';
        if (config.supabaseUrl && config.supabaseAnonKey) {
          try {
            if (window.supabase && window.supabase.createClient) {
              supabase = window.supabase.createClient(config.supabaseUrl, config.supabaseAnonKey);
            }
          } catch (e) {
            console.warn('Auth init failed:', e);
          }
        }
        return !!supabase;
      });
  }

  function getRole(session) {
    if (!session || !session.user) return null;
    return (session.user.user_metadata && session.user.user_metadata.role) || null;
  }

  function fetchRole(session) {
    if (!supabase || !session) return Promise.resolve(null);
    return supabase.from('profiles').select('role').eq('id', session.user.id).single()
      .then(function(r) { return (r.data && r.data.role) || null; })
      .catch(function() { return null; });
  }

  function redirectByRole(session) {
    return fetchRole(session).then(function(role) {
      role = role || getRole(session) || 'driver';
      if (role === 'driver') {
        window.location.href = '/driver.html';
        return;
      }
      if (role === 'dispatcher' || role === 'admin') {
        window.location.href = '/index.html';
        return;
      }
      window.location.href = '/index.html';
    });
  }

  function requireAuth(onAuthenticated) {
    init().then(function(hasAuth) {
      if (!hasAuth) {
        window.location.href = '/login.html';
        return;
      }
      return supabase.auth.getSession().then(function(r) {
        if (!r.data.session) {
          window.location.href = '/login.html';
          return;
        }
        if (onAuthenticated) onAuthenticated(r.data.session, true);
      });
    });
  }

  function guardPage(redirectIfDriver, onStay) {
    requireAuth(function(session, ok) {
      if (!ok || !session) return;
      fetchRole(session).then(function(role) {
        role = role || 'driver';
        if (redirectIfDriver && role === 'driver') {
          window.location.href = '/driver.html';
          return;
        }
        if (!redirectIfDriver && role !== 'driver') {
          window.location.href = '/index.html';
          return;
        }
        if (typeof onStay === 'function') onStay();
      });
    });
  }

  window.GeomapperAuth = {
    init: init,
    supabase: null,
    get supabase() {
      if (!supabase && config.supabaseUrl && config.supabaseAnonKey) {
        try {
          if (window.supabase && window.supabase.createClient) {
            supabase = window.supabase.createClient(config.supabaseUrl, config.supabaseAnonKey);
          }
        } catch (e) {}
      }
      return supabase;
    },
    redirectByRole: redirectByRole,
    requireAuth: requireAuth,
    guardPage: guardPage,
    getToken: function() {
      return supabase && supabase.auth.getSession().then(function(r) {
        return (r.data && r.data.session && r.data.session.access_token) || null;
      });
    }
  };

  init().then(function(hasAuth) {
    if (hasAuth && supabase) {
      Object.defineProperty(window.GeomapperAuth, 'supabase', { value: supabase, writable: false });
    }
  });
})();
