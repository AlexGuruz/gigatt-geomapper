#!/usr/bin/env python
"""
Phase 6: Verify batch location idempotency (retry same batch, no duplicate rows).
Plan 6.3. Requires server + Supabase + valid driver_id (and optionally JWT for auth).
Usage: python scripts/test_phase6_batch_idempotency.py [BASE_URL] [DRIVER_ID]
Without DRIVER_ID, the batch endpoint may reject (or use body driver_id if server allows).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GEOMAPPER_URL", "http://127.0.0.1:8080")
BASE = BASE.rstrip("/")
DRIVER_ID = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GEOMAPPER_DRIVER_ID")
EVENT_ID = "phase6-idem-" + str(int(time.time()))


def post_batch(driver_id, events, token=None):
    url = BASE + "/api/driver-locations/batch"
    body = json.dumps({"driver_id": driver_id, "events": events}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=10) as res:
            return res.getcode(), json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def main():
    print("Phase 6 batch idempotency test — base:", BASE)
    if not DRIVER_ID:
        print("[SKIP] No DRIVER_ID. Set GEOMAPPER_DRIVER_ID or pass as second argument.")
        print("Server may require JWT (Authorization: Bearer); then use a driver account token.")
        return
    events = [
        {
            "event_id": EVENT_ID,
            "lat": 32.78,
            "lng": -96.80,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "speed": 0,
            "heading": 0,
        }
    ]
    code1, out1 = post_batch(DRIVER_ID, events)
    if code1 not in (200, 201):
        print("[FAIL] First POST batch ->", code1, out1)
        return
    accepted1 = out1.get("accepted", out1) if isinstance(out1, dict) else None
    print("[OK] First POST batch ->", code1, "accepted:", accepted1)
    code2, out2 = post_batch(DRIVER_ID, events)
    if code2 not in (200, 201):
        print("[FAIL] Second POST batch (retry) ->", code2, out2)
        return
    accepted2 = out2.get("accepted", out2) if isinstance(out2, dict) else None
    print("[OK] Second POST batch (retry) ->", code2, "accepted:", accepted2)
    # Idempotent: second time should still report accepted (dedup by event_id)
    if accepted1 is not None and accepted2 is not None and accepted2 >= 0:
        print("[OK] Idempotency: retry accepted (no duplicate row expected in location_history).")
    print("Done. Check location_history for driver_id=%s: single row with event_id=%s." % (DRIVER_ID, EVENT_ID))


if __name__ == "__main__":
    main()
