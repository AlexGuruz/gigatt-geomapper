#!/usr/bin/env python
"""
Phase 7 API smoke test: jobs near driver (distance filter).
GET /api/jobs?near_lat=...&near_lng=...&min_mi=...&max_mi=...
Run with: python scripts/test_phase7_api.py [BASE_URL]
Default BASE_URL: http://127.0.0.1:8080
"""
import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BASE = BASE.rstrip("/")

# Dallas area
LAT, LNG = 32.78, -96.80
MIN_MI, MAX_MI = 0, 500


def req(path):
    url = BASE + path
    r = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(r, timeout=10) as res:
            return res.getcode(), json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return None, str(e)


def main():
    print("Phase 7 API smoke test (jobs near driver) — base:", BASE)
    path = "/api/jobs?near_lat={}&near_lng={}&min_mi={}&max_mi={}".format(LAT, LNG, MIN_MI, MAX_MI)
    code, body = req(path)
    if code == 200:
        jobs = body if isinstance(body, list) else body.get("jobs", body) if isinstance(body, dict) else []
        print("[OK] GET /api/jobs?near_lat=...&near_lng=...&min_mi=...&max_mi=... -> 200, list length:", len(jobs))
    elif code == 503:
        print("[SKIP] GET /api/jobs (near) -> 503 (Supabase not configured)")
    else:
        print("[FAIL] GET /api/jobs (near) ->", code, body)
        sys.exit(1)


if __name__ == "__main__":
    main()
