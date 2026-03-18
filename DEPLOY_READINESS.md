# Deploy readiness — systems not ready for app deploy

This document lists what is **ready for production use** today (backend, dispatch UI, admin) and what is **not yet ready** for driver app deploy or full rollout. Use it to dial in other systems and plan when to enable app distribution.

---

## Ready now (no app deploy required)

| System | Status | Notes |
|--------|--------|--------|
| **Backend API** | Ready | `server.py` + Supabase; auth, jobs, drivers, ingestion, permit-candidates, driver-locations batch, admin API. |
| **Dispatcher web UI** | Ready | Geomapper at `/` (or `/index.html`); login, role routing, dispatch sidebar, permits, jobs, assign, jobs near driver. |
| **Driver portal (web)** | Ready | `/driver.html` for drivers; assignment card, location batching, offline queue (web only). |
| **Admin UI** | Ready | Visible to users with role `admin` in the right sidebar: Users (role/active), Driver state permissions, Settings (dispatch_config). |
| **Auth & roles** | Ready | Supabase Auth; profiles (driver / dispatcher / admin); role-based routing and backend checks. |

Use these for internal or staging: deploy backend (e.g. Railway/Render), point frontend at API, create admin user(s) in Supabase (`profiles.role = 'admin'`), and use the web app. No mobile app or TestFlight needed.

---

## Not ready for app deploy (Phase 6 and related)

These items must be in place before distributing the **driver app** to real drivers (TestFlight, Android link, etc.):

| Item | Plan reference | What to do |
|------|----------------|------------|
| **Driver app build** | Phase 4, 6 | A **Capacitor scaffold** lives in `driver-app/` (syncs from `web/`; see `driver-app/README.md`). Add iOS/Android projects, then build for TestFlight/Play; configure background location (UIBackgroundModes, Android permissions). |
| **TestFlight / Android distribution** | Phase 6.1 | Publish iOS build to TestFlight; provide Android build via link or internal testing. |
| **Test driver verification** | Phase 6.2 | Invite 2–3 test drivers; verify install, login, location permission, background updates, and that Geomapper map/right sidebar update. |
| **Offline queue & idempotency** | Phase 6.3 | Verify offline queue and batch on reconnect; verify retrying same batch does not create duplicate `location_history` rows. |
| **Last-seen & availability** | Phase 6.4 | Verify last-seen freshness (green/yellow/red) and availability rules (e.g. `projected_available_at`, end-of-day cutoff). |

Until these are done, treat driver app as **dev/staging only** and do not rely on it for production driver tracking. Use [PHASE6_VERIFICATION.md](PHASE6_VERIFICATION.md) for a step-by-step verification checklist.

---

## Optional / later (not blocking)

| Item | Notes |
|------|--------|
| **Driver availability calendar API** | Plan “unbuilt”: `driver_availability` table exists; API (GET/PUT per driver) and UI to set available/unavailable/limited by date not yet built. |
| **Full realtime** | Plan 8.7: v1 uses polling; add Supabase Realtime or WebSocket later for live driver positions. |
| **Admin: invite users** | Plan 2.3: create/invite users; currently create users via Supabase Dashboard or `scripts/create_test_users.py` and set role in Admin UI. |

---

## Making a user an admin

1. In Supabase: **Table Editor → `profiles`** → find the user row (by `email` or `id`) → set **`role`** to `admin` → Save.
2. Or run SQL: `UPDATE public.profiles SET role = 'admin' WHERE email = 'your@email.com';`
3. After next login, the Admin section appears in the dispatch right sidebar (Users, State permissions, Settings).

---

## Summary

- **Backend, dispatch UI, driver portal (web), and admin** are ready; deploy and use without distributing a native driver app.
- **Driver app deploy** (TestFlight, Android, real drivers) should wait until Phase 6 steps (build, distribution, test drivers, offline/idempotency, last-seen) are completed and verified.
- Use this checklist to “dial in” each system when you are ready to move to the next step.
