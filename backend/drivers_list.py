"""
Return driver list for dispatcher: driver_profiles + last location + profile email + assigned job.
Plan Phase 2 + Phase 3: GET drivers with last_seen_at, status, position, assigned_job (origin, destination, ETA, etc.).
"""
def get_drivers(client):
    """
    Fetch all driver_profiles with last location, profile email, and assigned job if any.
    client: Supabase client (service role).
    Returns list of dicts: id, user_id, name, email, status, last_seen_at, last_location_at, lat, lng, timestamp, assigned_job.
    """
    if not client:
        return []
    try:
        r = client.table("driver_profiles").select(
            "id, user_id, name, phone, status, last_seen_at, last_location_at, last_status_at, "
            "driver_last_location(lat, lng, timestamp)"
        ).execute()
    except Exception:
        return []
    rows = (r.data or []) if hasattr(r, "data") else []
    driver_ids = [str(d.get("id")) for d in rows if d.get("id")]
    # Assigned jobs: one job per driver where assigned_driver_id in driver_ids and status in ('assigned','active')
    jobs_by_driver = {}
    if driver_ids:
        try:
            jr = client.table("jobs").select(
                "id, origin, destination, route_text, estimated_miles, estimated_duration, "
                "assigned_driver_id, status, projected_completion, projected_available_at, projected_available_location"
            ).in_("assigned_driver_id", driver_ids).in_("status", ["assigned", "active"]).execute()
            job_rows = (jr.data or []) if hasattr(jr, "data") else []
            for j in job_rows:
                did = j.get("assigned_driver_id")
                if did:
                    jobs_by_driver[str(did)] = j
        except Exception:
            pass
    # Resolve profile email: batch by user_id
    user_ids = list({str(d.get("user_id")) for d in rows if d.get("user_id")})
    emails = {}
    if user_ids:
        try:
            pr = client.table("profiles").select("id, email").in_("id", user_ids).execute()
            for p in (pr.data or []):
                emails[str(p.get("id"))] = p.get("email") or ""
        except Exception:
            pass
    out = []
    for d in rows:
        loc = d.get("driver_last_location")
        if isinstance(loc, list):
            ll = loc[0] if loc else {}
        elif isinstance(loc, dict):
            ll = loc
        else:
            ll = {}
        did = str(d.get("id"))
        out.append({
            "id": did,
            "user_id": str(d.get("user_id")) if d.get("user_id") else None,
            "name": d.get("name") or "",
            "email": emails.get(str(d.get("user_id")), ""),
            "phone": d.get("phone") or "",
            "status": d.get("status") or "off_duty",
            "last_seen_at": d.get("last_seen_at"),
            "last_location_at": d.get("last_location_at"),
            "lat": ll.get("lat"),
            "lng": ll.get("lng"),
            "timestamp": ll.get("timestamp"),
            "assigned_job": jobs_by_driver.get(did),
        })
    return out
