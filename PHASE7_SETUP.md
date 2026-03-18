# Phase 7 — Next-route matching (jobs near driver)

Plan Phase 7: filter unassigned jobs by distance from a driver's next available location and show them in Geomapper.

## Backend

- **Migration**: Run `supabase/migrations/003_jobs_origin_coords.sql` to add `origin_lat`, `origin_lng` to `jobs`.
- **GET /api/jobs** query params:
  - `near_lat`, `near_lng` — center point (e.g. driver's next location).
  - `min_mi`, `max_mi` — distance range in miles (default 150–300 when point is set).
  - `near_driver_id` — alternative: backend resolves driver's assigned job `projected_available_location.lat/lng` (when stored).
- Only jobs with `origin_lat` and `origin_lng` set are included when distance filter is used. Set them via **PATCH /api/jobs/:id** with `{"origin_lat": 34.0, "origin_lng": -96.0}` (e.g. after geocoding job origin in the UI).

## Geomapper UI

- **"Jobs near driver's next location"** section in the right sidebar:
  - Select a driver, set Min mi / Max mi (default 150–300), click **Show**.
  - Next location is taken from the driver's assigned job `projected_available_location` (lat/lng or geocoded address) or the driver's current lat/lng.
  - Listed jobs show distance from that point; **Assign driver** opens the existing assign modal.

## Acceptance

- Jobs are filterable by distance from a point (or from a driver's next location when lat/lng are stored).
- "Jobs near Driver X's next location" is available in the right sidebar with driver select and distance range.
