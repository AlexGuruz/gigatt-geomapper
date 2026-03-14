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
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def _handle_batch_locations(self):
        """Idempotent batch location upload. Plan 8.1-8.2."""
        supabase = _get_supabase() if callable(getattr(__import__('backend.supabase_client', fromlist=['is_configured']), 'is_configured', None)) else None
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
        driver_id = payload.get("driver_id")
        events = payload.get("events") or []
        if not driver_id:
            self.send_json({"error": "driver_id required"}, 400)
            return
        if not isinstance(events, list):
            self.send_json({"error": "events must be an array"}, 400)
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
            self.send_json(out)
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
        self.send_error(404)

    def _handle_batch_locations(self):
        """Idempotent batch location insert. Plan 8.1-8.2."""
        if not is_configured():
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
        events = payload.get("events") or []
        if not driver_id or not isinstance(events, list):
            self.send_json({"error": "driver_id and events[] required"}, 400)
            return
        try:
            from backend.location_batch import batch_location_events
            client = get_client()
            accepted, errs = batch_location_events(client, str(driver_id), events)
            self.send_json({"accepted": accepted, "errors": errs})
        except Exception as e:
            log("batch locations error: %s" % e)
            self.send_json({"error": str(e)[:200]}, 500)


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
