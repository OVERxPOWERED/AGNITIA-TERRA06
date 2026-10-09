# TERRA Deployment Runbook

This guide contains step-by-step instructions for deploying the **TERRA** platform.

> [!IMPORTANT]
> **Deployment remains ON HOLD per AGENTS.md Rule 10 until explicitly requested.**
> Do not contact hosting services, create live GitHub releases, or trigger production deploys prematurely.
> When ready to deploy, follow the steps below in order.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────────────┐
                      │            Vercel (Edge CDN)                 │
                      │  Next.js 16 App Router (SSR / Static Export) │
                      │  NEXT_PUBLIC_API_BASE=https://<api>.onrender │
                      └──────────────────────┬───────────────────────┘
                                             │ HTTPS (CORS)
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │              Render (Web Service)            │
                      │  Docker (Python 3.11-slim + libgomp1)        │
                      │  FastAPI + Uvicorn (:8000 / $PORT)          │
                      │  Artifacts downloaded from GitHub Release   │
                      └───────┬──────────────────────────────┬───────┘
                              │                              │
                              ▼                              ▼
                 ┌─────────────────────────┐   ┌───────────────────────────┐
                 │   Neon Serverless DB    │   │  UptimeRobot / Cron Job   │
                 │   PostgreSQL 16 (Free)  │   │  GET /health every 5 min  │
                 │   pool_recycle=300      │   │  (Demo window only)       │
                 └─────────────────────────┘   └───────────────────────────┘
```

---

## Step 1: Create Neon Database

1. Sign up / log in to [Neon Console](https://console.neon.tech/).
2. Create a new project:
   - **Project Name**: `terra-db`
   - **Postgres Version**: `16`
   - **Region**: Closest to Render region (e.g., `Singapore` or `Frankfurt`).
3. Under **Connection Details**, copy the connection string.
   - Format: `postgres://<user>:<password>@<ep-hostname>.neon.tech/neondb?sslmode=require`
   - Note: The TERRA backend automatically normalizes `postgres://` or `postgresql://` to `postgresql+psycopg://`.
4. Ensure `?sslmode=require` is present at the end of the URL.

---

## Step 2: Build the Deployment Bundle

Create the runtime model & forecast bundle from your evaluated artifacts:

```bash
make bundle
```

This executes `scripts/make_deploy_bundle.py` (stdlib only) and outputs:
- `dist/terra-artifacts-<UTC-timestamp>.zip` (~12.5 MB compressed, ~22 MB uncompressed)
- `dist/terra-artifacts-<UTC-timestamp>.zip.sha256`

The script packages **only** runtime-required files:
- Active run referenced in `runs/LATEST`
- `evaluation/results.json`
- `backtests/solar/predictions.parquet` and `backtests/wind/predictions.parquet`
- Active model bundles referenced in `models/*/LATEST`
- Refuses any files matching `.env`, `secret`, `kaggle`, or private keys.

---

## Step 3: Publish GitHub Release Asset

Create a versioned release on the public repository `OVERxPOWERED/AGNITIA-TERRA06` so Render's Docker builder can download it without authentication tokens:

```bash
# Example with the generated bundle (substitute the exact filename from dist/):
gh release create v0.1.0-artifacts \
  dist/terra-artifacts-20261009T001709Z.zip \
  dist/terra-artifacts-20261009T001709Z.zip.sha256 \
  --title "TERRA Runtime Artifacts v0.1.0" \
  --notes "Runtime model bundles, evaluation results, and initial forecast runs."
```

Your download URL will be:
```
https://github.com/OVERxPOWERED/AGNITIA-TERRA06/releases/download/v0.1.0-artifacts/terra-artifacts-20261009T001709Z.zip
```
And the SHA256 checksum is located inside `dist/terra-artifacts-20261009T001709Z.zip.sha256`.

---

## Step 4: Deploy Backend on Render

1. Log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** → **Blueprint**.
3. Connect repository `OVERxPOWERED/AGNITIA-TERRA06` (branch `main`).
4. Render detects [`render.yaml`](../render.yaml).
5. Fill in the required parameters when prompted:

| Variable / Argument | Type | Source / Value | Notes |
|---|---|---|---|
| `ARTIFACT_URL` | Build Argument | `https://github.com/OVERxPOWERED/AGNITIA-TERRA06/releases/download/v0.1.0-artifacts/terra-artifacts-<timestamp>.zip` | Direct download URL of release zip |
| `ARTIFACT_SHA256` | Build Argument | SHA256 from the `.sha256` file | Verified during Docker build via `sha256sum` |
| `TERRA_DB_URL` | Environment Variable | `postgres://user:pass@ep-xyz.neon.tech/neondb?sslmode=require` | Neon connection string |
| `TERRA_CORS_ORIGINS` | Environment Variable | `http://localhost:3000` (initially) | Update to Vercel URL in Step 6 |
| `TERRA_MODE` | Environment Variable | `replay` | Set by `render.yaml` |
| `TERRA_SCHEDULER_ENABLED` | Environment Variable | `false` | Replay mode data is pre-computed; saves CPU |

