#!/usr/bin/env python
"""
Run Phase 3, 5, 7 API smoke tests; optionally Phase 6 if GEOMAPPER_DRIVER_ID is set.
Usage: python scripts/run_api_tests.py [BASE_URL]
Example: python scripts/run_api_tests.py http://127.0.0.1:8080

Ensure the server is running (python server.py). Supabase must be configured for Phase 5 and full Phase 3.
See TESTING.md for details.
"""
import os
import subprocess
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BASE = BASE.rstrip("/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER_ID = os.environ.get("GEOMAPPER_DRIVER_ID")


def main():
    results = []
    # Phase 3
    print("=" * 50)
    print("Phase 3 API smoke test")
    print("=" * 50)
    r3 = subprocess.run([sys.executable, "scripts/test_phase3_api.py", BASE], cwd=ROOT)
    results.append(r3.returncode == 0)
    print()
    # Phase 5
    print("=" * 50)
    print("Phase 5 API smoke test")
    print("=" * 50)
    r5 = subprocess.run([sys.executable, "scripts/test_phase5_api.py", BASE], cwd=ROOT)
    results.append(r5.returncode == 0)
    print()
    # Phase 6 (optional)
    if DRIVER_ID:
        print("=" * 50)
        print("Phase 6 batch idempotency test")
        print("=" * 50)
        r6 = subprocess.run([sys.executable, "scripts/test_phase6_batch_idempotency.py", BASE, DRIVER_ID], cwd=ROOT)
        results.append(r6.returncode == 0)
        print()
    else:
        print("(Phase 6 skipped: set GEOMAPPER_DRIVER_ID to run batch idempotency)")
        print()
    # Phase 7
    print("=" * 50)
    print("Phase 7 API smoke test (jobs near driver)")
    print("=" * 50)
    r7 = subprocess.run([sys.executable, "scripts/test_phase7_api.py", BASE], cwd=ROOT)
    results.append(r7.returncode == 0)
    print()
    ok = all(results)
    print("Overall:", "PASS" if ok else "See failures above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
