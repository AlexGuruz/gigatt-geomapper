"""
Resolve user id and role from Bearer token (Supabase JWT). Used to require admin role for admin API routes.
"""
import os


def get_user_and_role_from_token(client, bearer_token):
    """
    If bearer_token is a valid Supabase JWT, return (user_id, role) from profiles.
    Otherwise return (None, None). role is e.g. 'driver', 'dispatcher', 'admin'.
    """
    if not client or not bearer_token or not isinstance(bearer_token, str):
        return None, None
    token = bearer_token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return None, None
    try:
        import jwt
    except ImportError:
        return None, None
    secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not secret:
        return None, None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except Exception:
        return None, None
    user_id = payload.get("sub")
    if not user_id:
        return None, None
    try:
        r = client.table("profiles").select("id, role").eq("id", user_id).limit(1).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        if rows:
            return str(rows[0]["id"]), (rows[0].get("role") or "driver")
    except Exception:
        pass
    return user_id, None  # user exists in JWT but no profile row
