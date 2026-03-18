# Phase 6 — Verification checklist

Use this **after** the driver app is built (Capacitor iOS/Android) and before or alongside TestFlight/Play distribution. Plan reference: Section 11 Phase 6, [DEPLOY_READINESS.md](DEPLOY_READINESS.md).

---

## 6.1 Distribution (when ready)

- [ ] **iOS:** Build with Xcode, upload to App Store Connect, enable TestFlight, invite internal testers.
- [ ] **Android:** Build release APK or AAB; distribute via Play Console internal testing or direct link.

---

## 6.2 Test driver verification

Invite 2–3 test drivers. For each, confirm:

- [ ] Install app from TestFlight (iOS) or link/APK (Android).
- [ ] Sign in with assigned account (Supabase Auth).
- [ ] Grant location permission (prefer “Always” for background).
- [ ] Driver lands on **driver portal** (assignment card, not dispatcher map).
- [ ] **Geomapper (dispatcher):** With the same backend, open Geomapper as dispatcher; confirm driver appears in the right sidebar with status and (after location is sent) last-seen freshness.
- [ ] Assign a job to the test driver from Geomapper; confirm assignment appears on the driver app.

---

## 6.3 Offline queue and idempotency

- [ ] **Offline:** Turn off device network (or airplane mode); use the driver app (e.g. move around). Re-enable network; confirm location batch is sent and Geomapper shows updated position.
- [ ] **Idempotency:** Use script `scripts/test_phase6_batch_idempotency.py` if available, or manually POST the same `driver-locations/batch` payload (same `event_id`s) twice; confirm no duplicate rows in `location_history` and response is success both times.

---

## 6.4 Last-seen and availability

- [ ] **Last-seen:** In Geomapper driver list, confirm freshness (green/yellow/red) updates as the driver app sends batches (or stops sending).
- [ ] **Availability:** If using `projected_available_at` / end-of-day rule, assign a job to a driver and confirm driver card shows expected “available at” time; confirm config keys `dispatch_day_cutoff_time`, `dispatch_next_day_start_time`, `availability_buffer_minutes` are applied.

---

## Sign-off

When all items above are verified, Phase 6 is complete and the driver app can be treated as production-ready for tracking and dispatch. Document any exceptions or follow-up (e.g. device-specific issues) in your runbook or tickets.
