# Environment variables

Use these for local development (`.env`) or production (Railway/Render dashboard). Do not commit secrets.

## Required for backend (with Supabase)

| Variable | Description | Where to get it |
|----------|-------------|-----------------|
| `SUPABASE_URL` | Supabase project URL | Supabase Dashboard → Project Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Public anon key | Same → Project API keys → anon public |
| `SUPABASE_SERVICE_KEY` | Service role key (secret) | Same → service_role (keep secret) |
| `SUPABASE_JWT_SECRET` | JWT signing secret | Same → JWT Settings → JWT Secret. Required for `/api/me`, admin API, and driver Bearer token validation. |

## Optional

| Variable | Description |
|----------|-------------|
| `PORT` | Set by Railway/Render. When set, server binds to `0.0.0.0` for external access. |
| `SECRETS_DIR` | Path to folder containing `Guru Config.json` or `Supabase Pass.json`; secrets are loaded into env from there. |
| `BACKEND_PUBLIC_URL` | Public URL of this backend; injected into `/api/config` as `apiBase` when set. Use for CORS or public links when the frontend runs on another host (e.g. StackBlitz, production frontend). |

## Local development

1. Copy `.env.example` to `.env` (or create `.env` with the variables above).
2. Fill in your Supabase values and optional `BACKEND_PUBLIC_URL` if the frontend runs elsewhere.
3. Run `python server.py` (or use the project’s start script).

## Production (Railway / Render)

Set all required variables in the host’s environment. Add your production frontend URL to Supabase **Authentication → URL configuration** (Site URL and Redirect URLs). See [DEPLOY.md](DEPLOY.md).
