#!/usr/bin/env python3
"""
Arkansas DOT OSOW Permit ID 3866904 — permit-faithful path.

The PDF lists **every** highway transition in order. A single OSRM request with
sparse anchors can pick different alternates between stops. This script:

1. Defines one coordinate per **permit clause** (same order as the PDF).
2. Chains **many short OSRM legs** (each leg = only the next junction pair) and
   concatenates the GeoJSON geometry → authoritative GPX / polyline.
3. Builds a Google Maps URL by **sampling that merged polyline** (≤23 internal
   waypoints, Google’s practical limit) plus origin/destination — so Google
   follows the same corridor, not a fresh optimization through a handful of pins.

Google still may tweak between samples; for legal trace use the GPX track.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

USER_AGENT = "GeomapperARPermit3866904/1.0 (contact: permit routing)"
OSRM_BASE = "https://router.project-osrm.org"

# (lat, lon), label — order MUST match the ROUTE paragraph on the permit.
PERMIT_JUNCTIONS: list[tuple[tuple[float, float], str]] = [
    ((33.3857082, -94.0429481), "AR-151 @ Miller MP 0 / TX line (OSM)"),
    ((33.3920313, -94.0147969), "AR-151 NE toward Texarkana (OSM)"),
    ((33.4385000, -94.0045000), "I-49 NB corridor, Texarkana (snap)"),
    ((33.4580000, -93.9985000), "US-82 EB, Texarkana (snap)"),
    ((33.4656827, -93.9869541), "AR-237 NB, Texarkana (OSM AR-237)"),
    ((33.4850000, -93.9750000), "US-67 NEB after Texarkana stack (snap)"),
    ((33.5200000, -93.9450000), "US-67 N, leaving Texarkana (snap)"),
    ((33.6420000, -93.5850000), "AR-29B / US-67 area, Hope (snap)"),
    ((33.6520000, -93.5820000), "AR-29 corridor, Hope (snap)"),
    ((33.6600000, -93.5750000), "US-278 NB, Hope (snap)"),
    ((33.6713935, -93.5656762), "US-67 NEB, Hope (Nominatim)"),
    ((33.7991895, -93.3824600), "US-371 / AR-24, Prescott"),
    ((33.8015000, -93.4200000), "AR-19 NB, Prescott (snap)"),
    ((33.7999478, -93.4382689), "I-30 EB northerly, Prescott"),
    ((34.1200170, -93.0805380), "AR-51 / I-30 Exit 54, Clark Co."),
    ((33.8887161, -93.2040588), "US-67 NEB, Beirne"),
    ((34.0250000, -93.1100000), "AR-26 NWB, Gum Springs (snap)"),
    ((34.0647673, -93.0973621), "I-30 EB northerly, Gum Springs"),
    ((34.2251440, -92.9996170), "AR-283 / I-30 Exit 83, Friendship"),
    ((34.2204186, -93.0095060), "US-67 NEB, Friendship"),
    ((34.5638595, -92.6050946), "I-30 EB westerly, Benton"),
    ((34.7820000, -92.4180000), "I-430 NB corridor (snap)"),
    ((34.8499140, -92.4000610), "I-40 WB @ end I-430, Maumelle (snap)"),
    ((35.0200000, -91.9450000), "US-64 EB east of Little Rock (snap)"),
    ((35.0598395, -91.9295811), "I-57 NEB / US-67, Beebe"),
    ((35.8200000, -91.6800000), "US-167 NB, north of Beebe (snap)"),
    ((36.2267452, -91.6075282), "US-62 NEB, Ash Flat"),
    ((36.3218485, -91.4892617), "US-63B / US-63, Hardy"),
    ((36.3400000, -91.5050000), "US-63 NB northerly, Hardy (snap)"),
    ((36.4933225, -91.5358684), "US-63 @ Fulton MP 0 / MO line (Mammoth Spring)"),
]


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371000.0
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * r * asin(min(1.0, sqrt(h)))


def osrm_route_two(a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
    coord_str = f"{a[1]},{a[0]};{b[1]},{b[0]}"
    url = f"{OSRM_BASE}/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode())
        if data.get("code") != "Ok" or not data.get("routes"):
            return []
        coords = data["routes"][0]["geometry"]["coordinates"]
        return [(lat, lon) for lon, lat in coords]
    except Exception:
        return []


def chain_osrm_track(junctions: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for i in range(len(junctions) - 1):
        seg = osrm_route_two(junctions[i], junctions[i + 1])
        if not seg:
            print(f"OSRM leg failed {i}→{i+1}, using straight tie")
            seg = [junctions[i], junctions[i + 1]]
        if merged and seg:
            if haversine_m(merged[-1], seg[0]) < 3:
                seg = seg[1:]
        merged.extend(seg)
    return merged


def sample_polyline_max_waypoints(
    pts: list[tuple[float, float]],
    max_internal: int,
    origin: tuple[float, float],
    dest: tuple[float, float],
) -> list[tuple[float, float]]:
    """Pick up to max_internal points along pts, excluding corridor near origin/dest."""
    if not pts or max_internal <= 0:
        return []
    # cumulative distance
    dists = [0.0]
    for i in range(1, len(pts)):
        dists.append(dists[-1] + haversine_m(pts[i - 1], pts[i]))
    total = dists[-1]
    if total < 1000:
        return []
    targets = [total * (k + 1) / (max_internal + 1) for k in range(max_internal)]
    out: list[tuple[float, float]] = []
    ti = 0
    for t in targets:
        while ti + 1 < len(dists) and dists[ti + 1] < t:
            ti += 1
        if ti + 1 >= len(pts):
            break
        # linear interp between pts[ti] and pts[ti+1]
        d0, d1 = dists[ti], dists[ti + 1]
        frac = 0.5 if d1 <= d0 else (t - d0) / (d1 - d0)
        frac = max(0.0, min(1.0, frac))
        lat = pts[ti][0] + frac * (pts[ti + 1][0] - pts[ti][0])
        lon = pts[ti][1] + frac * (pts[ti + 1][1] - pts[ti][1])
        p = (lat, lon)
        if haversine_m(p, origin) < 1200 or haversine_m(p, dest) < 1200:
            continue
        if not out or haversine_m(out[-1], p) > 2500:
            out.append(p)
    return out[:max_internal]


def google_maps_dir_url(
    origin: tuple[float, float],
    destination: tuple[float, float],
    waypoints: list[tuple[float, float]],
) -> str:
    def fmt(ll: tuple[float, float]) -> str:
        return f"{ll[0]:.6f},{ll[1]:.6f}"

    params: dict[str, str] = {
        "api": "1",
        "origin": fmt(origin),
        "destination": fmt(destination),
        "travelmode": "driving",
    }
    if waypoints:
        params["waypoints"] = "|".join(fmt(p) for p in waypoints)
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)


def write_gpx(path: Path, coords: list[tuple[float, float]], name: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            '<gpx version="1.1" creator="Geomapper AR 3866904" '
            'xmlns="http://www.topografix.com/GPX/1/1">\n'
        )
        f.write("  <trk><name>")
        f.write(name.replace("&", "&amp;").replace("<", "&lt;"))
        f.write("</name><trkseg>\n")
        for lat, lon in coords:
            f.write(f'    <trkpt lat="{lat}" lon="{lon}"></trkpt>\n')
        f.write("  </trkseg></trk>\n</gpx>\n")


def write_junction_csv(path: Path, junctions: list[tuple[float, float]]) -> None:
    lines = ["idx,lat,lon,label"]
    for i, ((_, _), lab) in enumerate(PERMIT_JUNCTIONS):
        lat, lon = junctions[i]
        lines.append(f'{i},{lat:.7f},{lon:.7f},"{lab.replace(chr(34), "")}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    base = Path(__file__).resolve().parent
    junctions = [ll for ll, _ in PERMIT_JUNCTIONS]
    write_junction_csv(base / "AR-3866904-permit-junctions.csv", junctions)

    print("Chaining OSRM legs (one leg per adjacent permit junction)…")
    track = chain_osrm_track(junctions)
    if len(track) < 10:
        print("Chained track short; falling back to single OSRM multi-stop.")
        coord_str = ";".join(f"{lon},{lat}" for lat, lon in junctions)
        url_full = f"{OSRM_BASE}/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
        req = urllib.request.Request(url_full, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode())
            if data.get("code") == "Ok" and data.get("routes"):
                coords = data["routes"][0]["geometry"]["coordinates"]
                track = [(lat, lon) for lon, lat in coords]
        except Exception as e:
            print("Fallback failed:", e)

    o, d = junctions[0], junctions[-1]
    google_wp = sample_polyline_max_waypoints(track, 23, o, d)

    url = google_maps_dir_url(o, d, google_wp)
    (base / "AR-3866904-Google-Maps-URL.txt").write_text(url + "\n", encoding="utf-8")
    write_gpx(
        base / "AR-3866904-route-TRACK.gpx",
        track,
        "AR 3866904 chained OSRM legs (permit clause order)",
    )
    print(f"Track points: {len(track)}  Google vias: {len(google_wp)}")
    print("Wrote", base / "AR-3866904-Google-Maps-URL.txt")
    print("Wrote", base / "AR-3866904-route-TRACK.gpx")
    print("Wrote", base / "AR-3866904-permit-junctions.csv")


if __name__ == "__main__":
    main()
