"""
Admin API logic: users (profiles), driver state permissions, dispatch config.
Plan Section 2.3: admin v1 — create/invite/deactivate users, assign roles, driver-state permissions, config.
"""
from datetime import datetime, timezone


def __utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Users (profiles)
def list_users(client):
    """List all profiles: id, email, role, active, created_at."""
    if not client:
        return []
    try:
        r = client.table("profiles").select("id, email, role, active, created_at, updated_at").order("created_at", desc=True).execute()
        return (r.data or []) if hasattr(r, "data") else []
    except Exception:
        return []


def get_user(client, user_id):
    """Get one profile by id."""
    if not client or not user_id:
        return None
    try:
        r = client.table("profiles").select("id, email, role, active, created_at, updated_at").eq("id", user_id).limit(1).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return rows[0] if rows else None
    except Exception:
        return None


def update_user(client, user_id, payload):
    """Update profile: role, active. Returns updated row or None."""
    if not client or not user_id:
        return None
    data = {"updated_at": __utc_now()}
    if "role" in payload and payload["role"] in ("driver", "dispatcher", "admin"):
        data["role"] = payload["role"]
    if "active" in payload:
        data["active"] = bool(payload["active"])
    if len(data) <= 1:
        return get_user(client, user_id)
    try:
        r = client.table("profiles").update(data).eq("id", user_id).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return rows[0] if rows else get_user(client, user_id)
    except Exception:
        return None


# Driver state permissions
def list_driver_state_permissions(client, driver_id):
    """List state permissions for a driver: [{ state_code, allowed }, ...]."""
    if not client or not driver_id:
        return []
    try:
        r = client.table("driver_state_permissions").select("id, state_code, allowed, source, updated_at").eq("driver_id", driver_id).execute()
        return (r.data or []) if hasattr(r, "data") else []
    except Exception:
        return []


def set_driver_state_permissions(client, driver_id, permissions):
    """
    permissions: list of { state_code: str (2-letter), allowed: bool }.
    Upserts so that driver has exactly these state rows (replace existing for this driver).
    """
    if not client or not driver_id:
        return []
    if not isinstance(permissions, list):
        return list_driver_state_permissions(client, driver_id)
    # Delete existing and insert new (simple replace)
    try:
        client.table("driver_state_permissions").delete().eq("driver_id", driver_id).execute()
    except Exception:
        pass
    out = []
    for p in permissions:
        sc = (p.get("state_code") or "").strip().upper()[:2]
        if not sc:
            continue
        allowed = bool(p.get("allowed", True))
        try:
            r = client.table("driver_state_permissions").insert({
                "driver_id": driver_id,
                "state_code": sc,
                "allowed": allowed,
                "source": "manual_admin",
            }).execute()
            rows = (r.data or []) if hasattr(r, "data") else []
            if rows:
                out.append(rows[0])
        except Exception:
            pass
    return out if out else list_driver_state_permissions(client, driver_id)


# Dispatch config
def get_dispatch_config(client):
    """Return all dispatch_config as { key: value } (value is parsed jsonb)."""
    if not client:
        return {}
    try:
        r = client.table("dispatch_config").select("key, value").execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        return {row["key"]: row.get("value") for row in rows}
    except Exception:
        return {}


def update_dispatch_config(client, key, value):
    """Set one dispatch_config key. value can be str, number, or dict/list (stored as jsonb). Returns updated config."""
    if not client or not key or not isinstance(key, str):
        return get_dispatch_config(client)
    try:
        client.table("dispatch_config").upsert({"key": key, "value": value}, on_conflict="key").execute()
        return get_dispatch_config(client)
    except Exception:
        return get_dispatch_config(client)
