# SpendLens — Jetro public deploy

**Slug:** `spendlens`  
**Public URL:** https://spendlens.jetro.app (after `publish`)

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running
- Signed in to **Jetro** (deploy/publish uses Jetro cloud tunnel)
- Frontend built inside Docker (handled by `deploy/Dockerfile`)

## Deploy from Jetro (recommended)

In the Jetro chat / agent:

1. **Start** the container locally:
   ```
   jet_deploy({ action: "start", projectSlug: "spendlens" })
   ```
2. **Publish** the public URL:
   ```
   jet_deploy({ action: "publish", projectSlug: "spendlens" })
   ```
3. **Status**:
   ```
   jet_deploy({ action: "status", projectSlug: "spendlens" })
   ```

Other actions: `stop`, `redeploy`, `remove`.

Logs: `docker logs jet-app-spendlens`

## Manual Docker test (optional)

From `projects/spendlens`:

```powershell
docker build -f deploy/Dockerfile -t spendlens:local .
docker run --rm -p 8080:8080 -e SPENDLENS_SECRET=change-me-in-prod spendlens:local
```

Open http://127.0.0.1:8080

## Layout

| File | Role |
|------|------|
| `deploy/server.py` | Jetro entry — gunicorn → `scripts/app.py` |
| `deploy/requirements.txt` | Container Python deps |
| `deploy/Dockerfile` | Multi-stage: npm build + Flask |
| `deploy/jetro.json` | Slug, URL, port metadata |
| `scripts/app.py` | Flask API + serves `frontend/dist` |

## Production env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8080` | Listen port |
| `SPENDLENS_SECRET` | (dev key) | Flask session signing — **set in prod** |
| `FLASK_DEBUG` | `0` | Disable debug in container |
| `SESSION_COOKIE_SECURE` | `1` | HTTPS cookies when published |
| `CORS_EXTRA_ORIGINS` | — | Comma-separated extra origins |
