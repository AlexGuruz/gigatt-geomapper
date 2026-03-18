#!/usr/bin/env python
"""
Phase 3 API smoke test. Run with: python scripts/test_phase3_api.py [BASE_URL]
Default BASE_URL: http://127.0.0.1:8080
Ensure the server is running (python server.py) and Supabase is configured for full tests.
"""
import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BASE = BASE.rstrip("/")


def req(method, path, body=None):
    url = BASE + path
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as res:
            return res.getcode(), json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return None, str(e)


def main():
    print("Phase 3 API smoke test — base:", BASE)
    print()

    # GET /api/jobs
    code, body = req("GET", "/api/jobs")
    if code == 200:
        print("[OK] GET /api/jobs -> 200, list length:", len(body) if isinstance(body, list) else "n/a")
    elif code == 503:
        print("[SKIP] GET /api/jobs -> 503 (Supabase not configured)")
    else:
        print("[FAIL] GET /api/jobs ->", code, body)

    # GET /api/jobs?status=unassigned
    code, body = req("GET", "/api/jobs?status=unassigned")
    if code == 200:
        print("[OK] GET /api/jobs?status=unassigned -> 200")
    elif code == 503:
        print("[SKIP] GET /api/jobs?status=unassigned -> 503")
    else:
        print("[FAIL] GET /api/jobs?status=unassigned ->", code)

    # POST /api/jobs (create) — requires Supabase
    code, body = req("POST", "/api/jobs", {"origin": "Dallas, TX", "destination": "Oklahoma City, OK", "estimated_miles": 200, "estimated_duration": 180})
    if code == 200 and isinstance(body, dict) and body.get("id"):
        job_id = body["id"]
        print("[OK] POST /api/jobs -> 200, job_id:", job_id[:8] + "...")
        # GET /api/jobs/:id
        code2, job = req("GET", "/api/jobs/" + job_id)
        if code2 == 200:
            print("[OK] GET /api/jobs/:id -> 200")
        # GET candidate-drivers
        code3, cand = req("GET", "/api/jobs/" + job_id + "/candidate-drivers")
        if code3 == 200 and "candidates" in cand:
            print("[OK] GET /api/jobs/:id/candidate-drivers -> 200, candidates:", len(cand["candidates"]))
        else:
            print("[FAIL] GET candidate-drivers ->", code3, cand)
    elif code == 503:
        print("[SKIP] POST /api/jobs -> 503 (Supabase not configured)")
    else:
        print("[FAIL] POST /api/jobs ->", code, body)

    # GET /api/drivers (should include assigned_job when applicable)
    code, body = req("GET", "/api/drivers")
    if code == 200:
        print("[OK] GET /api/drivers -> 200, drivers:", len(body) if isinstance(body, list) else "n/a")
    elif code == 503:
        print("[SKIP] GET /api/drivers -> 503")
    else:
        print("[FAIL] GET /api/drivers ->", code)

    print()
    print("Done. Fix any [FAIL]; [SKIP] is expected if Supabase is not set up.")


if __name__ == "__main__":
    main()
