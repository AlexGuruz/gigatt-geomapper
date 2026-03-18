# Contributing to GIGATT Geomapper

Thanks for contributing. This project follows the build plan in **plan.md** and keeps behavior aligned with **BASELINE.md** for Phase 0.

---

## Branch naming

- `feature/<short-name>` — new feature (e.g. `feature/availability-calendar`)
- `fix/<short-name>` — bugfix (e.g. `fix/batch-idempotency`)
- `docs/<short-name>` — documentation only

---

## Before submitting a PR

1. **Run the test suite**
   - Start the server: `python server.py`
   - Run API smoke tests: `python scripts/run_api_tests.py`
   - Optional: run pytest from repo root: `pytest tests/ -v`
   - If you have Supabase configured and an admin JWT: set `GEOMAPPER_ADMIN_JWT` and re-run so admin tests run.

2. **Don’t break Phase 0**
   - See [BASELINE.md](BASELINE.md). Changes to map, sidebar, `/api/routes`, or poller should not break existing behavior without a plan update.

3. **Documentation**
   - New env vars → add to [ENV_VARS.md](ENV_VARS.md).
   - New setup steps → add to the right PHASE* or [DEPLOY.md](DEPLOY.md), and link from [README](README.md) doc index if user-facing.

---

## Adding new tests

- **API (backend):** Add a script under `scripts/` (e.g. `test_phaseN_api.py`) and, if useful, a corresponding pytest module under `tests/` that uses the `base_url` fixture from `conftest.py`. Document the script in [TESTING.md](TESTING.md) and optionally add it to `run_api_tests.py`.
- **Admin API:** Use the `admin_jwt` fixture; skip when `GEOMAPPER_ADMIN_JWT` is not set (see `tests/test_admin_api.py`).
- **E2E:** Not required yet. If you add Playwright (or similar), document in TESTING.md and CONTRIBUTING.md.

---

## Where to look

| Area | Location |
|------|----------|
| Backend API | `server.py`, `backend/*.py` |
| Frontend (dispatch) | `web/index.html`, `web/js/app.js`, `web/css/style.css` |
| Driver portal | `web/driver.html`, `web/js/driver-portal.js` |
| Auth / config | `web/js/auth.js`, `web/js/config.js` |
| Plan & phases | [plan.md](plan.md) |
| Test docs | [TESTING.md](TESTING.md) |