6. Click **Apply**.
7. Wait for the build to finish. Once live, copy your service URL (e.g., `https://terra-api.onrender.com`).

---

## Step 5: Deploy Frontend on Vercel

1. Log in to [Vercel Dashboard](https://vercel.com/).
2. Click **Add New…** → **Project** and import `OVERxPOWERED/AGNITIA-TERRA06`.
3. In project configuration:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
4. **Environment Variables**:
   - `NEXT_PUBLIC_API_BASE` = `https://terra-api.onrender.com` (from Step 4)
   > [!WARNING]
   > Next.js inlines `NEXT_PUBLIC_*` environment variables during build time. You **must** configure `NEXT_PUBLIC_API_BASE` before the initial build, or redeploy after setting it. If missing or pointing to localhost, the client displays a visible configuration error card.
5. Click **Deploy**.
6. Note your production Vercel domain (e.g., `https://agnitia-terra06.vercel.app`).

---

## Step 6: Update CORS on Render

1. Open Render Dashboard → `terra-api` service → **Environment**.
2. Set `TERRA_CORS_ORIGINS` to include your Vercel domain:
   ```
   https://agnitia-terra06.vercel.app
   ```
3. Save changes. Render will automatically redeploy the service.

---

## Step 7: Configure Uptime Pinger (Demo Window)

To mitigate Render's free-tier spin-down (15 minutes of inactivity):

1. Go to [UptimeRobot](https://uptimerobot.com/) or [cron-job.org](https://cron-job.org/).
2. Create an HTTP monitor:
   - **URL**: `https://terra-api.onrender.com/health`
   - **Monitoring Interval**: Every `5 minutes`
   - **HTTP Method**: `GET`
   - **Expected Status**: `200 OK`
3. **Usage Guidelines**:
   - Enable this monitor **only during the evaluation / demo window**.
   - Render's free tier provides 750 hours/month of free web service usage (sufficient for one always-on service throughout a 30-day month). Pausing the pinger outside demo windows conserves free-tier hours.

---

## Verification & Smoke Tests

Run these curl commands to verify your deployment:

```bash
API="https://terra-api.onrender.com"

# 1. Health check (fast, no DB dependency)
curl -f "$API/health"

# 2. Site configuration
curl -f "$API/site"

# 3. Forecasts (solar, wind, hybrid)
curl -f "$API/forecast?source=hybrid&horizon=48"
curl -f "$API/forecast?source=solar&horizon=24"
curl -f "$API/forecast?source=wind&horizon=24"

# 4. Active alerts (seeded from database)
curl -f "$API/alerts"

# 5. Dispatch schedule
curl -f "$API/dispatch?strategy=advisor"

# 6. Model comparison
curl -f "$API/models/compare?source=solar"
curl -f "$API/models/compare?source=wind&by=lead_bucket"

# 7. What-If simulator (POST)
curl -f -X POST "$API/whatif" \
  -H "Content-Type: application/json" \
  -d '{"irradiance_scale": 0.8, "wind_speed_scale": 1.1, "battery_mwh": 60}'
```

---

## Rollback Procedure

If a release bundle contains issues:
1. Identify the previous working release tag or bundle on GitHub Releases (e.g. `v0.0.9-artifacts`).
2. Update `ARTIFACT_URL` and `ARTIFACT_SHA256` in Render's **Environment** tab.
3. Click **Manual Deploy** → **Clear build cache & deploy**.

---

## Local Docker Compose

For local testing with Docker without external dependencies:

```bash
docker compose up --build
```
`docker-compose.yml` mounts local `./artifacts` and `./data` as volumes, and configures SQLite at `/app/artifacts/terra.db`.

---

## Known Limits & Free-Tier Behaviors

1. **Cold Starts**: Render free tier sleeps after 15 minutes of inactivity. When cold, the first request takes ~30–50 seconds. The frontend features an automatic wake-up handler with 12 exponential backoff retries and informative visual cues.
2. **Neon Scale-to-Zero**: Neon suspends idle compute after 5 minutes. The initial connection re-activation adds ~1.5–3 seconds of latency. `pool_pre_ping=True` and `pool_recycle=300` in SQLModel handle reconnects cleanly.
3. **Replay Mode**: In replay mode, historical weather and pre-computed forecast runs simulate operational behavior without live API dependencies.
