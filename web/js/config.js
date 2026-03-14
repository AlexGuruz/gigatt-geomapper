/**
 * API base URL for backend. Empty = same origin (local dev).
 * When the app is served by the same backend (e.g. local server.py), the backend
 * can provide apiBase via GET /api/config (from config.json or secrets e.g. Guru Config
 * "Backend URL" / backend_public_url / BACKEND_PUBLIC_URL), and the frontend will set
 * this automatically. For StackBlitz or any host that doesn't run the backend, set it here:
 *   window.GEOMAPPER_API_BASE = 'https://your-app.up.railway.app';
 */
window.GEOMAPPER_API_BASE = '';
