"""
PilotCar Loads Map - Email poller.
Polls IMAP for "Load Alert" emails, parses route lines, geocodes via Google API, appends to data/routes.json.
Run in a loop (e.g. every poll_interval_sec) or once.
"""
import hashlib
import imaplib
import email
from email.utils import parsedate_to_datetime
import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(ROOT, "config.json")
ROUTES_PATH = os.path.join(DATA_DIR, "routes.json")
CACHE_PATH = os.path.join(DATA_DIR, "geocode_cache.json")
POLLER_STATE_PATH = os.path.join(DATA_DIR, "poller_state.json")

# Route types: each entry is (display_name, list of substrings to match in email body, case-insensitive)
ROUTE_TYPE_MATCHES = [
    ("Lead", ["lead"]),
    ("Chase", ["chase"]),
    ("High Pole", ["high pole", "highpole", "high-pole"]),
    ("Survey", ["survey"]),
    ("Flagger", ["flagger"]),
]
# Pay pattern: $amount optional /day or /mile, optional (total), optional (Quick Pay)
PAY_PATTERN = re.compile(
    r"\$\s*[\d,]+(?:\.\d{2})?\s*(?:/\s*day|/\s*mile)?\s*(?:\(total\))?\s*(?:\(Quick Pay\))?",
    re.IGNORECASE,
)
DOT_PATTERN = re.compile(r"DOT:\s*(\d+)", re.IGNORECASE)
MC_PATTERN = re.compile(r"MC:\s*(\d+)", re.IGNORECASE)
ROUTED_MILES_PATTERN = re.compile(r"(\d+)\s*routed\s*miles?", re.IGNORECASE)
# Optional origin/destination detail (e.g. "Origin: 123 Main St, City, ST" or "Pickup: ...")
ORIGIN_DETAIL_PATTERN = re.compile(
    r"(?:origin|pickup|from):\s*(.+?)(?=\n|$)", re.IGNORECASE | re.DOTALL
)
DEST_DETAIL_PATTERN = re.compile(
    r"(?:destination|delivery|to):\s*(.+?)(?=\n|$)", re.IGNORECASE | re.DOTALL
)


def _resolve_path(path):
    """Resolve a config path relative to ROOT if not absolute."""
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(ROOT, path))


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Resolve API key from file path if set (path relative to project root)
    key_path = raw.get("google_api_key_path")
    if key_path:
        key_path = _resolve_path(key_path)
        if os.path.isfile(key_path):
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    raw = dict(raw)
                    raw["google_api_key"] = f.read().strip()
            except IOError:
                pass
    # Resolve IMAP credentials from file path if set (line1=password, line2=email)
    cred_path = raw.get("imap_credentials_path")
    if cred_path:
        cred_path = _resolve_path(cred_path)
        if os.path.isfile(cred_path):
            try:
                with open(cred_path, "r", encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f.readlines() if ln.strip()]
                if len(lines) >= 2:
                    raw = dict(raw)
                    raw["imap_password"] = lines[0].replace(" ", "")
                    raw["imap_user"] = lines[1]
                elif len(lines) == 1:
                    raw = dict(raw)
                    raw["imap_user"] = lines[0]
            except IOError:
                pass
    return raw


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


def geocode(address, api_key):
    """Return (lat, lng) or (None, None). Uses cache."""
    cache = load_json(CACHE_PATH, {})
    key = address.strip().lower()
    if key in cache:
        return cache[key]["lat"], cache[key]["lng"]
    if not api_key:
        return None, None
    url = "https://maps.googleapis.com/maps/api/geocode/json?address=" + urllib.parse.quote(address) + "&key=" + api_key
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "OK" and data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                lat, lng = loc["lat"], loc["lng"]
                cache[key] = {"lat": lat, "lng": lng}
                save_json(CACHE_PATH, cache)
                return lat, lng
    except Exception:
        pass
    return None, None


