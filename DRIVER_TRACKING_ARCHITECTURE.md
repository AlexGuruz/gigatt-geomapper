# Driver Tracking & Hybrid Capacitor App — Architecture Reference

This document is the single reference for building the driver mobile app, auth, and Geomapper integration. Use it when planning and implementing the system.

---

## 1. Driver experience: install and go

### What the flow looks like

With a **Capacitor-based** mobile app, the driver flow is:

1. Install **TestFlight** from the App Store (if not already installed).
2. Tap your **invite link** or accept your invite.
3. Install your **driver app** from TestFlight.
4. **Sign in** with the account you assign.
5. Grant **Location** permission (and ideally **Always Allow** if tracking needs background updates).
6. Start using the app; location is sent to the backend.

So: **one link → install TestFlight → install app → sign in → allow location → done.** It is not a single “click a web link and it installs like a website” — on iPhone you go through TestFlight (or a company-managed distribution path). TestFlight is the simplest practical option; Apple supports both email invites and public links for external testers.

### What Capacitor changes

Capacitor is a **native iOS/Android runtime** for apps built from web code. It gives you:

- A real native app (not a Safari tab or PWA).
- Native permissions (e.g. Location, Background Modes).
- Native plugins for location, so tracking can work when the app is in background, screen locked, or user is in Maps.

So: **background tracking is not automatic.** You must:

- Configure the app for **background location** (e.g. `UIBackgroundModes` with `location` on iOS).
- Have the user grant the **right permission** (e.g. “Always” for background).
- Implement **reliable background location handling** and **periodic sync** of GPS + timestamp to your backend.

### Recommended driver rollout

- Send each driver a **TestFlight invite** (or public link).
- They install TestFlight → install your driver app → sign in → approve location.
- Build the driver app for:
  - **Background location updates**
  - **App relaunch/resume** handling
  - **Periodic backend sync** of GPS + timestamp
  - Clear **“tracking on / off”** in the UI

---

## 2. Auth subsystem: accounts and login

You need a real auth subsystem so drivers and dispatchers have stable identities and sessions.

### What you need

| Need | Description |
|------|-------------|
| **User accounts** | Each person (driver, dispatcher, later admin) has an identity: user id, name, email/phone, role, active status, link to driver or dispatcher profile. |
| **Login** | Sign in again later and stay tied to the same account (email+password, magic link, or e.g. Google sign-in). |
| **Sessions** | After sign-in, the app has a session/token so the backend knows who is making the request and what role they have. |
| **Authorization** | Server enforces what each role can do (e.g. driver: own location + own assignment; dispatcher: all drivers; admin: users + settings). |

Do **not**: hardcode one shared password, let drivers type any name and post location, or trust the device to say “I am driver 12” without auth. Use a **managed auth provider** (e.g. Supabase Auth or Firebase Auth), not hand-rolled password/session logic.

### Recommended v1

- **Managed auth:** Supabase Auth or Firebase Auth (handles sign-in, tokens, password reset).
- **Database:** e.g. Supabase Postgres with `users`, `driver_profiles`, `dispatcher_profiles`, and optionally `sessions` (or rely on provider).
- **Roles:** `driver`, `dispatcher`, `admin`.
- **Flows:** invite user → create account → sign in → stay signed in → sign out → password reset / re-invite → disable account.

Auth is one subsystem used by **both** the driver app and the dispatcher (Geomapper) web app.

---

## 3. Overall setup: three pieces

Think of the system as **three pieces** that work together.

### 1) Driver mobile app (Capacitor)

- **What it is:** Capacitor-wrapped web app built as iOS and Android apps.
- **Responsibilities:**
  - Sign the driver in.
  - Request location permission (and “Always” when needed).
  - Run location tracking (including background where supported).
  - Send GPS updates to the backend (e.g. `driverId`, `lat`, `lng`, `timestamp`, optional `speed`, `heading`, `battery`).
  - Show the driver only what they need (e.g. assignment, status, “tracking on/off”).

