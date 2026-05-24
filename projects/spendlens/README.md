# SpendLens

## Fix for “Unsafe attempt to load URL …/analyse from frame”

**Cause:** The upload form used `action="/analyse"` which **navigates** the browser (or Jetro iframe) to `http://127.0.0.1:5050/analyse`. If the server is down or the page is embedded, Chrome shows `chrome-error://chromewebdata/` and blocks cross-frame access.

**Fix:** Use **`fetch` → `POST /api/analyse`** and render results in the same page. Never open `/analyse` as a document URL.

| Wrong | Right |
|-------|--------|
| `<form action="/analyse">` | `fetch('/api/analyse', { method: 'POST', body: formData })` |
| iframe `src="http://127.0.0.1:5050/analyse"` | iframe `src="http://127.0.0.1:5173"` (React) or Flask `/` |
| GET `/analyse` | GET `/api/demo`, POST `/api/analyse` |

## Run locally

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

### 3. Flask-only (no Node)

Open http://127.0.0.1:5050 — uses the updated `index.html` with `fetch` (no React).

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check |
| GET | `/api/demo` | Sample analysis JSON |
| POST | `/api/analyse` | Upload `statement` file → `{ ok, report }` |
| GET | `/api/download-pdf` | PDF (needs session cookie) |
| POST | `/api/analyze` | US spelling alias |

Legacy HTML routes `/analyse` (POST) still work with `Accept: application/json`. **GET `/analyse` returns 405** to avoid iframe loads.

## Production build

```powershell
cd projects\spendlens\frontend
npm run build
cd ..\scripts
python app.py
```

Serve React from `frontend/dist` via Flask `/` when the build exists.
