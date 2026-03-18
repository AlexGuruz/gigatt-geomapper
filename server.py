"""
PilotCar Loads Map - Local HTTP server.
Serves web/ static files and API: GET /api/routes, GET /api/drivers, GET /api/config, PATCH /api/routes/:id, POST /api/poll
Phase 1: + POST /api/driver-locations/batch (idempotent, requires Supabase)
"""
import json
import os
import re
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Optional Supabase backend for dispatch layer
try:
    from backend.supabase_client import get_client, is_configured
except ImportError:
    get_client = None
    is_configured = lambda: False


def _parse_multipart(body_bytes, content_type):
    """
    Parse multipart/form-data body. Returns dict: name -> str value, or name -> (filename, bytes, mime).
    Works without cgi (Python 3.13+).
    """
    out = {}
    if not content_type or "multipart/form-data" not in (content_type if isinstance(content_type, str) else content_type.decode("utf-8", errors="replace")):
        return out
    # Get boundary
    for part in (content_type.split(";") if isinstance(content_type, str) else content_type.decode("utf-8").split(";")):
        part = part.strip()
        if part.lower().startswith("boundary="):
            boundary = part[9:].strip().strip('"').encode("ascii")
            break
    else:
        return out
    if not body_bytes or isinstance(body_bytes, str):
        body_bytes = body_bytes.encode("utf-8") if body_bytes else b""
    parts = body_bytes.split(b"--" + boundary)
    for raw in parts:
        raw = raw.strip()
        if not raw or raw == b"--":
            continue
        head, _, rest = raw.partition(b"\r\n\r\n")
        if not rest:
            continue
        name = None
        filename = None
        mime = b"application/octet-stream"
        for line in head.split(b"\r\n"):
            line = line.strip()
            if line.lower().startswith(b"content-disposition:"):
                val = line.split(b":", 1)[1].strip().decode("utf-8", errors="replace")
                for tok in val.split(";"):
                    tok = tok.strip()
                    if tok.lower().startswith("name="):
                        name = tok[5:].strip('"')
                    elif tok.lower().startswith("filename="):
                        filename = tok[9:].strip('"')
            elif line.lower().startswith(b"content-type:"):
                mime = line.split(b":", 1)[1].strip()
        if name is None:
            continue
        content = rest.rstrip(b"\r\n")
        if filename is not None:
            out[name] = (filename, content, mime.decode("utf-8", errors="replace") if isinstance(mime, bytes) else mime)
        else:
            out[name] = content.decode("utf-8", errors="replace")
    return out


def _is_connection_aborted(exc):
    """True if the client closed the connection (timeout, refresh, etc.)."""
    if exc is None:
        return False
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 10053:
        return True
    return False

ROOT = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
LOG_PATH = os.path.join(DATA_DIR, "server_log.txt")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Load baked-in secrets (Guru Config, Supabase Pass) before config
try:
    from backend.secrets_loader import load_into_env
    load_into_env()
except ImportError:
    pass


