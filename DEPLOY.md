# Deploying the backend & using StackBlitz

**Purpose:** Deploy the Geomapper backend so the frontend (e.g. StackBlitz) can call it. Aligned with **plan.md** (backend = Supabase Auth + Postgres + API; driver-locations batch, auth, config).

**Last updated:** 2026-03-14

---

## Deploy the backend

The app is set up so the **frontend** can run anywhere (e.g. StackBlitz) and talk to a **deployed backend** via a configurable API base URL.

### 1. Deploy to Railway or Render

**Railway (recommended):**

1. Create a new project at [railway.app](https://railway.app), connect your GitHub repo.
2. Add a **service** from this repo. Railway will detect Python and use `Procfile` (`web: python server.py`). If not, set **Start Command** to `python server.py`.
3. In the service → **Variables**, add all required env vars (see §2). Include `SUPABASE_JWT_SECRET` from Supabase → Project Settings → API → JWT Secret.
4. Deploy. The service will get a public URL (e.g. `https://your-app.up.railway.app`). The same URL serves both the API and the `web/` frontend (no separate frontend deploy needed unless you prefer Option B in §4).
5. In Supabase → Authentication → URL configuration, set **Site URL** and **Redirect URLs** to your Railway URL (see §5).

**Render:** New Web Service, connect repo, build command empty, start command: `python server.py`. Set env vars in the dashboard.

The server reads `PORT` from the environment and binds to `0.0.0.0` when `PORT` is set (so the host can route traffic).

### 2. Environment variables on the host

Set these in your deployment dashboard (Railway/Render/etc.):

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon/public key (for `/api/config` and auth) |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key (backend APIs, RLS bypass) |
| `SUPABASE_JWT_SECRET` | Yes | Supabase JWT secret (Project Settings → API → JWT Secret). Required for `/api/me` and admin API (Bearer token verification). |
| `PORT` | No | Set automatically by Railway/Render |

Optional: `SECRETS_DIR` if you mount a volume with `Guru Config.json` / `Supabase Pass.json`; otherwise use env vars only. See [ENV_VARS.md](ENV_VARS.md) for a full list.

### 3. Point the frontend at the deployed backend

When the frontend is served from **another origin** (e.g. StackBlitz), set the API base URL so all `/api/*` requests go to your deployed backend.

**In StackBlitz:**

1. Open this repo in StackBlitz and run the app. The login page will show a **"Connect to backend"** section when the backend isn’t configured.
2. Enter your deployed backend URL (e.g. `https://your-app.up.railway.app`) in the input and click **Connect & reload**. The URL is stored in `localStorage` and used for all `/api/*` requests.
3. Alternatively, edit `web/js/config.js` and set `GEOMAPPER_API_BASE`, or add `web/app-config.json` (see `web/app-config.example.json`) with `supabaseUrl`, `supabaseAnonKey`, and `apiBase`.
4. CORS is allowed (`Access-Control-Allow-Origin: *`) on the backend.

**Local dev:** Leave `window.GEOMAPPER_API_BASE = ''` so the frontend uses the same origin (your local server).

### 4. Frontend hosting options

- **Option A — Same host as backend (Railway):** This repo’s `server.py` serves the `web/` folder. Deploy the full repo; the root URL serves `web/index.html` and static assets. No separate frontend deploy. Set your Railway app URL as the Supabase redirect URL (see below).
- **Option B — Separate host (Vercel, Netlify, StackBlitz):** Deploy only the `web/` folder, set `apiBase` (or Connect to backend) to your Railway backend URL. Add your frontend origin to Supabase redirect URLs.

### 5. Supabase auth (production)

After deploying, configure Supabase so login works from your production frontend:

1. **Supabase Dashboard** → your project → **Authentication** → **URL configuration**.
2. **Site URL:** Your production app URL (e.g. `https://your-app.up.railway.app` or your Vercel/Netlify URL).
3. **Redirect URLs:** Add the same URL and any paths used for redirect (e.g. `https://your-app.up.railway.app/**`, `https://your-app.up.railway.app/login.html`, `https://your-app.up.railway.app/index.html`).

Without this, sign-in redirects may fail or point to localhost.

For Supabase and auth setup, see [PHASE1_SETUP.md](PHASE1_SETUP.md). For architecture and phases, see [plan.md](plan.md).

## Push this repo to GitHub (first time)

No remote is set yet. Do this once:

1. **Create a new repository** on GitHub (e.g. `geomapper-app` or `gigatt-geomapper`). Do not add a README or .gitignore.
2. In this project folder, run:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```
3. Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub user and repo name.

## StackBlitz preview (live UI)

The repo includes a `package.json` so StackBlitz can run a dev server and show the app in the preview:

1. **Import** the repo in StackBlitz (e.g. **Import from GitHub** → `AlexGuruz/gigatt-geomapper`).
2. StackBlitz runs `npm install` and `npm start`, which serves the `web/` folder on port 3000.
3. **Auth-first flow:** The app is wrapped with Supabase auth. If the backend isn’t configured, the login page shows a **"Connect to backend"** form. Enter your deployed backend URL and click **Connect & reload**; the app then loads config from that backend and sign-in works. The dispatcher map loads only after sign-in (dispatcher/admin role).
4. To **demonstrate full features** (map, route cards, refresh), use the Connect form with your deployed backend URL (or set it in `web/js/config.js` / `web/app-config.json`), then sign in with a test dispatcher account.

## GitHub + StackBlitz workflow (commit per rollout)

1. Develop and test locally; when ready, **commit** and **push** to `main` on GitHub.
2. In StackBlitz, use **Sync** / **Pull** (or re-open the repo) to get the latest commit.
3. Preview updates automatically so you can live-monitor UI and feature rollouts per commit.
