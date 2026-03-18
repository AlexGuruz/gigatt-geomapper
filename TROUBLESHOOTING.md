# Troubleshooting — GIGATT Geomapper

Common issues and where to look. See also [ENV_VARS.md](ENV_VARS.md) and [DEPLOY.md](DEPLOY.md).

---

## New routes not showing from email

- **Refresh:** Click **Refresh** in the sidebar. If the server hasn’t polled in the last ~15 seconds, it will run the email poller once before returning routes.
- **Poll log:** Check `data/poll_log.txt` for the last run (e.g. `added=`, `skipped_sender=`, `skipped_parse=`, `skipped_duplicate=`). Many “skipped sender” means the From address doesn’t match `config.json` → adjust `allowed_senders` or set to `[]` to accept all.
- **Poller running:** Use **Start GIGATT Geomapper.bat** so the background poller runs. If you only started the server, new emails are only ingested when you click Refresh.
- **Format:** The parser expects a line like `City, ST to City, ST` or `City, ST > City, ST` in the email body. See README “New route cards not showing from email?”.

---

## 503 from API (Supabase not configured)

- **Cause:** The backend uses Supabase for jobs, drivers, permits, and auth. If `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` (or equivalent in `.env` or `config.json`) are missing or wrong, many endpoints return 503.
- **Fix:** Follow [PHASE1_SETUP.md](PHASE1_SETUP.md): create a Supabase project, run migrations under `supabase/migrations/`, set env vars (or `config.json` with `supabase_url`, `supabase_anon_key`, and service key via `.env`). See [ENV_VARS.md](ENV_VARS.md).

---

## Driver app (native) can’t connect to backend

- **Cause:** The native app runs in a WebView and doesn’t share the same origin as your backend. It must know the backend URL.
- **Fix:**
  1. On the **login** screen, use “Connect to backend” and enter the backend URL (e.g. `https://your-app.up.railway.app`). This is saved in `localStorage`.
  2. For store builds, set a default API URL so drivers don’t have to type it (see [driver-app/README.md](driver-app/README.md) “Backend URL (native)” and “Store deployment”).
- **CORS:** The backend must allow requests from the app’s origin. If you use Capacitor’s `capacitor://` or `https://` origin, ensure the server (or proxy) allows that origin. See [DEPLOY.md](DEPLOY.md) for production URLs.

---

## Login fails or “Invalid API key”

- **Cause:** Frontend can’t load Supabase config (e.g. `/api/config` fails or returns wrong keys).
- **Fix:** Ensure the server is running and the frontend’s API base is correct (empty = same origin). If the frontend is served from another host (e.g. StackBlitz), set “Connect to backend” on the login page to your backend URL. Backend must have `SUPABASE_URL` and `SUPABASE_ANON_KEY` (or equivalent) and expose them via `GET /api/config`. See [PHASE1_SETUP.md](PHASE1_SETUP.md) and [ENV_VARS.md](ENV_VARS.md).

---

## Admin section not visible

- **Cause:** Your user’s `profiles.role` is not `admin`.
- **Fix:** In Supabase Table Editor → `profiles`, set `role` to `admin` for your user. Or run: `UPDATE public.profiles SET role = 'admin' WHERE email = 'your@email.com';` See [DEPLOY_READINESS.md](DEPLOY_READINESS.md) “Making a user an admin”.

---

## Tests fail (run_api_tests or pytest)

- **Server not running:** Start `python server.py` first. Tests hit `http://127.0.0.1:8080` by default; set `GEOMAPPER_URL` to override.
- **503 / Supabase:** Phase 3, 5, 7 may skip or fail if Supabase isn’t configured. Configure Supabase and re-run.
- **Phase 6:** Requires `GEOMAPPER_DRIVER_ID`. Set it to a valid driver profile UUID (and optionally `GEOMAPPER_ADMIN_JWT` for admin tests). See [TESTING.md](TESTING.md).
