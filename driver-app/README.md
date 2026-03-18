# GIGATT Driver App (Capacitor)

Native iOS/Android wrapper for the **Driver Portal** (Plan Phase 4). Uses the same UI as `../web/driver.html` and `../web/login.html`, synced into `www/` for Capacitor.

## Prerequisites

- Node 18+
- **iOS:** macOS, Xcode, CocoaPods
- **Android:** Android Studio, SDK + NDK

## Setup

```bash
npm install
npm run build    # syncs from ../web into www/
npx cap sync     # copies www into native projects
```

## Sync web changes

After editing `../web/driver.html`, `../web/login.html`, or any of the driver portal JS/CSS:

```bash
npm run build
npx cap sync
```

Then rebuild/run the native app.

## Backend URL (native)

The app loads config from `GET /api/config` (Supabase URL/keys and optional `apiBase`). When running as a native app, the backend is not same-origin. Either:

1. **Set API base before login:** Use the “Connect to backend” section on the login screen (saved in `localStorage`), or  
2. **Set default in app:** In `www/js/config.js` or via a build-time config, set `GEOMAPPER_API_BASE` to your backend (e.g. `https://your-app.up.railway.app`).

**Setting a default API URL for store builds:** So drivers don’t have to enter the backend URL, set it at build time. Options: (1) In `www/js/config.js`, set `window.GEOMAPPER_API_BASE` to your production backend URL when building for release (e.g. replace a placeholder with an env var in a build script). (2) Or ship a small `www/app-config.json` that the app loads first and that sets `apiBase`; ensure your sync script doesn’t overwrite it. (3) Or use Capacitor’s build-time env (e.g. `CAPACITOR_API_BASE`) and inject it into a script tag in `www/index.html`. After changing `www/`, run `npm run build` and `npx cap sync` before building the native app.

## Non-driver users

If a user signs in with a **dispatcher** or **admin** role, they are redirected to the dispatch app. Set `window.GEOMAPPER_DISPATCH_URL` (e.g. in a script in `www/index.html`) to your main app URL so they open the web dispatch UI instead of staying in the driver app.

## Run

- **iOS:** `npm run cap:ios` (opens Xcode; run on simulator or device)
- **Android:** `npm run cap:android` (opens Android Studio; run on emulator or device)

## Add native projects (first time)

If `ios/` or `android/` are not present:

```bash
npx cap add ios
npx cap add android
npx cap sync
```

Then open the IDE and run as above.

## Store deployment

- **TestFlight / App Store:** Archive in Xcode, upload, then submit from App Store Connect.
- **Google Play:** Build release AAB in Android Studio, upload to Play Console.

See the main repo **DEPLOY.md** for backend and auth setup (Supabase redirect URLs, etc.).
