# Testing — GIGATT Geomapper

How to run API and integration tests, and what is (not) covered. Aligned with [plan.md](plan.md) phases.

---

## Quick run

**Prerequisites:** Server running (`python server.py`), Supabase configured (for Phase 3/5/6/7).

```bash
# Run Phase 3 + Phase 5 smoke tests (no auth required)
python scripts/run_api_tests.py

# With custom base URL
python scripts/run_api_tests.py http://127.0.0.1:8080
```

**Optional:** To include Phase 6 (batch idempotency), set `GEOMAPPER_DRIVER_ID`. To run admin API tests, set `GEOMAPPER_ADMIN_JWT` to a Supabase access token for an admin user.

```bash
set GEOMAPPER_DRIVER_ID=<uuid-of-driver-profile>   # Windows
set GEOMAPPER_ADMIN_JWT=<access-token>             # optional, for admin tests
# export GEOMAPPER_DRIVER_ID=...                  # Linux/macOS
python scripts/run_api_tests.py
```

**Pytest (optional):** From the repo root, run `pytest tests/ -v`. Uses the same base URL (env `GEOMAPPER_URL`, default `http://127.0.0.1:8080`). Admin tests run only when `GEOMAPPER_ADMIN_JWT` is set.

Phase 6 is skipped if `GEOMAPPER_DRIVER_ID` is not set; Phase 7 runs without auth.

---

## Test scripts (scripts/)

| Script | What it covers | Auth / env |
|--------|----------------|------------|
| **test_phase3_api.py** | GET/POST /api/jobs, GET job by id, candidate-drivers, GET /api/drivers. Handles 503 when Supabase not configured. | None |
| **test_phase5_api.py** | Ingestion: multipart upload, parse, permit-candidates list/PATCH/approve/reject, create-job. | None (or server-side Supabase) |
| **test_phase6_batch_idempotency.py** | POST same location batch twice; asserts no duplicate rows (idempotency). | `GEOMAPPER_DRIVER_ID` (optional JWT via token) |
| **test_phase7_api.py** | GET /api/jobs with `near_lat`, `near_lng`, `min_mi`, `max_mi` (Phase 7 “jobs near driver” filter). | None |
| **run_api_tests.py** | Runs Phase 3, Phase 5; if `GEOMAPPER_DRIVER_ID` is set, runs Phase 6; always runs Phase 7. | As above |

**One-off / setup:**

- **create_test_users.py** — Seeds Supabase with test users (admin, dispatcher, driver). Not an automated test; run once per environment.

---

## Pytest suite (tests/)

| Module | What it covers |
|--------|----------------|
| **conftest.py** | Fixtures: `base_url` (from `GEOMAPPER_URL`), `admin_jwt` (from `GEOMAPPER_ADMIN_JWT`), `driver_id` (from `GEOMAPPER_DRIVER_ID`). |
| **test_api_phase3.py** | GET/POST /api/jobs, GET job by id, candidate-drivers, GET /api/drivers. Skips when server unreachable or 503. |
| **test_api_phase7.py** | GET /api/jobs?near_lat=...&near_lng=...&min_mi=...&max_mi=... |
| **test_admin_api.py** | GET /api/admin/config without token (expect 401/403); with admin JWT (expect 200). Admin test skipped if `GEOMAPPER_ADMIN_JWT` not set. |

Run: `pytest tests/ -v`. Install pytest: `pip install pytest` (or use project `requirements.txt`).

---

## Coverage gaps

- **Admin API** — Only GET /api/admin/config is covered by pytest. Other admin endpoints (users, state permissions) are manual via dispatch UI.
- **Auth / JWT** — Phase 3/5 do not use JWT. Phase 6 can use `GEOMAPPER_DRIVER_ID` without token if server allows body `driver_id`; for full auth, pass a driver JWT (e.g. from Supabase sign-in).
- **Frontend** — No JS unit or E2E tests. Dispatch and driver portal are tested manually.
- **End-to-end** — No single script that starts server + DB and runs a full flow (login → create job → assign → driver batch). CI could run `run_api_tests.py` or `pytest tests/` against a deployed or local stack. E2E with Playwright (or similar) for login → dispatch → permit approve is a possible next step; see CONTRIBUTING.md.

---

## Adding new tests

- Keep the same pattern: `python scripts/test_phaseN_api.py [BASE_URL]` with exit code 0 = pass.
- For tests that need a driver or JWT, use env vars (e.g. `GEOMAPPER_DRIVER_ID`, `GEOMAPPER_JWT`) and skip gracefully when unset.
- Document the script in this file and, if applicable, add it to `run_api_tests.py`.
