"""
Phase 7 API smoke test: jobs near driver (distance filter).
GET /api/jobs?near_lat=...&near_lng=...&min_mi=...&max_mi=...
"""
import json
import urllib.request
import urllib.error

import pytest


def _req(base_url, path):
    url = base_url + path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.getcode(), json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except OSError as e:
        pytest.skip("Server not reachable: {}".format(e))


def test_jobs_near_point(base_url):
    path = "/api/jobs?near_lat=32.78&near_lng=-96.80&min_mi=0&max_mi=500"
    code, body = _req(base_url, path)
    assert code in (200, 503), "GET (near) -> {} {}".format(code, body)
    if code == 503:
        pytest.skip("Supabase not configured")
    jobs = body if isinstance(body, list) else (body.get("jobs", body) if isinstance(body, dict) else [])
    assert isinstance(jobs, list)
