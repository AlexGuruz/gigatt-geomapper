"""
Jobs API: list, get, assign driver, update status. Plan Phase 3.
Compute projected_completion, projected_available_at, projected_available_location (end-of-day rule).
Phase 7: list_jobs filter by distance from point (near_lat/lng or near_driver_id, min_mi, max_mi).
"""
from datetime import datetime, timedelta, date, time as dt_time
import json
import math


def haversine_mi(lat1, lng1, lat2, lng2):
    """Distance in miles between two WGS84 points."""
    try:
        lat1, lng1, lat2, lng2 = float(lat1), float(lng1), float(lat2), float(lng2)
    except (TypeError, ValueError):
        return None
    R = 3958.8  # Earth radius miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _get_dispatch_config(client):
    """Return dispatch_config as dict key -> value (parsed jsonb)."""
    if not client:
        return {}
    try:
        r = client.table("dispatch_config").select("key, value").execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return {row["key"]: (row["value"] if isinstance(row["value"], (int, float, str, list, dict)) else json.loads(json.dumps(row["value"]))) for row in rows}
    except Exception:
        return {}


def _parse_time(s):
    """Parse '16:00' or '08:00' -> (hour, minute)."""
    if not s:
        return None
    if isinstance(s, str) and ":" in s:
        parts = s.strip().split(":")
        if len(parts) >= 2:
            try:
                return int(parts[0], 10), int(parts[1], 10)
            except ValueError:
                pass
    return None


def _projected_available_at(completion_ts, config):
    """Apply end-of-day rule: if completion after cutoff, next day start + buffer."""
    if not completion_ts:
        return None
    cutoff = _parse_time(config.get("dispatch_day_cutoff_time") or "16:00")
    next_start = _parse_time(config.get("dispatch_next_day_start_time") or "08:00")
    buffer_min = int(config.get("availability_buffer_minutes") or 15)
    if not cutoff or not next_start:
        return completion_ts + timedelta(minutes=buffer_min)
    comp = datetime.utcfromtimestamp(completion_ts.timestamp()) if hasattr(completion_ts, "timestamp") else completion_ts
    cutoff_dt = comp.replace(hour=cutoff[0], minute=cutoff[1], second=0, microsecond=0)
    if comp >= cutoff_dt:
        next_day = (comp.date() if hasattr(comp, "date") else comp) + timedelta(days=1)
        start_dt = datetime.combine(next_day, dt_time(next_start[0], next_start[1], 0))
        return start_dt + timedelta(minutes=buffer_min)
    return completion_ts + timedelta(minutes=buffer_min)


def _resolve_driver_next_location(client, driver_id):
    """Get (lat, lng) for driver's projected_available_location if available. Returns (lat, lng) or (None, None)."""
    if not client or not driver_id:
        return None, None
    try:
        r = client.table("driver_profiles").select("id").eq("id", driver_id).limit(1).execute()
        if not (r.data and r.data[0]):
            return None, None
        # Get driver's assigned job for projected_available_location
        jr = client.table("jobs").select("projected_available_location").eq("assigned_driver_id", driver_id).eq("status", "assigned").limit(1).execute()
        if not (jr.data and jr.data[0]):
            return None, None
        loc = jr.data[0].get("projected_available_location") or {}
        lat, lng = loc.get("lat"), loc.get("lng")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
        return None, None
    except Exception:
        return None, None


def list_jobs(client, status=None, near_lat=None, near_lng=None, min_mi=None, max_mi=None, near_driver_id=None):
    """
    List jobs, optionally filter by status and by distance from a point.
    Point: (near_lat, near_lng) or resolved from near_driver_id (driver's projected_available_location lat/lng).
    min_mi, max_mi: include jobs whose origin (origin_lat, origin_lng) is within [min_mi, max_mi] from the point.
    Jobs without origin_lat/lng are excluded when distance filter is applied.
    """
    if not client:
        return []
    try:
        sel = (
            "id, permit_id, permit_candidate_id, origin, destination, route_text, estimated_miles, estimated_duration, "
            "origin_lat, origin_lng, escort_requirements, assigned_driver_id, status, scheduled_start, projected_completion, "
            "projected_available_at, projected_available_location, created_at, updated_at"
        )
        q = client.table("jobs").select(sel).order("created_at", desc=True)
        if status:
            q = q.eq("status", status)
        r = q.execute()
        rows = (r.data or []) if hasattr(r, "data") else []
    except Exception:
        try:
            sel_base = (
                "id, permit_id, permit_candidate_id, origin, destination, route_text, estimated_miles, estimated_duration, "
                "escort_requirements, assigned_driver_id, status, scheduled_start, projected_completion, "
                "projected_available_at, projected_available_location, created_at, updated_at"
            )
            q = client.table("jobs").select(sel_base).order("created_at", desc=True)
            if status:
                q = q.eq("status", status)
            r = q.execute()
            rows = (r.data or []) if hasattr(r, "data") else []
            for row in rows:
                row.setdefault("origin_lat", None)
                row.setdefault("origin_lng", None)
        except Exception:
            rows = []
    # Resolve point for distance filter
    lat, lng = near_lat, near_lng
    if (lat is None or lng is None) and near_driver_id:
        lat, lng = _resolve_driver_next_location(client, near_driver_id)
    if lat is None or lng is None:
        if min_mi is not None or max_mi is not None:
            return []
        return rows
    try:
        min_mi = float(min_mi) if min_mi is not None else 150.0
        max_mi = float(max_mi) if max_mi is not None else 300.0
    except (TypeError, ValueError):
        return rows
    out = []
    for job in rows:
        olat, olng = job.get("origin_lat"), job.get("origin_lng")
        if olat is None or olng is None:
            continue
        d = haversine_mi(lat, lng, olat, olng)
        if d is None:
            continue
        if min_mi <= d <= max_mi:
            job["distance_mi"] = round(d, 1)
            out.append(job)
    return out


