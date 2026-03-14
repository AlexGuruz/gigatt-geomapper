# Deploying the backend & using StackBlitz

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
4. The app will call `https://your-app.up.railway.app/api/config`, `/api/routes`, etc. CORS is allowed (`Access-Control-Allow-Origin: *`).

**Local dev:** Leave `window.GEOMAPPER_API_BASE = ''` so the frontend uses the same origin (your local server).

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

## GitHub + StackBlitz workflow

1. After pushing, in StackBlitz: **Import from GitHub** → select the repo.
2. Set `web/js/config.js` to your deployed backend URL (or keep `''` to use a local backend if you run one).
3. As you develop, commit and push; you can open the same repo in StackBlitz to get the latest and monitor features.