def parse_load_alert_body(body):
    """
    Parse an email body for one or more route lines.

    One email/thread can contain several postings, each with a line like:
      - "City, ST, USA to City, ST, USA"
      - "City, ST to City, ST"
      - "City, ST, USA > City, ST, USA"

    Returns a list of parsed route dicts (one per matched route line). If no
    usable routes are found, returns an empty list.
    """
    if not body:
        return []
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return []

    # Collect every line that looks like origin-to-destination (to or >) with city/state (comma)
    route_lines = []
    for ln in lines:
        if "," not in ln:
            continue
        if " to " in ln:
            parts = re.split(r"\s+to\s+", ln, maxsplit=1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                route_lines.append(ln)
                continue
        if " > " in ln:
            parts = re.split(r"\s*>\s*", ln, maxsplit=1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                route_lines.append(ln)
                continue

    if not route_lines:
        return []

    # Shared body-level metadata (applies to all routes in this email)
    first = (lines[0] or "").strip()
    company = ""
    if first:
        fl = first.lower()
        if (
            " to " not in fl
            and " mi" not in fl
            and "routed" not in fl
            and "needed" not in fl
            and "credentials" not in fl
            and not re.match(r"^\d+\s", first)
            and len(first) < 80
        ):
            company = first

    miles = None
    routed_miles = None
    date_val = None
    phone = None
    phone_text_only = False
    for ln in lines:
        mi = re.match(r"(\d+)\s*mi", ln, re.I)
        if mi:
            miles = int(mi.group(1))
        if re.match(r"^\d{1,2}/\d{1,2}", ln):
            date_val = ln
        digits = re.sub(r"\D", "", ln)
        if len(digits) >= 10:
            phone = ln.strip()
            if "text only" in ln.lower():
                phone_text_only = True
    rm = ROUTED_MILES_PATTERN.search(body)
    if rm:
        routed_miles = int(rm.group(1))
    dot_match = DOT_PATTERN.search(body)
    dot = dot_match.group(1) if dot_match else None
    mc_match = MC_PATTERN.search(body)
    mc = mc_match.group(1) if mc_match else None
    pay_match = PAY_PATTERN.search(body)
    pay = pay_match.group(0).strip() if pay_match else None

    origin_detail = None
    dest_detail = None
    om = ORIGIN_DETAIL_PATTERN.search(body)
    if om:
        origin_detail = om.group(1).strip().split("\n")[0].strip()
    dm = DEST_DETAIL_PATTERN.search(body)
    if dm:
        dest_detail = dm.group(1).strip().split("\n")[0].strip()

    body_lower = body.lower()
    route_types = []
    for display_name, substrings in ROUTE_TYPE_MATCHES:
        for sub in substrings:
            if sub.lower() in body_lower:
                route_types.append(display_name)
                break

    result = []
    for route_line in route_lines:
        if " to " in route_line:
            parts = re.split(r"\s+to\s+", route_line, maxsplit=1)
        else:
            parts = re.split(r"\s*>\s*", route_line, maxsplit=1)
        if len(parts) != 2:
            continue
        origin, destination = parts[0].strip(), parts[1].strip()
        # Prefer city/state-style for geocoding: ensure we have something like "City, ST" or "City, ST, USA"
        if len(origin) < 3 or len(destination) < 3:
            continue
        result.append(
            {
                "company": company,
                "origin": origin,
                "destination": destination,
                "origin_detail": origin_detail,
                "dest_detail": dest_detail,
                "miles": miles,
                "routed_miles": routed_miles,
                "date": date_val,
                "phone": phone,
                "phone_text_only": phone_text_only,
                "pay": pay,
                "dot": dot,
                "mc": mc,
                "chase": route_line,
                "route_types": route_types,
            }
        )
    return result


def route_id(parsed):
    """Stable per-route id; include route line so multiple postings in one email are distinct."""
    h = hashlib.sha256(
        (
            parsed.get("origin", "")
            + "|"
            + parsed.get("destination", "")
            + "|"
            + parsed.get("date", "")
            + "|"
            + parsed.get("chase", "")
        ).encode()
    ).hexdigest()
    return h[:16]


def poll_once(config):
    """
    Poll IMAP once, append new routes to data/routes.json.
    Returns dict with keys: polled, error, added, skipped_sender, skipped_parse, skipped_duplicate, total_checked.
    """
    api_key = config.get("google_api_key", "")
    host = config.get("imap_host", "imap.gmail.com")
    port = int(config.get("imap_port", 993))
    user = config.get("imap_user", "")
    password = config.get("imap_password", "")
    folder = config.get("imap_folder", "INBOX")
    # allowed_senders: omit or use [] to allow all senders; otherwise list of substrings to match in From
    allowed_senders_cfg = config.get("allowed_senders")
    if allowed_senders_cfg is None:
        allowed_senders_cfg = ["team@pilotcarloads.com"]
    allow_all_senders = isinstance(allowed_senders_cfg, list) and len(allowed_senders_cfg) == 0
    allowed_senders = set() if allow_all_senders else {s.lower() for s in allowed_senders_cfg}

    stats = {"polled": False, "added": 0, "skipped_sender": 0, "skipped_parse": 0, "skipped_duplicate": 0, "total_checked": 0, "added_routes": []}

    if not user or not password:
        return stats

    routes = load_json(ROUTES_PATH, [])
    existing_ids = {r.get("id") for r in routes if r.get("id")}

    # Persist last-seen IMAP UID so we only fetch new messages (realistic counts)
    state = load_json(POLLER_STATE_PATH, {})
    last_seen_uid = int(state.get("last_seen_uid") or 0)

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select(folder)

        # 1) Messages we haven't seen (UID > last_seen_uid). Use single criterion per IMAP spec.
        uid_set = set()
        if last_seen_uid > 0:
            try:
                _, msg_ids = conn.uid("SEARCH", None, "UID %d:*" % (last_seen_uid + 1))
                if msg_ids and msg_ids[0]:
                    for u in msg_ids[0].split():
                        try:
                            uid_set.add(int(u))
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass
        else:
            # Bootstrap: recent window only
            poll_since_days = config.get("poll_since_days")
            if isinstance(poll_since_days, (int, float)) and poll_since_days > 0:
                since_date = time.gmtime(time.time() - int(poll_since_days) * 86400)
                since_str = time.strftime("%d-%b-%Y", since_date)
                _, msg_ids = conn.uid("SEARCH", None, "(SINCE %s)" % since_str)
            else:
                _, msg_ids = conn.uid("SEARCH", None, "ALL")
            id_list = msg_ids[0].split() if msg_ids and msg_ids[0] else []
            for u in (id_list[-50:] if len(id_list) > 50 else id_list):
                try:
                    uid_set.add(int(u))
                except (ValueError, TypeError):
                    pass

        # 2) Always include a recent window (default 2 days) so we never miss newest emails
        poll_recent_days = config.get("poll_recent_days")
        if poll_recent_days is None:
            poll_recent_days = 2
        if isinstance(poll_recent_days, (int, float)) and poll_recent_days > 0:
            since_date = time.gmtime(time.time() - int(poll_recent_days) * 86400)
            since_str = time.strftime("%d-%b-%Y", since_date)
            try:
                _, msg_ids = conn.uid("SEARCH", None, "(SINCE %s)" % since_str)
                if msg_ids and msg_ids[0]:
                    recent_uids = []
                    for u in msg_ids[0].split():
                        try:
                            recent_uids.append(int(u))
                        except (ValueError, TypeError):
                            pass
                    recent_uids.sort(reverse=True)
                    for u in recent_uids[:100]:  # cap at 100 from recent window
                        uid_set.add(u)
            except Exception:
                pass

        uid_list = sorted(uid_set, reverse=True)
        max_uid_seen = last_seen_uid

        for uid in uid_list:
            stats["total_checked"] += 1
            _, data = conn.uid("FETCH", str(uid), "(RFC822)")
            if not data or not data[0]:
                continue
            if data[0] and isinstance(data[0], tuple) and len(data[0]) >= 2:
                raw = data[0][1]
            else:
                continue
            try:
                if isinstance(raw, bytes):
                    pass
                else:
                    raw = raw.encode("utf-8", errors="replace") if raw else b""
            except Exception:
                continue
            msg = email.message_from_bytes(raw)
            max_uid_seen = max(max_uid_seen, uid)
            from_hdr = (msg.get("From") or "").lower()
            if not allow_all_senders and not any(s in from_hdr for s in allowed_senders):
                stats["skipped_sender"] += 1
                continue
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        except Exception:
                            body = ""
                        break
                if not body.strip():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        if ctype == "text/html":
                            try:
                                raw = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                body = re.sub(r"<[^>]+>", " ", raw)
                                body = re.sub(r"\s+", "\n", body).strip()
                            except Exception:
                                pass
                            break
            else:
                try:
                    payload = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                    if "text/html" in (msg.get_content_type() or ""):
                        payload = re.sub(r"<[^>]+>", " ", payload)
                        payload = re.sub(r"\s+", "\n", payload).strip()
                    body = payload
                except Exception:
                    body = ""
            parsed_list = parse_load_alert_body(body)
            if not parsed_list:
                stats["skipped_parse"] += 1
                continue
            # Use email Date header as ingestion time when available; else poll time
            posted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            date_hdr = msg.get("Date")
            if date_hdr:
                try:
                    dt = parsedate_to_datetime(date_hdr)
                    posted_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except (ValueError, TypeError):
                    pass

            for parsed in parsed_list:
                rid = route_id(parsed)
                if rid in existing_ids:
                    stats["skipped_duplicate"] += 1
                    continue
                origin_geocode = (parsed.get("origin_detail") or parsed["origin"]).strip()
                dest_geocode = (parsed.get("dest_detail") or parsed["destination"]).strip()
                origin_lat, origin_lng = geocode(origin_geocode, api_key)
                dest_lat, dest_lng = geocode(dest_geocode, api_key)
                # Use email Date header as ingestion time; fallback to poll time
                posted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                date_hdr = msg.get("Date")
                if date_hdr:
                    try:
                        dt = parsedate_to_datetime(date_hdr)
                        posted_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    except (ValueError, TypeError):
                        pass
                route = {
                    "id": rid,
                    "origin": parsed["origin"],
                    "destination": parsed["destination"],
                    "origin_detail": parsed.get("origin_detail"),
                    "dest_detail": parsed.get("dest_detail"),
                    "origin_lat": origin_lat,
                    "origin_lng": origin_lng,
                    "dest_lat": dest_lat,
                    "dest_lng": dest_lng,
                    "miles": parsed["miles"],
                    "routed_miles": parsed.get("routed_miles"),
                    "company": parsed["company"],
                    "chase": parsed.get("chase", ""),
                    "date": parsed.get("date", ""),
                    "phone": parsed.get("phone", ""),
                    "phone_text_only": parsed.get("phone_text_only", False),
                    "pay": parsed.get("pay"),
                    "dot": parsed.get("dot"),
                    "mc": parsed.get("mc"),
                    "route_types": parsed.get("route_types", []),
                    "status": "new",
                    "posted_at": posted_at,
                }
                routes.append(route)
                existing_ids.add(rid)
                stats["added"] += 1
                stats["added_routes"].append({"id": rid, "origin": route["origin"], "destination": route["destination"]})

        conn.close()
        conn.logout()
        stats["polled"] = True
        # Persist highest UID we saw so next poll only fetches newer messages
        if max_uid_seen > last_seen_uid:
            try:
                save_json(POLLER_STATE_PATH, {"last_seen_uid": max_uid_seen})
            except IOError:
                pass
    except Exception as e:
        stats["error"] = str(e)
        print("Poller IMAP error:", e)
        return stats

    save_json(ROUTES_PATH, routes)

    # Write last poll result to log for debugging (why new emails might not appear)
    log_path = os.path.join(DATA_DIR, "poll_log.txt")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " | "
                + "added=%d skipped_sender=%d skipped_parse=%d skipped_duplicate=%d total_checked=%d\n"
                % (
                    stats.get("added", 0),
                    stats.get("skipped_sender", 0),
                    stats.get("skipped_parse", 0),
                    stats.get("skipped_duplicate", 0),
                    stats.get("total_checked", 0),
                )
            )
            if stats.get("error"):
                f.write("Error: " + stats["error"] + "\n")
            # Log each route added this run so you can verify email -> UI
            added_list = stats.get("added_routes") or []
            for r in added_list:
                f.write("  + %s -> %s (id=%s)\n" % (r.get("origin", ""), r.get("destination", ""), r.get("id", "")))
    except IOError:
        pass

    return stats


def main():
    config = load_config()
    poll_interval = int(config.get("poll_interval_sec", 60))
    print("PilotCar poller: running every", poll_interval, "s (Ctrl+C to stop)")
    while True:
        s = poll_once(config)
        if s.get("polled"):
            print(
                "Poll: added=%d skipped_sender=%d skipped_parse=%d skipped_duplicate=%d"
                % (
                    s.get("added", 0),
                    s.get("skipped_sender", 0),
                    s.get("skipped_parse", 0),
                    s.get("skipped_duplicate", 0),
                )
            )
        elif s.get("error"):
            print("Poll error:", s["error"])
        time.sleep(poll_interval)


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        s = poll_once(load_config())
        print("Done (once). added=%d skipped_sender=%d skipped_parse=%d skipped_duplicate=%d total_checked=%d" % (
            s.get("added", 0), s.get("skipped_sender", 0), s.get("skipped_parse", 0),
            s.get("skipped_duplicate", 0), s.get("total_checked", 0)))
        if s.get("error"):
            print("Error:", s["error"])
    else:
        main()
