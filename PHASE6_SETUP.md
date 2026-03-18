# Phase 6 — Rollout + hardening

Plan Phase 6: publish driver app, verify with test drivers, offline queue, last-seen freshness.

## 6.1 Publish driver app (TestFlight / Android)

- **iOS**: Build with Capacitor, upload to App Store Connect, submit for TestFlight. See `PHASE4_SETUP.md` for `npx cap build ios` and Xcode archive.
- **Android**: Build with `npx cap build android`, sign APK/AAB, distribute via internal track or direct link.

## 6.2 Test drivers (2–3)

1. Invite test drivers (Supabase Auth invites or sign-up).
2. Ensure each has a `driver_profiles` row and `profiles.role = 'driver'`.
3. Verify: install app → login → grant location (Always when possible) → confirm Geomapper map and right sidebar update when driver has an assignment.

## 6.3 Offline queue and idempotency

- **Offline queue**: Driver portal queues location events in `localStorage` when offline; on `online` it flushes to `POST /api/driver-locations/batch`. See `web/js/driver-portal.js`.
- **Idempotency**: Batch endpoint uses `event_id`; duplicate `event_id` for same driver is treated as success (no duplicate row in `location_history`). Test with:
  ```bash
  python scripts/test_phase6_batch_idempotency.py http://127.0.0.1:8080 <DRIVER_UUID>
  ```
  Use a valid driver JWT in env if the server requires `Authorization: Bearer` (set `SUPABASE_JWT_SECRET` and pass token when you have a driver session).

## 6.4 Last-seen freshness and availability

- **Freshness (green/yellow/red)**: Dispatcher UI uses `getDriverFreshness(d)` (e.g. last_seen_at vs thresholds). Ensure `driver_profiles.last_seen_at` is updated by the batch endpoint.
- **projected_available_at / end-of-day**: Assignment flow computes `projected_available_at` from job completion and `dispatch_config` (cutoff, next-day start). Verify in assign modal and driver card.

## Acceptance checklist

- [ ] Driver app published to TestFlight (iOS) and distributable (Android).
- [ ] 2–3 test drivers: install, login, location, background updates.
- [ ] Offline queue and idempotency verified (script or manual).
- [ ] Last-seen freshness and availability rules working in UI.
