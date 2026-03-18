"""
Admin API smoke test: GET /api/admin/config with admin JWT.
Skip if GEOMAPPER_ADMIN_JWT is not set.
"""
import json
import urllib.request
import urllib.error

import pytest


def _req(base_url, path, token=None):
    url = base_url + path
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers, method="GET")
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


def test_admin_config_requires_auth(base_url):
    """Without token, admin config should return 401 or 403."""
    code, _ = _req(base_url, "/api/admin/config")
    assert code in (401, 403, 404), "Expected 401/403/404 without auth, got {}".format(code)


@pytest.mark.skipif(
    __import__("os").environ.get("GEOMAPPER_ADMIN_JWT") is None,
    reason="Set GEOMAPPER_ADMIN_JWT to run admin API test",
)
def test_admin_config_with_jwt(base_url, admin_jwt):
    """With valid admin JWT, GET /api/admin/config returns 200 and config payload."""
    code, body = _req(base_url, "/api/admin/config", token=admin_jwt)
    assert code == 200, "GET /api/admin/config with JWT -> {} {}".format(code, body)
    assert isinstance(body, dict)
