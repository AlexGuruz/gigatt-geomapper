# Phase 1 Setup Guide

**Purpose:** Enable Supabase auth and the driver-locations batch API. Aligned with **plan.md** Section 11 (Phase 1 — Foundation).

**Last updated:** 2026-03-14

---

## 1. Create Supabase project

1. Go to [supabase.com](https://supabase.com) and create a project.
2. In **Project Settings → API**, copy:
   - **Project URL** (e.g. `https://YOUR_PROJECT_REF.supabase.co`)
   - **anon public** key (for client-side auth and `/api/config`)
   - **service_role** key (for backend APIs only — never expose in client; store in `.env` only)

## 2. Run migration

1. Open Supabase SQL Editor.
2. Run the contents of `supabase/migrations/001_initial.sql`.

## 3. Configure environment

Copy `.env.example` to `.env` and set:

```
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
```

Or add to `config.json`:

```json
{
  "supabase_url": "https://YOUR_PROJECT.supabase.co",
  "supabase_anon_key": "YOUR_ANON_KEY"
}
```

The service key must be in `.env` only (not config.json) for security.

## 4. Install Python deps (optional)

```bash
pip install -r requirements.txt
```

If using the bundled Python, ensure `supabase` and `python-dotenv` are available.

## 5. Create test users

**Option A — Run script (recommended):**

```bash
# Ensure .env has SUPABASE_URL, SUPABASE_SERVICE_KEY
python scripts/create_test_users.py
```

Creates:
- `dispatcher@test.gigatt.com` / `Test123!@#` (role: dispatcher)
- `driver@test.gigatt.com` / `Test123!@#` (role: driver, driver_profiles row)

**Option B — Manual:**
1. In Supabase Auth → Users, create a user (email + password).
2. In Table Editor → `profiles`, set `role` to `dispatcher` or `driver`.
3. For drivers: create a row in `driver_profiles` with `user_id` = auth user id.

## 6. Verify

- Open [http://127.0.0.1:8080](http://127.0.0.1:8080) → should redirect to `/login.html` if Supabase is configured.
- Sign in with a dispatcher → lands on map.
- Sign in with a driver → lands on `/driver.html`.
- `POST /api/driver-locations/batch` with valid `driver_id` and `events[]` when Supabase is configured.

For full Phase 1 acceptance criteria and next phases (dispatcher right sidebar, assignments, driver app), see **plan.md** Section 11.

