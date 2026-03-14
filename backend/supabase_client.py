"""
Supabase client for GIGATT Geomapper backend.
Used for: driver-locations batch, drivers/jobs from DB, auth validation.
Falls back to None if env not configured.
"""
import os
import logging

logger = logging.getLogger(__name__)
_supabase = None


def _load_dotenv():
    """Load .env if python-dotenv available. Then load baked-in secrets (Guru Config, Supabase Pass)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    try:
        from backend.secrets_loader import load_into_env
        load_into_env()
    except Exception:
        pass


def get_client():
    """Return Supabase client or None if not configured."""
    global _supabase
    if _supabase is not None:
        return _supabase
    _load_dotenv()
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        logger.debug("Supabase not configured (missing SUPABASE_URL or SUPABASE_SERVICE_KEY)")
        return None
    try:
        from supabase import create_client
        _supabase = create_client(url, key)
        return _supabase
    except ImportError:
        logger.warning("supabase package not installed; run: pip install supabase")
        return None


def is_configured():
    """True if Supabase env vars are set."""
    _load_dotenv()
    return bool(os.environ.get("SUPABASE_URL", "").strip() and
                os.environ.get("SUPABASE_SERVICE_KEY", "").strip())
