# GIGATT Geomapper

Portable web app: poll email for PilotCar load alerts, geocode routes, and view them on a dark map with hot zones and a sidebar of route cards. Assign drivers from a dropdown; filter by time, route type, and zone radius.

**Future direction:** The platform is evolving into a role-based, authenticated driver-tracking and permit-aware dispatch system. See **[plan.md](plan.md)** for the full build plan, phased order, and architecture. Documentation below is aligned with plan.md.

---

## Documentation index

| Document | Purpose |
|----------|---------|
| **[plan.md](plan.md)** | **Single source of truth.** Full build plan: architecture, phases, data model, ingestion pipeline, driver/dispatcher/admin flows, and execution rules. |
| [BASELINE.md](BASELINE.md) | Phase 0 baseline: current endpoints, map/sidebar behavior, routes.json schema, regression checklist. Use to verify “unchanged” after changes. |
| [PHASE1_SETUP.md](PHASE1_SETUP.md) | Phase 1 setup: Supabase project, migrations, env config, test users. Auth + driver-locations batch API. |
| [MIGRATION_PATH.md](MIGRATION_PATH.md) | V1 migration decision (Option A: parallel transition). Plan Section 8.6. |
| [DEPLOY.md](DEPLOY.md) | Deploy backend (Railway/Render); point frontend at API; GitHub + StackBlitz workflow. |
| [HYBRID_CAPACITOR_APP_PLAN.md](HYBRID_CAPACITOR_APP_PLAN.md) | Driver app (Capacitor), role-based routing, availability, and build phases — summary aligned with plan.md. |
| [DRIVER_TRACKING_ARCHITECTURE.md](DRIVER_TRACKING_ARCHITECTURE.md) | Driver tracking, auth, three-piece setup (driver app, backend, Geomapper). Companion to plan.md. |

When in doubt, follow **plan.md** (Section 3: What Must Not Be Broken; Section 11: Phased Build Order; Section 16: Execution Rules for AI Agent).

---

## Quick start

1. Copy `config.json.example` to `config.json`.
2. In `config.json` set:
   - **google_api_key:** Your Google Maps API key (Geocoding + Maps JavaScript + Directions API enabled).
   - For email polling: **imap_user**, **imap_password** (and optionally imap_host, imap_port, imap_folder).
3. (Optional) Add driver names to `data/drivers.json` as a JSON array, e.g. `["Driver A", "Driver B"]`.
4. Run: **Start GIGATT Geomapper.bat** (or start.bat)
   - The launcher checks for Python (portable `python\python.exe` first, then system python). If Python is missing, it opens install_python.html with instructions.
   - Then starts the poller, the local server, and opens the browser to http://127.0.0.1:8080.

**With Supabase (Phase 1+):** For auth and driver-locations batch API, follow [PHASE1_SETUP.md](PHASE1_SETUP.md). See [plan.md](plan.md) Section 11 (Phased Build Order).

---

## Run from USB

Copy the whole GIGATT Geomapper folder to your USB drive. Double-click **Start GIGATT Geomapper.bat** on the target Windows PC. If Python is not installed, the launcher opens install_python.html; you can install Python from python.org or extract a portable Python into a `python` subfolder in this directory so no install is required on the host.

---

## Refresh and on-demand poll

Click **Refresh** in the sidebar to fetch the latest routes. If the server has not run a poll in the last 15 seconds, it runs the email poller once before returning the route list, so new emails are ingested and appear in the cards and map heatmap. The "Last updated" time shows when data was last loaded.

---

## Zone filter (radius)

Use the Zone filter to show only routes whose origin or destination falls within a radius of a point:

- **Map:** Click "Zone filter" in the top-left toolbar on the map, choose radius (mi), then click the map to set the center. Drag the center marker to move it.
- **Sidebar:** Same "Zone filter" toggle, radius dropdown, and "Clear zone" in the sidebar. Both stay in sync. Click the map to set the center when zone mode is on.

---

## Config (config.json)

- **google_api_key** (required for map, geocoding, and driving routes): Create in Google Cloud Console, enable Geocoding API, Maps JavaScript API, and Directions API; restrict the key to http://localhost:*.
- **poll_interval_sec:** Seconds between email polls (default 60).
- **poll_since_days:** On first run (or when no state exists), only consider emails from the last N days (e.g. 7). After that, the poller uses UID to fetch only new messages.
- **poll_recent_days:** Every poll also re-checks the last N days (default 2) so the most recent emails always show up. Set to 0 to disable (only fetch UID > last seen).
- **imap_host, imap_port, imap_user, imap_password, imap_folder:** IMAP settings for load-alert inbox. Leave user/password blank to skip email polling (you can still use the UI with manually added or existing data in `data/routes.json`).
- **allowed_senders:** Optional. List of substrings to match in the email "From" address (e.g. `["team@pilotcarloads.com"]`). Only matching emails are turned into routes. Use an empty list `[]` to accept all senders. If omitted, defaults to `["team@pilotcarloads.com"]`.

---

## API key and secrets

Do not commit `config.json`. You can store the API key in a file and set **google_api_key_path** in config.json, or paste the key into config.json and keep that file out of version control (.gitignore includes config.json). For Supabase, use `.env` for the service key; see [PHASE1_SETUP.md](PHASE1_SETUP.md).

---

## Data files

- **data/routes.json:** List of routes (written by poller, updated by UI when you assign a driver). Each route has a unique id (hash of origin, destination, date, chase) so duplicates are skipped and only new routes are added.
- **data/drivers.json:** List of driver names for the sidebar dropdown. Plan Phase 2+ uses backend drivers from Supabase; see [plan.md](plan.md).
- **data/geocode_cache.json:** Geocoding cache (created automatically).
- **data/poll_log.txt:** Last poll run summary (added/skipped counts). Useful when new emails are not showing—check skipped_sender (wrong From), skipped_parse (email format not recognized), or skipped_duplicate (same route already in list).
- **data/poller_state.json:** Last-seen IMAP UID so only new messages are fetched each run (keeps total_checked low; do not edit).

---

## Run without email

To only use the map and sidebar (no polling): leave **imap_user** and **imap_password** empty in config.json. You can still add routes manually to `data/routes.json` or run the poller once with: `python poller.py --once` after configuring IMAP.

---

## New route cards not showing from email?

1. Click **Refresh** in the sidebar. Read the message under the button: if it says "0 new (skipped: N sender, ...)" then emails are being skipped.
   - Many skipped as "sender": the "From" address does not match config. In config.json set `"allowed_senders": []` to accept all senders, or add the sender address.
   - "unparsed": the email body does not contain a line like "City, ST to City, ST" or "City, ST > City, ST". The parser needs that format.
   - "duplicate": a route with the same origin, destination, date, and route line is already in the list.
2. Check **data/poll_log.txt** for the last poll run (added=, skipped_sender=, skipped_parse=, skipped_duplicate=).
3. Ensure both the poller and the server are running: use **Start GIGATT Geomapper.bat** so the background poller runs every 60–120 seconds. If you only started the server, new emails are only ingested when you click Refresh.
