#!/usr/bin/env python3
"""
MoDOT OSOW Single Trip #26084050401 — Google Maps + GPX from permit text.

Authorized route (per PDF):
  START: US-63 N at the Missouri–Arkansas state line
  END:   US-63, 1.82 miles north of US-63 / Route PP (Howell Co., near West Plains)

Also builds a second link: staging from Milton, Randolph County, MO (per user request),
then OSRM driving route to the permit north terminus, with MoDOT endpoints forced in.

No API keys. OSRM (router.project-osrm.org) + public Overpass for PP junction geometry.

Re-run after verifying coordinates against the signed permit / field check.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

USER_AGENT = "GeomapperMOPermitRoute/1.0 (contact: permit routing)"
OSRM_BASE = "https://router.project-osrm.org"

# Staging origin: Milton, Randolph County, MO (Nominatim)
MILTON_MO = (39.4700363, -92.3290684)

# US-63 at MO–AR line (OSRM nearest snap ~36.488,-91.540)
BORDER_US63 = (36.487929, -91.539914)

# US-63 ∩ MO Route PP, Howell County (Overpass way 18500637 endpoint)
PP_US63 = (36.689959, -91.795028)

# 1.82 statute miles north along US-63 from PP_US63 (via OSRM geometry walk)
NORTH_TERM = (36.70755616899664, -91.8193783755488)


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371000.0
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * r * asin(min(1.0, sqrt(h)))


def osrm_route(coords: list[tuple[float, float]]) -> dict | None:
    if len(coords) < 2:
        return None
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"{OSRM_BASE}/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
        if data.get("code") != "Ok" or not data.get("routes"):
            print("OSRM route error:", data.get("code"), data.get("message", ""))
            return None
        return data
    except Exception as e:
        print("OSRM route failed:", e)
        return None


def geometry_to_latlons(data: dict) -> list[tuple[float, float]]:
    geom = data["routes"][0]["geometry"]
    if geom["type"] != "LineString":
        return []
    return [(lat, lon) for lon, lat in geom["coordinates"]]


def sample_polyline(
    pts: list[tuple[float, float]], step_m: float
) -> list[tuple[float, float]]:
    if not pts:
        return []
    out = [pts[0]]
    acc = 0.0
    i = 1
    cur = list(pts[0])
    while i < len(pts):
        nxt = pts[i]
        seg = haversine_m(tuple(cur), nxt)
        if acc + seg < step_m:
            acc += seg
            cur = list(nxt)
            i += 1
            continue
        need = step_m - acc
        frac = need / seg if seg else 0.0
        lat = cur[0] + frac * (nxt[0] - cur[0])
        lon = cur[1] + frac * (nxt[1] - cur[1])
        out.append((lat, lon))
        cur = [lat, lon]
        acc = 0.0
    if haversine_m(out[-1], pts[-1]) > 800:
        out.append(pts[-1])
    else:
        out[-1] = pts[-1]
    return out


def insert_near(
    chain: list[tuple[float, float]],
    extra: list[tuple[float, float]],
    min_m: float = 2500.0,
) -> list[tuple[float, float]]:
    for e in extra:
        if not chain or min(haversine_m(e, p) for p in chain) > min_m:
            chain.append(e)
    return chain


def merge_ordered_along_polyline(
    poly: list[tuple[float, float]],
    must_have: list[tuple[float, float]],
    step_m: float,
) -> list[tuple[float, float]]:
    """Sample polyline (excluding endpoints), insert must_have points by closest segment index."""
    if len(poly) < 2:
        return list(must_have)
    sampled = sample_polyline(poly, step_m)
    inner = sampled[1:-1] if len(sampled) > 2 else []
    # cumulative distance along poly for ordering inserts
    cum: list[float] = [0.0]
    for i in range(1, len(poly)):
        cum.append(cum[-1] + haversine_m(poly[i - 1], poly[i]))

    def proj_dist(p: tuple[float, float]) -> float:
        best = 0.0
        best_d = float("inf")
        for i in range(len(poly) - 1):
            a, b = poly[i], poly[i + 1]
            seg = haversine_m(a, b)
            if seg < 1:
                continue
            # distance to segment (approx: min to endpoints)
            d = min(haversine_m(p, a), haversine_m(p, b))
            if d < best_d:
                best_d = d
                best = cum[i] + min(haversine_m(p, a), seg * 0.5)
        return best

    tagged: list[tuple[float, tuple[float, float]]] = [(proj_dist(p), p) for p in inner]
    for p in must_have:
        tagged.append((proj_dist(p), p))
    tagged.sort(key=lambda x: x[0])
    out = [p for _, p in tagged]
    # dedupe close neighbors
    deduped: list[tuple[float, float]] = []
    for p in out:
        if not deduped or haversine_m(deduped[-1], p) > 1200:
            deduped.append(p)
    return deduped


def google_maps_dir_url(
    origin: tuple[float, float],
    destination: tuple[float, float],
    waypoints: list[tuple[float, float]],
    max_via: int = 23,
) -> str:
    """https://developers.google.com/maps/documentation/urls/get-started#directions-action"""
    via = [
        p
        for p in waypoints
        if haversine_m(p, origin) > 800 and haversine_m(p, destination) > 800
    ]
    # drop dupes consecutive
    slim: list[tuple[float, float]] = []
    for p in via:
        if not slim or haversine_m(slim[-1], p) > 400:
            slim.append(p)
    if len(slim) > max_via:
        step = max(1, len(slim) // max_via)
        slim = slim[::step][:max_via]
    o = f"{origin[0]},{origin[1]}"
    d = f"{destination[0]},{destination[1]}"
    if not slim:
        return (
            f"https://www.google.com/maps/dir/?api=1&origin={o}&destination={d}"
            f"&travelmode=driving"
        )
    w = "|".join(f"{lat},{lon}" for lat, lon in slim)
    w_enc = urllib.parse.quote(w, safe="")
    return (
        f"https://www.google.com/maps/dir/?api=1&origin={o}&destination={d}"
        f"&waypoints={w_enc}&travelmode=driving"
    )


def write_gpx_track(
    path: Path, coords: list[tuple[float, float]], name: str
) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            '<gpx version="1.1" creator="Geomapper MO 26084050401" '
            'xmlns="http://www.topografix.com/GPX/1/1">\n'
        )
        f.write("  <trk><name>")
        f.write(name.replace("&", "&amp;").replace("<", "&lt;"))
        f.write("</name><trkseg>\n")
        for lat, lon in coords:
            f.write(f'    <trkpt lat="{lat}" lon="{lon}"></trkpt>\n')
        f.write("  </trkseg></trk>\n</gpx>\n")


