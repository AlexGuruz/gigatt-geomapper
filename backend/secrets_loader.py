"""
Load Supabase credentials from baked-in secret files.
Files: E:\\secrets\\gcp\\Guru Config.json, E:\\secrets\\gcp\\Supabase Pass.json
Supports JSON or custom "key → value" text format. Populates os.environ for app use.
"""
import json
import os
import re

# Baked-in paths (override via SECRETS_DIR env)
_DEFAULT_SECRETS_DIR = r"E:\secrets\gcp"
_GURU_CONFIG = "Guru Config.json"
_SUPABASE_PASS = "Supabase Pass.json"

_loaded = False


def _secrets_dir():
    return os.environ.get("SECRETS_DIR", "").strip() or _DEFAULT_SECRETS_DIR


def _parse_text_config(content: str) -> dict:
    """Parse custom format: 'key → value' or 'key: value' per line."""
    out = {}
    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = False
        for sep in ("→", "->", "←"):
            if sep in line:
                k, _, v = line.partition(sep)
                out[k.strip()] = v.strip()
                parsed = True
                break
        if not parsed and ": " in line and not line.startswith("{"):
            k, _, v = line.partition(": ")
            out[k.strip()] = v.strip()
    return out


def _parse_supabase_pass(content: str) -> dict:
    """Parse Supabase Pass - may be 'key\\nvalue' pairs or plain lines."""
    lines = [l.strip() for l in content.strip().splitlines() if l.strip()]
    out = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and " " not in line and lines[i + 1]:
            # Possible key-value pair
            out[line] = lines[i + 1]
            i += 2
        else:
            # Single line - map common names
            lower = line.lower()
            if "project" in lower or "password" in lower:
                out["project_or_password"] = line
            i += 1
    return out


def _load_file(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return {}

    # Try JSON first
    s = raw.strip()
    if s.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Parse as text config
    if "Guru Config" in path or "Guru" in path:
        return _parse_text_config(raw)
    if "Supabase Pass" in path:
        return _parse_supabase_pass(raw)
    return {}


def _get(guru: dict, pass_data: dict, *keys) -> str:
    """Get first matching value from configs."""
    for k in keys:
        v = guru.get(k) or guru.get(k.replace(" ", "_")) or pass_data.get(k)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def load_into_env() -> bool:
    """
    Load credentials from Guru Config + Supabase Pass into os.environ.
    Returns True if SUPABASE_URL and SUPABASE_SERVICE_KEY were set.
    """
    global _loaded
    if _loaded:
        return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))

    base = _secrets_dir()
    guru_path = os.path.join(base, _GURU_CONFIG)
    pass_path = os.path.join(base, _SUPABASE_PASS)

    guru = _load_file(guru_path)
    pass_data = _load_file(pass_path)

    url = _get(guru, pass_data, "Project URL", "project_url", "supabase_url", "SUPABASE_URL")
    anon = _get(guru, pass_data, "anon public key", "anon_public_key", "anon_key", "supabase_anon_key", "SUPABASE_ANON_KEY")
    svc = _get(guru, pass_data, "service_role key", "service_role_key", "service_role", "SUPABASE_SERVICE_KEY")
    backend_url = _get(guru, pass_data, "Backend URL", "backend_public_url", "api_base", "BACKEND_PUBLIC_URL")

    if url and not os.environ.get("SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = url
    if anon and not os.environ.get("SUPABASE_ANON_KEY"):
        os.environ["SUPABASE_ANON_KEY"] = anon
    if svc and not os.environ.get("SUPABASE_SERVICE_KEY"):
        os.environ["SUPABASE_SERVICE_KEY"] = svc
    if backend_url and not os.environ.get("BACKEND_PUBLIC_URL"):
        os.environ["BACKEND_PUBLIC_URL"] = backend_url.rstrip("/")

    _loaded = True
    return bool(url and svc)


def get_supabase_url() -> str:
    """Return SUPABASE_URL from env (after load)."""
    load_into_env()
    return os.environ.get("SUPABASE_URL", "").strip()


def get_supabase_anon_key() -> str:
    """Return SUPABASE_ANON_KEY from env (after load)."""
    load_into_env()
    return os.environ.get("SUPABASE_ANON_KEY", "").strip()


def get_supabase_service_key() -> str:
    """Return SUPABASE_SERVICE_KEY from env (after load)."""
    load_into_env()
    return os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
