# Hybrid Capacitor App — Build Plan & Reference

**Purpose:** Single reference for building the **role-based** driver-tracking + dispatcher (Geomapper) system: Capacitor mobile app for drivers, Supabase backend, and Geomapper web app for dispatch. Auth and role-based routing are core architecture.

---

## 1. Overview

- **One system, role-based views.** After login, the UI and route depend on the user's role (driver, dispatcher, admin).
- **Driver app:** Capacitor-based iPhone (and Android) app. Drivers install via TestFlight (iOS) or link/APK (Android), sign in, grant location. They land on a **driver portal** (assignment, permits, navigation, availability calendar, profile), not the dispatcher map. App reports GPS to backend.
- **Backend:** Auth, users, roles, drivers, assignments, location updates, availability. Supabase Auth + Postgres.
- **Dispatcher app:** Geomapper. Dispatchers land here after login: left sidebar (opportunity), right sidebar (dispatch), map. Driver availability from calendar feeds assignment flow.
- **Admin:** Same dispatcher view plus admin tools (manage users, roles, settings, devices).

**Important:** Auth is not an afterthought. Login defines what data each user sees, what page they land on, and what APIs they can call. Backend authorization must enforce access.

---

## 2. Role-Based Post-Login Routing

| Role | Lands on |
|------|----------|
| **Driver** | Driver portal (`/driver`) — focused task page, assignment card, permits, navigation, availability calendar, profile |
| **Dispatcher** | Geomapper (`/dispatch`) — opportunity layer + dispatch layer |
| **Admin** | Dispatcher view + admin tabs (`/admin/users`, `/admin/settings`, etc.) |

Do not dump drivers into the dispatcher map. They need a focused portal.

---

## 3. Driver Experience (Install & Use)

### iOS (iPhone)

1. Install **TestFlight** from the App Store (if not already).
2. Tap your **invite link** or accept invite email.
3. Install **your driver app** from TestFlight.
4. **Sign in** with the account you assign.
5. **Grant Location** (and ideally "Always Allow" if you need background tracking).
6. Land on **driver portal** — current assignment, permits, navigation link, availability calendar, profile.

**Reality:** Not a plain web link. TestFlight (or similar) is the normal path without a full public App Store release.

### Android

- No TestFlight. Drivers install via **direct link**, **Play Store**, or **internal testing**. Often simpler than iOS.

### What "bam done" means

- **Install/sign-in/permissions:** Yes — one invite link, install app, sign in, allow location, land on driver portal.
- **Background tracking:** No — not automatic. Requires proper **background location** (Capacitor + native config) and "Always Allow" where needed.

---

## 4. Auth Subsystem (Required)

Auth is **core architecture**. You need:

| Piece | Purpose |
|-------|--------|
| **User accounts** | id, name, email/phone, role (driver/dispatcher/admin), active, link to driver or dispatcher profile. |
| **Login** | Sign in; stay tied to same account. |
| **Sessions** | Token so backend knows who is calling and their role. |
| **Authorization** | Backend enforces: driver only own data; dispatcher sees drivers; admin manages users. |

**Do not:** Frontend-only role protection (hiding buttons). Backend must enforce.

---

## 5. Architecture: Three Pieces

### 5.1 Driver mobile app (Capacitor)

- **Responsibilities:**
  - Sign in; land on driver portal (not dispatcher map).
  - Current assignment card; permit links/summaries; navigation (Google Maps with disclaimer); availability calendar; profile.
  - Location permission + background; send batched GPS to backend.

### 5.2 Backend (auth + database + API)

- **Responsibilities:**
  - Auth, users, roles, drivers, assignments, availability, location.
  - Role-based API enforcement.
  - Driver can only read/update own data; dispatcher reads all drivers; admin manages.

### 5.3 Dispatcher / Geomapper web app

- **Responsibilities:**
  - Dispatcher sign-in; land on `/dispatch`.
  - Left sidebar (opportunity); right sidebar (drivers, assignments, permits, availability from driver calendar).
  - Map with driver markers and route overlays.

---

## 6. Driver Portal Content (What Drivers See)

- **Current assignment card:** Status, route, origin/destination, ETA, dispatcher contact, notes.
- **Permit documents:** View original; view summary; restrictions; escort requirements.
- **Navigation:** Open in Google Maps (with disclaimer: "Follow permit-approved route and restrictions").
- **Availability calendar:** Mark available/unavailable/limited per day; optional note. Feeds dispatcher planning.
- **Profile:** Name, phone, email.

Drivers do **not** see: other drivers, dispatcher tools, unassigned jobs, or the full map.

---

## 7. How Availability Feeds Dispatch

Driver calendar availability flows into dispatcher UI:

- **Driver cards:** Show available today, unavailable, limited, next available.
- **Assignment flow:** Filter/sort by driver status, projected availability, calendar availability, distance, freshness.
- **Map filters:** Only available drivers, available this week, etc.

---

## 8. Build Phases (Suggested Order)

| Phase | Focus |
|-------|--------|
| **1. Foundation** | Supabase; auth; tables; role-based post-login routing; driver → `/driver`, dispatcher → `/dispatch`. |
| **2. Dispatcher** | Connect Geomapper to auth; load drivers; right sidebar; map markers; driver availability from calendar. |
| **3. Driver app** | Capacitor; driver portal (assignment, permits, nav, calendar, profile); location + background. |
| **4. Admin** | Admin tabs; manage users, roles, settings. |
| **5. Rollout** | TestFlight; invite drivers; verify install, login, driver portal, availability calendar, Geomapper updates. |

---

## 9. What to Avoid

- Do not dump drivers into the dispatcher UI.
- Do not use frontend-only role protection.
- Do not let drivers see permits/jobs not tied to their assignment.
- Do not overbuild calendar v1 (no recurrence, PTO workflows).
- Do not let Google Maps replace permit logic (convenience only).
- One shared password; clients "declare" identity; plain-text passwords.

---

## 10. One-Sentence Summary

**One authenticated platform:** Driver app (Capacitor) lands drivers on a focused portal (assignment, permits, nav, calendar); dispatchers land on Geomapper; admins get elevated controls. Same backend, role-based routing, backend-enforced authorization.

---

*Reference for the GIGATT Geomapper role-based driver-tracking project. See plan.md for the full build plan.*