def main() -> None:
    base = Path(__file__).resolve().parent

    # --- Authorized segment only: border → PP → north terminus ---
    seg = osrm_route([BORDER_US63, PP_US63, NORTH_TERM])
    permit_track: list[tuple[float, float]] = []
    if seg:
        permit_track = geometry_to_latlons(seg)
    if not permit_track:
        permit_track = [BORDER_US63, PP_US63, NORTH_TERM]

    permit_waypoints = sample_polyline(permit_track, step_m=25_000)
    permit_waypoints = insert_near(permit_waypoints, [PP_US63], min_m=1500)

    url_permit = google_maps_dir_url(
        BORDER_US63, NORTH_TERM, permit_waypoints[1:-1]
    )
    (base / "MO-26084050401-permit-only-Google-Maps-URL.txt").write_text(
        url_permit + "\n", encoding="utf-8"
    )

    # --- Full trip: Milton MO → north terminus (staging; not all miles on this permit) ---
    full = osrm_route([MILTON_MO, NORTH_TERM])
    full_track = geometry_to_latlons(full) if full else []
    if not full_track:
        full_track = [MILTON_MO, NORTH_TERM]

    via = merge_ordered_along_polyline(
        full_track, [BORDER_US63, PP_US63], step_m=52_000
    )
    url_full = google_maps_dir_url(MILTON_MO, NORTH_TERM, via)

    (base / "MO-26084050401-from-Milton-Google-Maps-URL.txt").write_text(
        url_full + "\n", encoding="utf-8"
    )

    write_gpx_track(
        base / "MO-26084050401-permit-segment-TRACK.gpx",
        permit_track,
        "26084050401 US-63 authorized segment (border to 1.82mi N of PP)",
    )
    write_gpx_track(
        base / "MO-26084050401-Milton-to-north-TRACK.gpx",
        full_track,
        "26084050401 Milton MO to north terminus (OSRM full drive)",
    )

    print("Wrote:")
    print(" ", base / "MO-26084050401-permit-only-Google-Maps-URL.txt")
    print(" ", base / "MO-26084050401-from-Milton-Google-Maps-URL.txt")
    print(" ", base / "MO-26084050401-permit-segment-TRACK.gpx")
    print(" ", base / "MO-26084050401-Milton-to-north-TRACK.gpx")
    print("\nPermit-only URL (first 120 chars):\n", url_permit[:120], "...")


if __name__ == "__main__":
    main()