### 2) Backend / auth / database

- **What it is:** API + auth + database (e.g. Supabase: Auth + Postgres).
- **Responsibilities:**
  - Authenticate drivers and dispatchers (same auth for both apps).
  - Store users, roles, drivers, dispatchers, routes, assignments, and latest locations.
  - Accept **location updates** from the driver app.
  - Return **driver positions and route data** to the dispatcher app.
  - Enforce **who can see what** (e.g. Row Level Security in Postgres).

### 3) Dispatcher / Geomapper web app

- **What it is:** Your existing (or upgraded) Geomapper — browser-based.
- **Responsibilities:**
  - Dispatcher sign-in.
  - Driver list, map, route overlays, statuses, timestamps.
  - Assign routes and monitor movement.
  - Optional: layers, filters, reporting.

So: **Geomapper is the dispatcher-facing half;** the driver app is the other half. Both use the same backend and auth.

---

## 4. How to accomplish this (step by step)

### Step 1: Backend and identity model

Create core data:

- **users** (id, email, role, etc.)
- **roles** (e.g. driver, dispatcher, admin)
- **drivers** / **dispatcher_profiles**
- **routes**, **route_stops**, **driver_assignments**
- **location_updates** and something like **driver_last_location** for the map

Enforce access in the DB (e.g. Supabase RLS): e.g. driver can only write their own location and read their own assignment; dispatcher can read all active drivers and assignments.

### Step 2: One auth system for both apps

- Use **one** auth system (e.g. Supabase Auth) for:
  - Driver mobile app
  - Dispatcher web app (Geomapper)
- Flow: create/invite user → they sign in → they get a session (e.g. JWT) → both apps send that token on API requests → backend allows/denies by role.

### Step 3: Driver app in Capacitor

- Build the driver UI with your web stack (e.g. React/Vue/vanilla).
- Wrap it with **Capacitor** to produce:
  - **iOS app** (Xcode, TestFlight)
  - **Android app** (Play Store or direct APK)
- In the app:
  - Sign in (using the same auth as above).
  - Request location permission (and “Always” if you need background).
  - Start tracking and send updates to the backend, e.g.:

```json
{
  "driverId": "drv_123",
  "lat": 35.222,
  "lng": -97.439,
  "timestamp": "2026-03-14T23:10:00Z",
  "speed": 54,
  "heading": 182,
  "battery": 0.61
}
```

- On iOS, enable **background location** in the project (e.g. `UIBackgroundModes` + `location`) and configure Core Location for background updates.

### Step 4: Distribute the driver app

- **iPhone:** TestFlight (invite link or email). Drivers: install TestFlight → install your app → sign in → allow location.
- **Android:** TestFlight not needed; use Play Store (or internal testing) or direct APK install.

### Step 5: Add Geomapper into this system

- **Option A (recommended):** Geomapper **is** the dispatcher app. Connect it to the same backend and auth:
  - Dispatcher signs in.
  - Geomapper loads drivers and `driver_last_location` (and routes/assignments) from your API.
  - Map shows live positions; sidebar shows drivers and assignments.
- **Option B:** Share code (e.g. React components, API client, auth client) between a “driver app” build and a “dispatch app” build; both point to the same backend.

So: **yes, you can add your existing web app (Geomapper) into this** so dispatchers see the same Geomapper, now backed by real driver accounts and live location from the driver app.

---

## 5. Pushing updates: minimal manual change for drivers/dispatchers

### Backend and web (dispatcher) updates

- **API, database, Geomapper UI:** Deploy to your server; users get new behavior on next request or refresh. No reinstall. Supabase (and similar) sessions keep working across deploys.
- **Dispatcher experience:** They just refresh the Geomapper page; new features and layers appear.

### Driver mobile app updates

- **Web-layer changes inside Capacitor** (UI, text, some logic): Can often be delivered via a **live-update** mechanism (web content) if you use one, reducing how often you need a new native build.
- **Native-capability changes** (location, background behavior, new plugins, entitlements, push): Usually require a **new app build** distributed via TestFlight (iOS) or Play/APK (Android). TestFlight is built for pushing updated beta builds to testers.

