# SpendLens

## Fix for iframe / `chrome-error://chromewebdata/` errors

**Cause:** Full-page navigation (`<a href="/api/...">`, `<form action="...">`, `target="_blank"`) inside an embedded iframe (e.g. Jetro). If a prior load failed, Chrome leaves the frame on `chrome-error://chromewebdata/` and blocks loading another URL there — including PDF download links.

**Fix:** Use **`fetch` + blob** for uploads and PDFs. Never navigate the iframe to API URLs.

| Wrong | Right |
|-------|--------|
| `<form action="/analyse">` | `fetch('/api/analyse', { method: 'POST', body: formData })` |
| `<a href="/api/download-pdf" target="_blank">` | `downloadReportPdf()` → `fetch` + `URL.createObjectURL` |
| iframe `src="http://127.0.0.1:5050/analyse"` | iframe `src="http://127.0.0.1:5173"` (React) or Flask `/` |
| GET `/analyse` | GET `/api/demo`, POST `/api/analyse` |

## Run locally

**You need both servers.** Vite (`:5173`) proxies `/api` to Flask (`:5050`). If Flask is stopped, uploads return **502 Bad Gateway**.

Quick start (Windows):

```powershell
cd projects\spendlens
.\dev.ps1
```

Or run two terminals manually (below).

### 1. Backend (Flask) — port **5050**

```powershell
cd projects\spendlens\scripts
pip install -r requirements.txt
python app.py
```

Verify: http://127.0.0.1:5050/api/health → `{"ok": true, ...}`

### 2. Frontend (React + Vite) — port **5173**

```powershell
cd projects\spendlens\frontend
npm install
npm run dev
```

Open: http://127.0.0.1:5173

Vite proxies `/api/*` to Flask — same-origin from the browser’s view, no CORS issues in dev.

Set `VITE_API_URL` when the API is on another host (see `frontend/.env.example`).

### 3. Flask-only (no Node)

Open http://127.0.0.1:5050 — uses the updated `index.html` with `fetch` (no React).

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check |
| GET | `/api/demo` | Sample analysis JSON |
| POST | `/api/analyse` | Upload `statement` file → `{ ok, report }` |
| GET | `/api/download-pdf` | Dashboard-style PDF report (needs session cookie) |
| POST | `/api/analyze` | US spelling alias |

Legacy HTML routes `/analyse` (POST) still work with `Accept: application/json`. **GET `/analyse` returns 405** to avoid iframe loads.

## Production build (local)

```powershell
cd projects\spendlens\frontend
npm run build
cd ..\scripts
python app.py
```

Serve React from `frontend/dist` via Flask `/` when the build exists.

## Jetro public deploy

**Slug:** `spendlens` → **https://spendlens.jetro.app**

Requires Docker + Jetro sign-in. See [`deploy/README.md`](deploy/README.md).

```text
jet_deploy({ action: "start", projectSlug: "spendlens" })
jet_deploy({ action: "publish", projectSlug: "spendlens" })
```
