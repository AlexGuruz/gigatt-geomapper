"""
Phase 3 API smoke tests: jobs CRUD, candidate-drivers, drivers.
Requires server running; Supabase required for POST job and full checks.
"""
import json
import urllib.request
import urllib.error

import pytest


def _req(base_url, method, path, body=None, headers=None):
    url = base_url + path
    headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
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


@pytest.mark.parametrize("path", ["/api/jobs", "/api/jobs?status=unassigned"])
def test_get_jobs(base_url, path):
    code, body = _req(base_url, "GET", path)
    assert code in (200, 503), "GET {} -> {} {}".format(path, code, body)
    if code == 503:
        pytest.skip("Supabase not configured")
    assert isinstance(body, list)


def test_post_job_and_candidate_drivers(base_url):
    code, body = _req(
        base_url,
        "POST",
        "/api/jobs",
        {"origin": "Dallas, TX", "destination": "Oklahoma City, OK", "estimated_miles": 200, "estimated_duration": 180},
    )
    if code == 503:
        pytest.skip("Supabase not configured")
    assert code == 200, "POST /api/jobs -> {} {}".format(code, body)
    assert isinstance(body, dict) and body.get("id")
    job_id = body["id"]

    code2, job = _req(base_url, "GET", "/api/jobs/" + job_id)
    assert code2 == 200, "GET /api/jobs/:id -> {} {}".format(code2, job)

    code3, cand = _req(base_url, "GET", "/api/jobs/" + job_id + "/candidate-drivers")
    assert code3 == 200, "GET candidate-drivers -> {} {}".format(code3, cand)
    assert "candidates" in cand


def test_get_drivers(base_url):
    code, body = _req(base_url, "GET", "/api/drivers")
    assert code in (200, 503)
    if code == 503:
        pytest.skip("Supabase not configured")
    assert isinstance(body, list)
