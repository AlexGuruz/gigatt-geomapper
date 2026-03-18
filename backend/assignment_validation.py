"""
Assignment validation: driver_id + job_id -> allowed, reasons.
Plan 10.13.3: check driver status, availability, state permissions; return 409/422 with blocked states.
"""
from datetime import date, datetime, time as dt_time


def _get_job_route_states(client, job_id):
    """Return set of state_code (2-letter) for the job."""
    if not client or not job_id:
        return set()
    try:
        r = client.table("job_route_states").select("state_code").eq("job_id", job_id).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return {str(row.get("state_code", "")).strip().upper() for row in rows if row.get("state_code")}
    except Exception:
        return set()


def _get_driver_allowed_states(client, driver_id):
    """Return set of state_code where driver has allowed=True."""
    if not client or not driver_id:
        return set()
    try:
        r = client.table("driver_state_permissions").select("state_code, allowed").eq("driver_id", driver_id).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return {str(row["state_code"]).strip().upper() for row in rows if row.get("allowed") is True}
    except Exception:
        return set()


def _get_driver_profile(client, driver_id):
    """Return driver profile dict or None."""
    if not client or not driver_id:
        return None
    try:
        r = client.table("driver_profiles").select("id, status").eq("id", driver_id).limit(1).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_job(client, job_id):
    """Return job dict or None."""
    if not client or not job_id:
        return None
    try:
        r = client.table("jobs").select("id, assigned_driver_id, status").eq("id", job_id).limit(1).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return rows[0] if rows else None
    except Exception:
        return None


def validate_assignment(client, driver_id, job_id):
    """
    Returns dict: { "allowed": bool, "reasons": [ {"code": str, "message": str}, ... ] }.
    Plan 10.13: driver status, availability, state permissions. Backend rejects with 409/422.
    """
    reasons = []
    job = _get_job(client, job_id)
    if not job:
        return {"allowed": False, "reasons": [{"code": "JOB_NOT_FOUND", "message": "Job not found."}]}
    driver = _get_driver_profile(client, driver_id)
    if not driver:
        return {"allowed": False, "reasons": [{"code": "DRIVER_NOT_FOUND", "message": "Driver not found."}]}

    # Already assigned to another driver
    current = job.get("assigned_driver_id")
    if current and str(current) != str(driver_id):
        reasons.append({"code": "JOB_ALREADY_ASSIGNED", "message": "Job is already assigned to another driver."})

    # Driver status: must be available or off_duty to accept (per plan: available for assignment)
    status = (driver.get("status") or "").strip().lower()
    if status in ("assigned", "en_route", "active"):
        reasons.append({"code": "DRIVER_ALREADY_ASSIGNED", "message": "Driver is already on an assignment."})

    # State permissions: every job route state must be in driver's allowed list
    job_states = _get_job_route_states(client, job_id)
    if job_states:
        allowed_states = _get_driver_allowed_states(client, driver_id)
        # Allowlist: driver may work only in states explicitly allowed. If no permissions row, treat as no states allowed.
        blocked = job_states - allowed_states
        if blocked:
            for st in sorted(blocked):
                reasons.append({"code": "STATE_RESTRICTED", "message": "Driver is not eligible for " + st + "."})

    allowed = len(reasons) == 0
    return {"allowed": allowed, "reasons": reasons}
