import json
import urllib.request

q = """
[out:json][timeout:25];
way["highway"]["ref"="AR 151"](around:40000,33.42,-94.05);
out geom 8;
"""
req = urllib.request.Request(
    "https://overpass-api.de/api/interpreter",
    data=q.encode(),
    headers={
        "User-Agent": "GeomapperFix/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)
with urllib.request.urlopen(req, timeout=60) as r:
    d = json.loads(r.read().decode())
for e in d.get("elements", []):
    g = e.get("geometry", [])
    if not g:
        continue
    print("way", e["id"], "pts", len(g))
    for label, i in (("S", 0), ("mid", len(g) // 2), ("N", -1)):
        p = g[i]
        print(f"  {label}", p["lat"], p["lon"])