### How to keep manual changes low

- **Thin driver app:** The app does a few stable things: sign in, session, collect/send location, show assignment/status. Move as much as possible to **backend**, **config**, and **web-rendered** or config-driven UI.
- **Feature flags / config tables:** e.g. `feature_flags`, `app_settings`, `role_permissions`, `map_layers`. Turn features on later without forcing every user to change settings or reinstall.
- **Stable core:** auth, users/roles, driver assignment, location ingestion, dispatcher map, basic event logging. **Extensible layers:** map overlays from DB, route metadata, custom statuses, alerts, notes, reporting.

Result: **most new features** (new map layers, statuses, reports, assignment rules) can be added with **backend + web** changes; drivers and dispatchers do little to nothing. Only when you change **native** behavior do drivers need to accept a new TestFlight (or store) update.

---

## 6. Cross-platform: Google (Android) and iPhone

The same architecture supports **both** Android and iPhone.

| Layer | Shared? | Notes |
|-------|--------|--------|
| **Backend** | Yes | Same API for all clients; doesn’t care if request is from iPhone, Android, or browser. |
| **Dispatcher (Geomapper)** | Yes | Web app; works on desktop, laptop, tablet, phone. |
| **Driver app** | Same codebase, two builds | Capacitor: one web codebase → iOS app + Android app. |

### Driver install by platform

- **iPhone:** TestFlight (or similar) → install app → sign in → allow location.
- **Android:** No TestFlight; install via Play Store, internal testing, or direct APK link. Often **easier** than iOS (e.g. “tap link → install”).

### Location on both

- **iPhone:** “Always allow” + background location capability in the app; user must grant the right permission.
- **Android:** Background location permission; on some devices you may need to guide users on battery optimization.

Capacitor and your backend handle both; the main differences are **build process**, **permissions**, and **background behavior tuning**, not the core app logic.

---

## 7. Minimal data flow (reference)

| Direction | Content |
|-----------|--------|
| **Driver app → backend** | Authenticated location updates; optional assignment status or check-in events. |
| **Backend → Geomapper** | Active drivers, last location, assigned route, last update time, status. |
| **Dispatcher actions → backend** | Assign route, set driver active/inactive, future: instructions, notes. |

---

## 8. Build order (phases)

| Phase | Focus |
|------|--------|
| **1. Foundation** | Supabase (or equivalent) project; auth; `users` + roles; drivers/dispatchers tables; simple login in web app. |
| **2. Dispatcher** | Connect Geomapper to auth; load drivers and `driver_last_location` from API; show markers and route assignments. |
| **3. Driver app** | Small web UI → Capacitor; iOS (and Android) build; location permission flow; background location; POST location to backend. |
| **4. Rollout** | Publish to TestFlight (and Android channel); invite a few test drivers; verify install → login → permission → background updates → map updates in Geomapper. |

---

## 9. Summary

- **Driver experience:** One link (TestFlight invite) → install app → sign in → allow location. Not “one web link installs everything,” but close; background tracking requires correct native setup and permissions.
- **Auth:** One subsystem (e.g. Supabase Auth + Postgres), shared by driver app and Geomapper; real accounts, login, and sessions; backend enforces roles.
- **Setup:** Driver app (Capacitor) + backend (auth + DB + API) + Geomapper (dispatcher web app). Geomapper is the dispatch UI; it can be your existing web app wired to this backend.
- **Updates:** Backend and Geomapper = deploy and refresh. Driver app = web-only changes can sometimes ship via live update; native changes need a new build (TestFlight/Play/APK). Keep the driver app thin and logic on the backend so most new features don’t require driver action.
- **Cross-platform:** Same backend and Geomapper; one Capacitor codebase for iOS and Android driver app. Works on both Google (Android) and iPhone.

Use this document as the single reference while building the plan and the app.
