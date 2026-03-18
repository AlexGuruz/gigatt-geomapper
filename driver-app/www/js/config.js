/**
 * API base URL for backend. Empty = same origin (local dev).
 * When the app is served by the same backend (e.g. local server.py), the backend
 * can provide apiBase via GET /api/config. For StackBlitz: use the "Connect to backend"
 * form on the login page (saved in localStorage) or set here / use app-config.json.
 */
(function() {
  var saved = typeof localStorage !== 'undefined' && localStorage.getItem('geomapper_api_base');
  window.GEOMAPPER_API_BASE = (saved && saved.trim()) ? saved.trim().replace(/\/$/, '') : '';
})();
