"""
Idempotent batch insert of driver location events.
Plan Section 8.1–8.2: event_id dedup, location_history + driver_last_location.
"""
from datetime import datetime


def batch_location_events(client, driver_id, events):
    """
    Insert location events idempotently.
    events: list of {event_id, lat, lng, timestamp, speed?, heading?}
    Returns (accepted_count, errors).
    """
    if not client or not events:
        return 0, []
    accepted = 0
    errors = []
    latest_ts = None
    latest_lat = None
    latest_lng = None
    latest_heading = None
    latest_speed = None
    for ev in events:
        eid = ev.get("event_id")
        lat = ev.get("lat")
        lng = ev.get("lng")
        ts = ev.get("timestamp")
        if not eid or lat is None or lng is None or not ts:
            errors.append({"event_id": eid or "?", "reason": "missing required field"})
            continue
        try:
            ts_val = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
        except Exception:
            errors.append({"event_id": eid, "reason": "invalid timestamp"})
            continue
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            errors.append({"event_id": eid, "reason": "invalid lat/lng"})
            continue
        row = {
            "driver_id": driver_id,
            "event_id": str(eid),
            "lat": float(lat),
            "lng": float(lng),
            "timestamp": ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts),
            "speed": ev.get("speed"),
            "heading": ev.get("heading"),
        }
        try:
            client.table("location_history").insert(row).execute()
        except Exception as e:
            err_msg = str(e)
            if "duplicate" in err_msg.lower() or "unique" in err_msg.lower():
                accepted += 1
                if latest_ts is None or (ts_val and latest_ts and ts_val > latest_ts):
                    latest_ts = ts_val
                    latest_lat = lat
                    latest_lng = lng
                    latest_heading = ev.get("heading")
                    latest_speed = ev.get("speed")
            else:
                errors.append({"event_id": eid, "reason": err_msg[:80]})
            continue
        accepted += 1
        if latest_ts is None or (ts_val and latest_ts and ts_val > latest_ts):
            latest_ts = ts_val
            latest_lat = lat
            latest_lng = lng
            latest_heading = ev.get("heading")
            latest_speed = ev.get("speed")
    if accepted > 0 and latest_ts and latest_lat is not None and latest_lng is not None:
        try:
            client.table("driver_last_location").upsert(
                {
                    "driver_id": driver_id,
                    "lat": latest_lat,
                    "lng": latest_lng,
                    "timestamp": latest_ts.isoformat() if hasattr(latest_ts, "isoformat") else str(latest_ts),
                    "heading": latest_heading,
                    "speed": latest_speed,
                },
                on_conflict="driver_id",
            ).execute()
            from datetime import timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            client.table("driver_profiles").update(
                {"last_seen_at": latest_ts.isoformat(), "last_location_at": latest_ts.isoformat(), "updated_at": now_iso}
            ).eq("id", driver_id).execute()
        except Exception as e:
            errors.append({"reason": "failed to update last_location: " + str(e)[:60]})
    return accepted, errors
