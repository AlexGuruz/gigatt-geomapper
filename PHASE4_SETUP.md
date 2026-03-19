# Phase 4 — Driver App (Capacitor)

**Purpose:** Driver portal at `/driver`, location batching with offline queue, optional Capacitor builds for iOS/Android. Aligned with **plan.md** Section 11 (Phase 4) and Section 5 (Driver Portal).

**Last updated:** 2026-03-15

---

## 1. What’s included (Phase 4)

- **Driver portal** (`driver.html` + `driver-portal.js`): After login, drivers see current assignment (origin → destination, ETA, “Open in Google Maps”), permits placeholder, availability placeholder, profile. Data is loaded from Supabase (RLS: driver sees only own profile and assigned job).
- **Location:** Request permission; collect position; batch events with client-generated `event_id`; send via `POST /api/driver-locations/batch` when online; queue in `localStorage` when offline and flush on reconnect. Send ~30 s when moving, ~60 s when stationary.
- **Auth for batch:** Optional `Authorization: Bearer <Supabase access token>`. If present, server resolves `driver_id` from the token (driver can only post own location). Set `SUPABASE_JWT_SECRET` in `.env` for this. If not set, request body must include `driver_id` (existing behavior).
- **One active session:** Supabase Auth gives one session per user; new login replaces the previous session. No extra backend logic required for “new login invalidates previous” (Section 8.8).

---

## 2. Backend: JWT secret (optional)

To have the server derive `driver_id` from the Bearer token (recommended for production):

1. In Supabase: **Project Settings → API → JWT Secret** (or **JWT Settings**), copy the **JWT Secret**.
2. In your backend `.env` (or env where the server runs), add:
   ```
   SUPABASE_JWT_SECRET=your-jwt-secret-here
   ```
3. Driver app sends `Authorization: Bearer <session.access_token>` with `POST /api/driver-locations/batch`. The server will ignore `driver_id` in the body when auth succeeds and use the resolved driver.

If `SUPABASE_JWT_SECRET` is not set, the driver app can still send `driver_id` in the body (e.g. from their profile); the server does not then verify that the token matches that driver.

---

## 3. Testing the driver portal (web)

1. Run the backend (e.g. `python server.py`).
2. Open `http://127.0.0.1:8080/driver.html` (or your port).
3. Log in with a user whose role is **driver** and who has a row in `driver_profiles` (same `user_id`).
4. You should see the driver portal: assignment card (or “No active assignment”), permits/availability placeholders, profile. If the driver has an assigned job, “Open in Google Maps” appears.
5. Grant location when prompted. With an assignment, the app will batch location and send to `/api/driver-locations/batch` (with Bearer token if you set `SUPABASE_JWT_SECRET`).

---

## 4. Capacitor (iOS / Android) — optional

To build a native app that wraps the same web UI (driver portal + location):

### 4.1 Install Capacitor

From the repo root (or the folder that contains `web/`):

```bash
npm install @capacitor/core @capacitor/cli
npx cap init "GIGATT Geomapper" com.gigatt.geomapper --web-dir web
```

Then add platforms:

```bash
npm install @capacitor/ios @capacitor/android
npx cap add ios
npx cap add android
```

### 4.2 Background location (native)

- **iOS:** In Xcode, open `ios/App/App/Info.plist` and add Location usage descriptions. For background tracking, add `location` to **UIBackgroundModes** (e.g. `<key>UIBackgroundModes</key><array><string>location</string></array>`). Use native geolocation (Capacitor Geolocation plugin) when `Capacitor.isNativePlatform()` is true.
- **Android:** For background tracking you typically need:
  - Manifest permissions (Fine/Coarse and Background)
  - A **foreground service** strategy (Android is strict about background location). Plain web `navigator.geolocation` inside a WebView is not reliably “always on”.
  - Use native geolocation in the driver app when running under Capacitor.

**Important:** “Background” behavior varies by OS version, OEM battery optimizations, and user settings. For best reliability on Android, plan on a foreground-service based approach (and document it for store review).

### 4.3 Build and run

- **iOS:** `npx cap open ios`, then build/run in Xcode (requires macOS).
- **Android:** `npx cap open android`, then build/run in Android Studio.

Point the app at your staging backend (e.g. set `apiBase` / `GEOMAPPER_API_BASE` in config or in the app so `/api/*` and auth hit the correct server).

---

## 5. Acceptance checklist (Phase 4)

- [ ] Driver lands on driver portal (not dispatcher map).
- [ ] Location permission requested; background location configured (when using Capacitor).
- [ ] Batched location sent; offline queue and retry on reconnect work.
- [ ] One active session; new login invalidates previous (Supabase default).
- [ ] iOS and Android builds run and can connect to staging (when Capacitor is set up).
