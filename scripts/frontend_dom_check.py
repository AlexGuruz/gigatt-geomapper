import requests


def page_contains(base_url: str, path: str, required_substrings: list[str]) -> tuple[bool, list[str], int]:
    url = base_url.rstrip("/") + path
    r = requests.get(url, timeout=20)
    html = r.text
    missing = [s for s in required_substrings if s not in html]
    ok = r.status_code < 400 and not missing
    return ok, missing, r.status_code


def main():
    base_url = "http://127.0.0.1:8086"

    checks = [
        (
            "/",
            [
                'id="app"',
                'id="sidebar"',
                'id="mapContainer"',
                'id="rightSidebar"',
            ],
        ),
        (
            "/login.html",
            [
                'id="loginForm"',
                'id="email"',
                'id="password"',
                'id="submitBtn"',
                "backend-connect",
            ],
        ),
        (
            "/driver.html",
            [
                'id="driverAssignmentCard"',
                'id="signOutBtn"',
                'id="locationStatus"',
                "class=\"driver-portal\"",
            ],
        ),
    ]

    print("Frontend DOM hook check")
    print("Base:", base_url)
    print()

    all_ok = True
    for path, required in checks:
        ok, missing, status = page_contains(base_url, path, required)
        if ok:
            print(f"PASS {path} (HTTP {status})")
        else:
            all_ok = False
            print(f"FAIL {path} (HTTP {status}) missing={missing}")

    print()
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

