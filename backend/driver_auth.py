"""
Resolve driver_id from Bearer token (Supabase JWT). Plan 8.8, Phase 4: driver can only post own location.
"""
import os


def resolve_driver_id_from_token(client, bearer_token):
    """
    If bearer_token is a valid Supabase JWT, return the driver_id (from driver_profiles) for that user.
    Otherwise return None.
    """
    if not client or not bearer_token or not isinstance(bearer_token, str):
        return None
    token = bearer_token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return None
    try:
        import jwt
    except ImportError:
        return None
    secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except Exception:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        r = client.table("driver_profiles").select("id").eq("user_id", user_id).limit(1).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        if rows and rows[0].get("id"):
            return str(rows[0]["id"])
    except Exception:
        pass
    return None
