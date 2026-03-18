#!/usr/bin/env python3
"""
Create test users for GIGATT Geomapper Phase 1.
Requires: SUPABASE_URL, SUPABASE_SERVICE_KEY in .env (or env vars).
Run: python scripts/create_test_users.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Load baked-in secrets (E:\secrets\gcp\Guru Config.json, Supabase Pass.json)
try:
    from backend.secrets_loader import load_into_env
    load_into_env()
except Exception:
    pass

URL = os.environ.get("SUPABASE_URL", "").strip()
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

TEST_USERS = [
    {"email": "admin@test.gigatt.com", "password": "WhatADay!", "role": "admin", "name": "Admin"},
    {"email": "dispatcher@test.gigatt.com", "password": "Test123!@#", "role": "dispatcher", "name": "Test Dispatcher"},
    {"email": "driver@test.gigatt.com", "password": "Test123!@#", "role": "driver", "name": "Test Driver"},
]


def main():
    if not URL or not KEY:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY. Set in .env")
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        print("Run: pip install supabase")
        sys.exit(1)

    client = create_client(URL, KEY)

    for u in TEST_USERS:
        email = u["email"]
        password = u["password"]
        role = u["role"]
        name = u.get("name", "")

        try:
            r = client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
            })
        except Exception as e:
            err = str(e).lower()
            if "already" in err or "exists" in err or "duplicate" in err or "23000" in err:
                print(f"  {email} already exists, updating profile...")
                # Get user id from profiles (trigger creates profile with same id as auth user)
                try:
                    pr = client.table("profiles").select("id").eq("email", email).execute()
                    if pr.data and len(pr.data) > 0:
                        user_id = pr.data[0]["id"]
                        _update_profile_and_driver(client, user_id, email, role, name)
                except Exception as ex:
                    print(f"    Could not update: {ex}")
                continue
            print(f"  {email}: {e}")
            continue

        user_id = None
        if hasattr(r, "user") and r.user:
            usr = r.user
            user_id = getattr(usr, "id", None) or (usr.get("id") if isinstance(usr, dict) else None)
        if not user_id and hasattr(r, "model_dump"):
            data = r.model_dump()
            usr_data = data.get("user") or {}
            user_id = usr_data.get("id") if isinstance(usr_data, dict) else None
        if not user_id:
            print(f"  {email}: created but could not get user id, check Table Editor")
            continue

        _update_profile_and_driver(client, user_id, email, role, name)
        print(f"  {email} ({role}) created")

    print("Done. Sign in at http://127.0.0.1:8080/login.html")


def _update_profile_and_driver(client, user_id, email, role, name):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    # Update profile role (trigger creates with 'driver' default)
    try:
        client.table("profiles").update({"role": role, "email": email, "updated_at": now}).eq("id", user_id).execute()
    except Exception as e:
        print(f"    profiles update: {e}")

    if role in ("dispatcher", "admin"):
        try:
            client.table("dispatcher_profiles").upsert(
                {"user_id": user_id, "name": name or ("Admin" if role == "admin" else "Dispatcher")},
                on_conflict="user_id",
            ).execute()
        except Exception as e:
            print(f"    dispatcher_profiles: {e}")

    if role == "driver":
        try:
            existing = client.table("driver_profiles").select("id").eq("user_id", user_id).execute()
            if not (existing.data and len(existing.data) > 0):
                client.table("driver_profiles").insert(
                    {"user_id": user_id, "name": name or "Driver", "status": "off_duty"}
                ).execute()
        except Exception as e:
            print(f"    driver_profiles: {e}")


if __name__ == "__main__":
    main()
