# Phase 0 — Geomapper Baseline (Pre-Build)

**Purpose:** Document current behavior before any plan.md changes. Use this to verify "unchanged" after modifications.

**Created:** 2026-03-14

---

## 0.1 Current Endpoints

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/` | Static | Serves `web/index.html` |
| GET | `/api/config` | API | Returns `{ mapsApiKey }` from config.json (or google_api_key_path) |
| GET | `/api/routes` | API | Returns `data/routes.json` as JSON array |
| GET | `/api/drivers` | API | Returns `data/drivers.json` as JSON array |
| GET | `/api/poll/status` | API | Returns last poll stats (added, skipped_sender, etc.) |
| PATCH | `/api/routes/:id` | API | Updates route `status` and/or `assigned_driver` in routes.json |
| POST | `/api/poll` | API | Triggers IMAP poll in background; returns `{ polled, in_background }`; throttled 15s |
| GET | `/*` (static) | Static | Serves files from `web/` (html, css, js, json, ico) |

---

## 0.2 Current Map Behaviors

| Behavior | Implementation |
|----------|----------------|
| **Opportunity markers** | `updateEndpointMarkers()`: green circle = origin, red circle = destination; from filtered routes; location filter (both/start/stop) controls which endpoints shown |
| **Heatmap** | `updateHeatmap()`: HeatmapLayer from filtered route origins + destinations; built from `filterRoutes()` + `getHeatmapPoints()` |
| **Zone circle** | `zoneCircle`, `zoneCenterMarker`: user clicks map or sidebar zone toggle; circle radius 25–200 mi; filters route cards and heatmap by `routeInZone()` |
| **Selected-route focus** | `focusRoute(route)`: clears previous focus; adds origin/dest markers; calls Directions API; draws blue polyline; fits bounds; shows `routeFocusSummary` with driving miles vs est. miles |
| **Clear route** | `clearRouteBtn`: calls `deselectRoute()` → clears `selectedRouteId`, polyline, markers, summary |

**Focus behavior:** `selectedRouteId` = id of focused market route. `clearFocus()` removes routeMarkers, focusPolyline, hides routeFocusSummary, hide clearRouteBtn.

---

## 0.3 Current Left Sidebar Behaviors

| Item | Behavior |
|------|----------|
| **Time filter** | `#timeFilter`: 1d, 2d, 5d...365d, all. Filters routes by `getRouteTimestamp()` vs `TIME_FILTERS` |
| **Route type filter** | `#routeTypeFilter`: All, Lead, Chase, High Pole, Survey, Flagger. Matches `route.route_types` |
| **Map locations filter** | `#locationFilter`: both, start, stop. Controls heatmap/endpoint markers only |
| **Zone filter** | `#zoneToggleSidebar`, `#zoneToggle` (map toolbar): toggle zone mode; radius select; click map to set center; Clear zone |
| **Route cards** | `#routeCards`: rendered from `filterRoutes()`; sorted by recency, then route line. Click card → select route, focus on map, PATCH status to viewed |
| **Route focus summary** | `#routeFocusSummary`: shown when route focused; driving miles vs est; within-range check |
| **Refresh** | `#refreshBtn`: POST `/api/poll`; shows poll status; refetches routes |
| **Poll status** | `#pollStatus`: shows poll result message (8s timeout) |

**Click route on left:** Sets `selectedRouteId`, calls `focusRoute(r)`, PATCH status to viewed, shows Clear route button.

---

## 0.4 routes.json Schema (Poller Output)

Source: `poller.py` → `data/routes.json`. Read by: server `GET /api/routes`, app.js `loadData()` + `poll()`.

```json
{
  "id": "string (16-char hash)",
  "origin": "City, ST",
  "destination": "City, ST",
  "origin_detail": "optional address",
  "dest_detail": "optional address",
  "origin_lat": number,
  "origin_lng": number,
  "dest_lat": number,
  "dest_lng": number,
  "miles": number | null,
  "routed_miles": number | null,
  "company": "string",
  "chase": "origin to destination line",
  "date": "MM/DD or MM/DD/YY",
  "phone": "string",
  "phone_text_only": boolean,
  "pay": "string",
  "dot": "string",
  "mc": "string",
  "route_types": ["Lead","Chase",...],
  "status": "new" | "viewed",
  "posted_at": "ISO8601"
}
```

**Poller:** `poller.py` polls IMAP (config: imap_*), parses Load Alert emails, geocodes via Google API, appends to routes.json. Uses `poll_state.json` for last_seen_uid.

---

## 0.5 drivers.json Schema

Source: `data/drivers.json`. Read by: server `GET /api/drivers`, app.js `loadData()`.

Currently loaded but **not displayed** in UI. Plan Phase 2 will add right sidebar driver list.

Expected shape (for future): array of `{ id, name, ... }`. Current file may be `[]` or placeholder.

---

## 0.6 Regression Checklist

After any change, verify:

- [ ] **Left sidebar:** Time, Route type, Map locations filters work
- [ ] **Left sidebar:** Zone filter toggle, radius, click-to-set, Clear work
- [ ] **Route cards:** Load from /api/routes; filter correctly; sort by recency
- [ ] **Click route card:** Selects route; focus polyline on map; route focus summary shows; status PATCH to viewed
- [ ] **Clear route:** Clears selection and focus
- [ ] **Refresh:** Triggers poll; poll status shows; routes refresh
- [ ] **Map:** Opportunity markers (green/red), heatmap, zone circle render
- [ ] **Poller:** Unchanged; still writes to routes.json; server still serves routes from JSON

---

## 0.7 Focus Behavior (app.js)

- **selectedRouteId:** Single route id or null. Only one route "focused" at a time.
- **Setting selectedRouteId:** Card click handler; also clears on deselect.
- **clearFocus():** Removes routeMarkers, focusPolyline; hides routeFocusSummary and clearRouteBtn.
- **deselectRoute():** Sets selectedRouteId = null; calls clearFocus(); renderCards().

**No driver focus yet.** Plan adds `driver_assignment` focus mode; selecting driver will clear market_route highlight (and vice versa). Current app has only market_route focus.

---

## 0.8 Files to Preserve

| File | Do not |
|------|--------|
| `server.py` | Replace entire handler; extend for new routes only |
| `poller.py` | Do not change IMAP/email/geocode flow |
| `web/index.html` | Do not remove left sidebar; add right sidebar as new nodes |
| `web/js/app.js` | Prefer extend; add new layers, do not rewrite map/left logic |
| `web/css/style.css` | Add new styles; preserve existing |

---

*End of baseline. Use when implementing plan.md phases.*
