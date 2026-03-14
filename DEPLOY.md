# Deploying the backend & using StackBlitz

**Purpose:** Deploy the Geomapper backend so the frontend (e.g. StackBlitz) can call it. Aligned with **plan.md** (backend = Supabase Auth + Postgres + API; driver-locations batch, auth, config).

**Last updated:** 2026-03-14

---

## Deploy the backend

The app is set up so the **frontend** can run anywhere (e.g. StackBlitz) and talk to a **deployed backend** via a configurable API base URL.

### 1. Deploy to Railway or Render

- **Railway**: Connect this repo, add a new service, set **Start Command** to `python server.py` (or use the `Procfile`). Set env vars (see below).
- **Render**: New Web Service, connect repo, build command can be empty, start command: `python server.py`. Set env vars in the dashboard.

The server reads `PORT` from the environment and binds to `0.0.0.0` when `PORT` is set (so the host can route traffic).

### 2. Environment variables on the host

Set these in your deployment dashboard (Railway/Render/etc.):

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon/public key (for `/api/config` and auth) |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key (backend APIs, RLS bypass) |
| `PORT` | No | Set automatically by Railway/Render |

Optional: `SECRETS_DIR` if you mount a volume with `Guru Config.json` / `Supabase Pass.json`; otherwise use env vars only.

### 3. Point the frontend at the deployed backend

When the frontend is served from **another origin** (e.g. StackBlitz), set the API base URL so all `/api/*` requests go to your deployed backend.

**In StackBlitz:**

1. Open this repo in StackBlitz (e.g. **Open in StackBlitz** from GitHub).
2. Edit `web/js/config.js`.
3. Set `window.GEOMAPPER_API_BASE` to your deployed backend URL (no trailing slash), e.g.:
   ```js
   window.GEOMAPPER_API_BASE = 'https://your-app.up.railway.app';
   ```
4. The app will call `https://your-app.up.railway.app/api/config`, `/api/routes`, `/api/driver-locations/batch` (when using Supabase), etc. CORS is allowed (`Access-Control-Allow-Origin: *`).

**Local dev:** Leave `window.GEOMAPPER_API_BASE = ''` so the frontend uses the same origin (your local server).

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
3. **Auth-first flow:** The app is wrapped with Supabase auth. If the backend is not configured (or not reachable), the preview **shows the login page** and the message: *"Backend not configured. Set GEOMAPPER_API_BASE in web/js/config.js to your deployed backend URL."* The dispatcher map and route cards load **only after** a successful sign-in (dispatcher/admin role).
4. To **demonstrate full features** (map, route cards, refresh, etc.), set your deployed backend URL in `web/js/config.js`:  
   `window.GEOMAPPER_API_BASE = 'https://your-backend.up.railway.app';`  
   Then sign in with a test dispatcher account; the map and sidebar will load and reflect backend data.

## GitHub + StackBlitz workflow (commit per rollout)

1. Develop and test locally; when ready, **commit** and **push** to `main` on GitHub.
2. In StackBlitz, use **Sync** / **Pull** (or re-open the repo) to get the latest commit.
3. Preview updates automatically so you can live-monitor UI and feature rollouts per commit.