def log(msg):
    """Append a timestamped line to data/server_log.txt (creates data dir if needed)."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime()) + str(msg) + "\n")
            f.flush()
    except Exception:
        pass


log("server.py loaded, ROOT=%s" % ROOT)

try:
    import poller as poller_module
    log("poller imported OK")
except Exception as e:
    log("poller import failed: %s" % e)
    raise

# Optional Supabase (Phase 1)
_supabase_client = None
def _get_supabase():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    try:
        from backend.supabase_client import get_client, is_configured
        if is_configured():
            _supabase_client = get_client()
    except Exception as e:
        log("Supabase init skipped: %s" % e)
    return _supabase_client
WEB_DIR = os.path.join(ROOT, "web")
CONFIG_PATH = os.path.join(ROOT, "config.json")
ROUTES_PATH = os.path.join(DATA_DIR, "routes.json")
DRIVERS_PATH = os.path.join(DATA_DIR, "drivers.json")
PORT = int(os.environ.get("PORT", "8080"))
POLL_THROTTLE_SEC = 15
last_poll_time = None
_last_poll_stats = {}
_poll_lock = threading.Lock()


def load_json(path, default):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_config():
    raw = load_json(CONFIG_PATH, {})
    # Resolve API key from file path if set
    key_path = raw.get("google_api_key_path")
    if key_path and os.path.isfile(key_path):
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                raw = dict(raw)
                raw["google_api_key"] = f.read().strip()
        except IOError:
            pass
    # Supabase (env overrides config) — anon key for frontend auth
    if os.environ.get("SUPABASE_URL"):
        raw = dict(raw)
        raw["supabaseUrl"] = os.environ.get("SUPABASE_URL", "").strip()
    if os.environ.get("SUPABASE_ANON_KEY"):
        raw = dict(raw)
        raw["supabaseAnonKey"] = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not raw.get("supabaseUrl") and raw.get("supabase_url"):
        raw = dict(raw)
        raw["supabaseUrl"] = raw["supabase_url"]
    if not raw.get("supabaseAnonKey") and raw.get("supabase_anon_key"):
        raw = dict(raw)
        raw["supabaseAnonKey"] = raw["supabase_anon_key"]
    if os.environ.get("BACKEND_PUBLIC_URL"):
        raw = dict(raw)
        raw["api_base"] = os.environ.get("BACKEND_PUBLIC_URL", "").strip().rstrip("/")
    if raw.get("backend_public_url") and not raw.get("api_base"):
        raw = dict(raw)
        raw["api_base"] = str(raw["backend_public_url"]).strip().rstrip("/")
    return raw


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        msg = format % args
        print("[%s] %s" % (self.log_date_time_string(), msg))
        log("request %s" % msg)

    def handle(self):
        try:
            BaseHTTPRequestHandler.handle(self)
        except Exception as e:
            if _is_connection_aborted(e):
                log("client disconnected (timeout or refresh)")
            else:
                log("request error: %s" % e)
                try:
                    self.send_error(500, str(e))
                except Exception:
                    pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _get_bearer_token(self):
        auth = self.headers.get("Authorization") or ""
        if isinstance(auth, bytes):
            auth = auth.decode("utf-8", errors="replace")
        auth = auth.strip()
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return auth or None

    def _require_admin(self):
        """Verify Bearer token and admin role. Returns (user_id, role) or None (and sends 401/403)."""
        supabase = _get_supabase()
        if not supabase:
            self.send_json({"error": "Supabase not configured"}, 503)
            return None
        token = self._get_bearer_token()
        if not token:
            self.send_json({"error": "Authorization required"}, 401)
            return None
        try:
            from backend.admin_auth import get_user_and_role_from_token
            user_id, role = get_user_and_role_from_token(supabase, "Bearer " + token)
        except Exception as e:
            log("admin_auth error: %s" % e)
            self.send_json({"error": "Invalid token"}, 401)
            return None
        if role != "admin":
            self.send_json({"error": "Admin access required"}, 403)
            return None
        return (user_id, role)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def _handle_batch_locations(self):
        """Idempotent batch location upload. Plan 8.1-8.2, Phase 4: optional Bearer auth (driver posts own only)."""
        try:
            from backend.supabase_client import is_configured
            if not is_configured():
                supabase = None
            else:
                supabase = _get_supabase()
        except Exception:
            supabase = None
        if not supabase:
            self.send_json({"error": "Supabase not configured"}, 503)
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, 400)
            return
        events = payload.get("events") or []
        if not isinstance(events, list):
            self.send_json({"error": "events must be an array"}, 400)
            return

        driver_id = None
        auth_header = self.headers.get("Authorization")
        if auth_header:
            try:
                from backend.driver_auth import resolve_driver_id_from_token
                driver_id = resolve_driver_id_from_token(supabase, auth_header)
            except Exception as e:
                log("driver_auth resolve: %s" % e)
        if not driver_id:
            driver_id = payload.get("driver_id")
        if not driver_id:
            self.send_json({"error": "driver_id required (or send Authorization: Bearer <token>)"}, 400)
            return
        if auth_header and payload.get("driver_id") and str(payload.get("driver_id")) != str(driver_id):
            self.send_json({"error": "driver_id does not match authenticated driver"}, 403)
            return

        try:
            from backend.location_batch import batch_location_events
            accepted, errs = batch_location_events(supabase, str(driver_id), events)
            self.send_json({"accepted": accepted, "errors": errs})
        except Exception as e:
            log("batch_locations error: %s" % e)
            self.send_json({"error": str(e)[:100], "accepted": 0, "errors": []}, 500)

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/poll/status":
            with _poll_lock:
                self.send_json(dict(_last_poll_stats))
            return
        if path == "/api/routes":
            routes = load_json(ROUTES_PATH, [])
            self.send_json(routes)
            return
        if path == "/api/drivers":
            supabase = _get_supabase()
            if supabase:
                try:
                    from backend.drivers_list import get_drivers
                    drivers = get_drivers(supabase)
                    self.send_json(drivers)
                except Exception as e:
                    log("get_drivers error: %s" % e)
                    drivers = load_json(DRIVERS_PATH, [])
                    self.send_json(drivers)
            else:
                drivers = load_json(DRIVERS_PATH, [])
                self.send_json(drivers)
            return
        if path == "/api/config":
            config = load_config()
            out = {"mapsApiKey": config.get("google_api_key", "")}
            url = os.environ.get("SUPABASE_URL", "").strip() or config.get("supabase_url", "")
            anon = os.environ.get("SUPABASE_ANON_KEY", "").strip() or config.get("supabase_anon_key", "")
            if url and anon:
                out["supabaseUrl"] = url
                out["supabaseAnonKey"] = anon
            api_base = (
                config.get("api_base") or config.get("backend_public_url")
                or os.environ.get("BACKEND_PUBLIC_URL", "").strip()
            )
            if not api_base and self.headers.get("Host"):
                api_base = "http://" + self.headers.get("Host", "localhost:8080").split(",")[0].strip()
            if api_base:
                out["apiBase"] = api_base.rstrip("/")
            self.send_json(out)
            return
        # Phase 3: Jobs API
        if path.startswith("/api/jobs/"):
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            path_rest = path[len("/api/jobs/"):].rstrip("/")
            if "/" in path_rest:
                job_id, sub = path_rest.split("/", 1)
                if sub == "candidate-drivers":
                    try:
                        from backend.drivers_list import get_drivers
                        from backend.assignment_validation import validate_assignment
                        drivers = get_drivers(supabase)
                        job = None
                        try:
                            from backend.jobs import get_job
                            job = get_job(supabase, job_id)
                        except Exception:
                            pass
                        if not job:
                            self.send_json({"error": "Job not found"}, 404)
                            return
                        candidates = []
                        for d in drivers:
                            v = validate_assignment(supabase, d["id"], job_id)
                            candidates.append({
                                "driver": d,
                                "allowed": v.get("allowed", False),
                                "reasons": v.get("reasons", []),
                            })
                        self.send_json({"job_id": job_id, "candidates": candidates})
                    except Exception as e:
                        log("candidate-drivers error: %s" % e)
                        self.send_json({"error": str(e)[:200]}, 500)
                    return
            elif path_rest:
                job_id = path_rest
                try:
                    from backend.jobs import get_job
                    job = get_job(supabase, job_id)
                    if not job:
                        self.send_json({"error": "Job not found"}, 404)
                        return
                    self.send_json(job)
                except Exception as e:
                    log("get_job error: %s" % e)
                    self.send_json({"error": str(e)[:200]}, 500)
                return
        if path == "/api/jobs":
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            qs = parse_qs(urlparse(self.path).query)
            status = (qs.get("status") or [None])[0]
            near_lat = (qs.get("near_lat") or [None])[0]
            near_lng = (qs.get("near_lng") or [None])[0]
            min_mi = (qs.get("min_mi") or [None])[0]
            max_mi = (qs.get("max_mi") or [None])[0]
            near_driver_id = (qs.get("near_driver_id") or [None])[0]
            try:
                from backend.jobs import list_jobs
                jobs = list_jobs(supabase, status=status, near_lat=near_lat, near_lng=near_lng, min_mi=min_mi, max_mi=max_mi, near_driver_id=near_driver_id)
                self.send_json(jobs)
            except Exception as e:
                log("list_jobs error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 5: GET ingestion-documents, permit-candidates
        if path == "/api/ingestion-documents":
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            qs = parse_qs(urlparse(self.path).query)
            ps = (qs.get("processing_status") or [None])[0]
            st = (qs.get("source_type") or [None])[0]
            try:
                from backend.ingestion import list_ingestion_documents
                out = list_ingestion_documents(supabase, processing_status=ps, source_type=st)
                self.send_json(out)
            except Exception as e:
                log("list_ingestion_documents error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        if path == "/api/permit-candidates":
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            qs = parse_qs(urlparse(self.path).query)
            rs = (qs.get("review_status") or [None])[0]
            try:
                from backend.ingestion import list_permit_candidates
                out = list_permit_candidates(supabase, review_status=rs)
                self.send_json(out)
            except Exception as e:
                log("list_permit_candidates error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Current user profile (id, email, role) — requires Bearer
        if path == "/api/me":
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            token = self._get_bearer_token()
            if not token:
                self.send_json({"error": "Authorization required"}, 401)
                return
            try:
                from backend.admin_auth import get_user_and_role_from_token
                from backend.admin import get_user
                user_id, role = get_user_and_role_from_token(supabase, "Bearer " + token)
                if not user_id:
                    self.send_json({"error": "Invalid token"}, 401)
                    return
                profile = get_user(supabase, user_id)
                if not profile:
                    self.send_json({"id": user_id, "email": None, "role": role or "driver", "active": True})
                    return
                self.send_json({"id": profile.get("id"), "email": profile.get("email"), "role": profile.get("role") or "driver", "active": profile.get("active", True)})
            except Exception as e:
                log("api/me error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Admin: list users (admin only)
        if path == "/api/admin/users":
            admin = self._require_admin()
            if admin is None:
                return
            supabase = _get_supabase()
            try:
                from backend.admin import list_users
                out = list_users(supabase)
                self.send_json(out)
            except Exception as e:
                log("admin list_users error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Admin: driver state permissions (admin only)
        match_dsp = re.match(r"^/api/admin/drivers/([^/]+)/state-permissions$", path)
        if match_dsp:
            admin = self._require_admin()
            if admin is None:
                return
            driver_id = match_dsp.group(1)
            supabase = _get_supabase()
            try:
                from backend.admin import list_driver_state_permissions
                out = list_driver_state_permissions(supabase, driver_id)
                self.send_json(out)
            except Exception as e:
                log("admin list_driver_state_permissions error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Admin: dispatch config (admin only)
        if path == "/api/admin/config":
            admin = self._require_admin()
            if admin is None:
                return
            supabase = _get_supabase()
            try:
                from backend.admin import get_dispatch_config
                out = get_dispatch_config(supabase)
                self.send_json(out)
            except Exception as e:
                log("admin get_dispatch_config error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Static file from web/
        if path == "/":
            path = "/index.html"
        file_path = os.path.join(WEB_DIR, path.lstrip("/"))
        if not os.path.normpath(file_path).startswith(os.path.normpath(WEB_DIR)):
            self.send_error(403)
            return
        if not os.path.isfile(file_path):
            self.send_error(404)
            return
        ext = os.path.splitext(file_path)[1].lower()
        types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".ico": "image/x-icon",
        }
        self.send_response(200)
        self.send_header("Content-Type", types.get(ext, "application/octet-stream"))
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def do_PATCH(self):
        path = urlparse(self.path).path
        # Admin: update user (role, active)
        match_admin_user = re.match(r"^/api/admin/users/([^/]+)$", path)
        if match_admin_user:
            admin = self._require_admin()
            if admin is None:
                return
            user_id = match_admin_user.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            supabase = _get_supabase()
            try:
                from backend.admin import update_user
                out = update_user(supabase, user_id, payload)
                if out is not None:
                    self.send_json(out)
                else:
                    self.send_json({"error": "User not found"}, 404)
            except Exception as e:
                log("admin update_user error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Admin: update dispatch config (body: { key, value } or { updates: { k: v } })
        if path == "/api/admin/config":
            admin = self._require_admin()
            if admin is None:
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            supabase = _get_supabase()
            try:
                from backend.admin import update_dispatch_config, get_dispatch_config
                if "key" in payload and "value" in payload:
                    update_dispatch_config(supabase, payload["key"], payload["value"])
                elif "updates" in payload and isinstance(payload["updates"], dict):
                    for k, v in payload["updates"].items():
                        update_dispatch_config(supabase, k, v)
                out = get_dispatch_config(supabase)
                self.send_json(out)
            except Exception as e:
                log("admin update_dispatch_config error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 5: PATCH /api/permit-candidates/:id (edit candidate fields)
        match_cand = re.match(r"^/api/permit-candidates/([^/]+)$", path)
        if match_cand:
            cand_id = match_cand.group(1)
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            try:
                from backend.ingestion import update_permit_candidate
                out = update_permit_candidate(supabase, cand_id, payload)
                if out is not None:
                    self.send_json(out)
                else:
                    self.send_json({"error": "Candidate not found"}, 404)
            except Exception as e:
                log("patch permit_candidate error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 3: PATCH /api/jobs/:id (update job status)
        match_job = re.match(r"^/api/jobs/([^/]+)$", path)
        if match_job:
            job_id = match_job.group(1)
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            try:
                from backend.jobs import get_job, update_job_status, update_job
                if "status" in payload or "origin_lat" in payload or "origin_lng" in payload:
                    updated = update_job(supabase, job_id, payload)
                    if updated:
                        self.send_json(updated)
                    else:
                        self.send_json({"error": "Job not found"}, 404)
                else:
                    self.send_json({"error": "No status or origin_lat/lng in body"}, 400)
            except Exception as e:
                log("patch job error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        match = re.match(r"^/api/routes/(.+)$", path)
        if not match:
            self.send_error(404)
            return
        route_id = match.group(1)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, 400)
            return
        routes = load_json(ROUTES_PATH, [])
        updated = None
        for r in routes:
            if str(r.get("id")) == str(route_id):
                if "status" in payload:
                    r["status"] = payload["status"]
                if "assigned_driver" in payload:
                    r["assigned_driver"] = payload["assigned_driver"]
                updated = r
                break
        if updated is None:
            self.send_json({"error": "Route not found"}, 404)
            return
        save_json(ROUTES_PATH, routes)
        self.send_json(updated)

    def do_PUT(self):
        path = urlparse(self.path).path
        # Admin: set driver state permissions (body: { permissions: [ { state_code, allowed } ] })
        match_put_dsp = re.match(r"^/api/admin/drivers/([^/]+)/state-permissions$", path)
        if match_put_dsp:
            admin = self._require_admin()
            if admin is None:
                return
            driver_id = match_put_dsp.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            permissions = payload.get("permissions")
            if not isinstance(permissions, list):
                permissions = []
            supabase = _get_supabase()
            try:
                from backend.admin import set_driver_state_permissions
                out = set_driver_state_permissions(supabase, driver_id, permissions)
                self.send_json(out)
            except Exception as e:
                log("admin set_driver_state_permissions error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        self.send_error(404)

    def do_POST(self):
        global last_poll_time, _last_poll_stats
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/poll":
            now = time.time()
            if last_poll_time is not None and (now - last_poll_time) <= POLL_THROTTLE_SEC:
                self.send_json({"polled": False})
                return
            # Run poll in background so the client doesn't time out (IMAP + geocoding can take 30s+)
            with _poll_lock:
                _last_poll_stats.clear()
            def run_poll():
                global last_poll_time, _last_poll_stats
                try:
                    stats = poller_module.poll_once(poller_module.load_config())
                    with _poll_lock:
                        last_poll_time = time.time()
                        _last_poll_stats.clear()
                        _last_poll_stats.update(stats if isinstance(stats, dict) else {"polled": True})
                except Exception as e:
                    print("Poll error:", e)
                    with _poll_lock:
                        _last_poll_stats.clear()
                        _last_poll_stats.update({"polled": False, "error": str(e)})
            t = threading.Thread(target=run_poll, daemon=True)
            t.start()
            # Return immediately so connection isn't held; UI can GET /api/routes again in a few seconds
            self.send_json({"polled": True, "in_background": True})
            return
        if path == "/api/driver-locations/batch":
            self._handle_batch_locations()
            return
        # Phase 3: POST /api/jobs (create job - manual for testing; Phase 5 will add from permit_candidate)
        if path == "/api/jobs":
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            try:
                from backend.jobs import create_job
                job = create_job(supabase, payload)
                if job:
                    self.send_json(job)
                else:
                    self.send_json({"error": "Create failed"}, 500)
            except Exception as e:
                log("create_job error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 5: POST /api/ingestion-documents (multipart: file + source_type)
        if path == "/api/ingestion-documents":
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            ct = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ct:
                self.send_json({"error": "Content-Type must be multipart/form-data"}, 400)
                return
            try:
                cl = int(self.headers.get("Content-Length", 0))
                if cl <= 0:
                    self.send_json({"error": "Content-Length required"}, 400)
                    return
                body_bytes = self.rfile.read(cl)
                form = _parse_multipart(body_bytes, ct)
                file_item = form.get("file") or form.get("document")
                if isinstance(file_item, tuple):
                    filename, file_data, mime_type = file_item[0], file_item[1], file_item[2] if len(file_item) > 2 else "application/octet-stream"
                else:
                    file_data = None
                    filename = "upload.bin"
                    mime_type = None
                source_type = (form.get("source_type") or "manual_upload").strip() if isinstance(form.get("source_type"), str) else "manual_upload"
                if source_type not in ("email_pdf", "text_screenshot", "email_screenshot", "manual_upload"):
                    source_type = "manual_upload"
                if not file_data:
                    self.send_json({"error": "file or document field required"}, 400)
                    return
                from backend.ingestion import create_ingestion_document
                doc = create_ingestion_document(client=supabase, source_type=source_type, file_data=file_data, filename=filename, mime_type=mime_type)
                if doc:
                    self.send_json(doc)
                else:
                    self.send_json({"error": "Create failed"}, 500)
            except Exception as e:
                log("ingestion-documents upload error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 5: POST /api/ingestion-documents/:id/parse
        if path.startswith("/api/ingestion-documents/") and path.endswith("/parse"):
            doc_id = path[len("/api/ingestion-documents/"):-len("/parse")].rstrip("/")
            if not doc_id:
                self.send_error(404)
                return
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            try:
                from backend.ingestion import parse_ingestion_document
                candidate, err = parse_ingestion_document(supabase, doc_id)
                if err:
                    self.send_json({"error": err}, 400)
                    return
                self.send_json({"permit_candidate": candidate, "ingestion_document_id": doc_id})
            except Exception as e:
                log("parse error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 5: POST /api/permit-candidates/:id/approve
        if re.match(r"^/api/permit-candidates/[^/]+/approve$", path):
            parts = path.split("/")
            cand_id = parts[-2] if len(parts) >= 5 else None
            if not cand_id:
                self.send_error(404)
                return
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            try:
                from backend.ingestion import approve_permit_candidate, get_permit_candidate
                approve_permit_candidate(supabase, cand_id)
                out = get_permit_candidate(supabase, cand_id)
                self.send_json(out or {"id": cand_id, "review_status": "approved"})
            except Exception as e:
                log("approve error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 5: POST /api/permit-candidates/:id/reject
        if re.match(r"^/api/permit-candidates/[^/]+/reject$", path):
            parts = path.split("/")
            cand_id = parts[-2] if len(parts) >= 5 else None
            if not cand_id:
                self.send_error(404)
                return
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            try:
                from backend.ingestion import reject_permit_candidate, get_permit_candidate
                reject_permit_candidate(supabase, cand_id)
                out = get_permit_candidate(supabase, cand_id)
                self.send_json(out or {"id": cand_id, "review_status": "rejected"})
            except Exception as e:
                log("reject error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 5: POST /api/permit-candidates/:id/create-job
        if re.match(r"^/api/permit-candidates/[^/]+/create-job$", path):
            parts = path.split("/")
            cand_id = parts[-2] if len(parts) >= 6 else None
            if not cand_id:
                self.send_error(404)
                return
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            try:
                from backend.ingestion import create_job_from_candidate
                job, err = create_job_from_candidate(supabase, cand_id)
                if err:
                    self.send_json({"error": err}, 400)
                    return
                self.send_json(job)
            except Exception as e:
                log("create_job_from_candidate error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        # Phase 3: POST /api/jobs/:id/assign
        if path.startswith("/api/jobs/") and path.endswith("/assign"):
            job_id = path[len("/api/jobs/"):-len("/assign")].rstrip("/")
            if not job_id:
                self.send_error(404)
                return
            supabase = _get_supabase()
            if not supabase:
                self.send_json({"error": "Supabase not configured"}, 503)
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            driver_id = payload.get("driver_id")
            if not driver_id:
                self.send_json({"error": "driver_id required"}, 400)
                return
            try:
                from backend.jobs import assign_driver
                job, err = assign_driver(supabase, job_id, str(driver_id))
                if err:
                    code = err.get("code", "VALIDATION_FAILED")
                    status = 409 if code == "VALIDATION_FAILED" else 422
                    self.send_json({"error": err.get("error", "Assignment not allowed"), "reasons": err.get("reasons", [])}, status)
                    return
                self.send_json(job)
            except Exception as e:
                log("assign_driver error: %s" % e)
                self.send_json({"error": str(e)[:200]}, 500)
            return
        self.send_error(404)


def main():
    log("main() entered")
    os.makedirs(WEB_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    try:
        server = HTTPServer((host, PORT), Handler)
        server.allow_reuse_address = True
        log("HTTPServer created, listening on %s:%s" % (host, PORT))
        print("PilotCar Map server at http://{}:{}".format(host, PORT))
        log("calling serve_forever()")
        server.serve_forever()
    except Exception as e:
        log("Server failed to start: %s" % e)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("Fatal: %s" % e)
        raise