def create_job(client, payload):
    """Create a job from payload (origin, destination, estimated_miles, estimated_duration, origin_lat, origin_lng, etc.). Populates job_route_states."""
    if not client:
        return None
    from backend.route_states import ensure_job_route_states
    data = {
        "origin": (payload.get("origin") or "").strip() or None,
        "destination": (payload.get("destination") or "").strip() or None,
        "route_text": payload.get("route_text"),
        "estimated_miles": payload.get("estimated_miles"),
        "estimated_duration": payload.get("estimated_duration"),
        "escort_requirements": payload.get("escort_requirements"),
        "status": "unassigned",
        "origin_lat": payload.get("origin_lat"),
        "origin_lng": payload.get("origin_lng"),
    }
    data = {k: v for k, v in data.items() if v is not None}
    try:
        r = client.table("jobs").insert(data).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        job = rows[0] if rows else None
        if job and (job.get("origin") or job.get("destination")):
            ensure_job_route_states(client, job["id"], job.get("origin"), job.get("destination"))
        return job
    except Exception:
        return None


def get_job(client, job_id):
    """Get single job by id. Returns dict or None. Ensures job_route_states populated from origin/destination."""
    if not client or not job_id:
        return None
    try:
        r = client.table("jobs").select(
            "id, permit_id, permit_candidate_id, origin, destination, route_text, estimated_miles, estimated_duration, "
            "origin_lat, origin_lng, escort_requirements, assigned_driver_id, status, scheduled_start, projected_completion, "
            "projected_available_at, projected_available_location, created_at, updated_at"
        ).eq("id", job_id).limit(1).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        job = rows[0] if rows else None
        if job and (job.get("origin") or job.get("destination")):
            from backend.route_states import ensure_job_route_states
            ensure_job_route_states(client, job_id, job.get("origin"), job.get("destination"))
        return job
    except Exception:
        return None


def assign_driver(client, job_id, driver_id):
    """
    Assign driver to job. Validates via assignment_validation; updates job and driver status;
    computes projected_completion, projected_available_at, projected_available_location.
    Returns (job_dict, None) on success or (None, error_dict) on validation failure.
    """
    from backend.assignment_validation import validate_assignment
    from backend.route_states import ensure_job_route_states

    if not client:
        return None, {"error": "Backend not configured"}
    job = get_job(client, job_id)
    if not job:
        return None, {"error": "Job not found", "code": "JOB_NOT_FOUND"}
    validation = validate_assignment(client, driver_id, job_id)
    if not validation.get("allowed"):
        return None, {"error": "Assignment not allowed", "reasons": validation.get("reasons", []), "code": "VALIDATION_FAILED"}

    config = _get_dispatch_config(client)
    now = datetime.utcnow()
    duration_min = job.get("estimated_duration") or 60
    projected_completion = now + timedelta(minutes=int(duration_min))
    projected_available_at = _projected_available_at(projected_completion, config)
    # projected_available_location: use job destination as place text (no lat/lng in jobs table for v1)
    dest = job.get("destination") or ""
    projected_available_location = {"address": dest} if dest else None

    try:
        client.table("jobs").update({
            "assigned_driver_id": driver_id,
            "status": "assigned",
            "projected_completion": projected_completion.isoformat(),
            "projected_available_at": projected_available_at.isoformat() if projected_available_at else None,
            "projected_available_location": projected_available_location,
            "updated_at": now.isoformat(),
        }).eq("id", job_id).execute()
        client.table("driver_profiles").update({
            "status": "assigned",
            "last_status_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }).eq("id", driver_id).execute()
    except Exception as e:
        return None, {"error": str(e), "code": "UPDATE_FAILED"}

    return get_job(client, job_id), None


def update_job_status(client, job_id, status):
    """Update job status. status in (unassigned, assigned, active, completed, cancelled)."""
    if not client or not job_id:
        return None
    try:
        now = datetime.utcnow()
        client.table("jobs").update({"status": status, "updated_at": now.isoformat()}).eq("id", job_id).execute()
        return get_job(client, job_id)
    except Exception:
        return None


def update_job(client, job_id, payload):
    """Update job with allowed fields: status, origin_lat, origin_lng."""
    if not client or not job_id or not payload:
        return None
    allowed = {"status", "origin_lat", "origin_lng"}
    data = {k: v for k, v in payload.items() if k in allowed}
    if not data:
        return get_job(client, job_id)
    data["updated_at"] = datetime.utcnow().isoformat()
    try:
        client.table("jobs").update(data).eq("id", job_id).execute()
        return get_job(client, job_id)
    except Exception:
        return None
