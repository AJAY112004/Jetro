# Jetro Workspace – SpendLens Project
This workspace contains the **SpendLens** project – a full‑stack personal finance app for analysing Indian bank statements, generating insights, and exporting a dashboard‑style PDF report.
This README explains:
- Overall workspace structure
- SpendLens project layout
- How to run the frontend and backend
- How to run tests and Docker
- Important environment variables
---
## 1. Workspace Structure
```text
Jetro/
├─ README.md                 ← This file (workspace overview)
└─ projects/
   └─ spendlens/             ← Main app: SpendLens
Inside projects/spendlens:

projects/spendlens/
├─ backend/                  ← Flask app factory, routes, services, security
├─ scripts/                  ← Analysis pipelines + Flask entrypoint
├─ frontend/                 ← React + Vite SPA
├─ data/                     ← Sample CSV and reference JSON
├─ deploy/                   ← Jetro-specific deploy files (optional)
├─ tests/                    ← pytest suite
├─ Dockerfile                ← Root Dockerfile (frontend + backend)
├─ docker-compose.yml        ← Simple compose setup
├─ render.yaml               ← Render backend config
├─ vercel.json               ← SPA rewrites for a static frontend
├─ README.md                 ← SpendLens-specific README
└─ project.json              ← Project metadata
2. SpendLens – Project Structure
2.1 Frontend (projects/spendlens/frontend)
Tech: React 18, Vite, Chart.js, react-chartjs-2, react-router-dom.
Key files:
src/main.jsx – React entrypoint.
src/App.jsx – App shell, routes, theme toggle.
src/api.js – API client using VITE_API_URL (no hardcoded localhost).
src/pages/UploadPage.jsx – Upload & analyse statement view.
src/pages/ResultsPage.jsx – Dashboard view (KPI cards, charts, insights).
src/components/ErrorBoundary.jsx – Global React error boundary.
src/components/SkeletonLoader.jsx – Loading UI.
src/components/ThemeToggle.jsx – Light/dark mode.
2.2 Backend (projects/spendlens/backend + scripts)
Tech: Python 3.12, Flask 3.x.
Entry: scripts/app.py (used locally, in Docker, and on Render).
Backend architecture:

backend/app_factory.py

Creates Flask app.
Configures:
CORS (CORS_ALLOWED_ORIGINS)
Security headers (flask-talisman)
JWT & rate limiting (flask-limiter)
Upload limits (MAX_UPLOAD_BYTES)
Registers API blueprint /api/*.
Serves frontend/dist as SPA when built.
backend/routes/api.py

GET /api/health – health check.
GET /api/auth/token – optional JWT token.
POST /api/analyse – upload CSV/PDF (statement field).
GET /api/download-pdf – download dashboard PDF for current session report.
GET /api/demo – demo analysis using sample CSV.
POST /api/analyze – alias to /api/analyse.
backend/services/

analysis_service.py – runs the standard‑library pipeline (stdlib_pipeline.run_pipeline) for CSV/PDF.
pdf_service.py – builds PDF bytes via pdf_report.build_styled_pdf.
report_service.py – stores/loads reports using report_cache and Flask session.
backend/utils/

errors.py – global error handlers and JSON response helpers.
security.py – JWT issue/verify, @require_auth decorator, rate limiting, security headers.
scripts/

app.py – calls backend.app_factory.create_app and exposes app.
stdlib_pipeline.py
Core CSV/PDF parser and analytics engine, pandas‑free.
Handles multiple bank formats, missing columns, and duplicate rows.
pdf_report.py
A4 landscape dashboard PDF using ReportLab.
report_cache.py
Saves/loads reports in .cache/reports/.
Other files (analytics.py, categorise.py, parse_statement.py, seed_report.py, export_report.py) – legacy/pandas pipeline and CLI helpers.
3. Environment & Configuration
All config is env‑driven. Key files:

projects/spendlens/.env – local dev defaults.
projects/spendlens/.env.production – prod defaults.
projects/spendlens/frontend/.env + .env.production – frontend env.
3.1 Backend env vars
In projects/spendlens:

PORT
Backend port (default 8080 for container, 5050 in dev).

SPENDLENS_SECRET
Flask session secret. Must be set to a strong value in production.

JWT_SECRET
JWT signing key (HS256). Must be long and random in prod.

AUTH_ENABLED
1 = require bearer token on /api/*, 0 = disabled.

MAX_UPLOAD_BYTES
Max upload size (e.g. 16777216 for 16 MB).

RATE_LIMIT_DEFAULT
Default rate limit, e.g. "60 per minute".

CORS_ALLOWED_ORIGINS
Comma‑separated origins for cross‑origin frontend (e.g. deployed SPA).

3.2 Frontend env vars
In projects/spendlens/frontend:

VITE_API_URL
API base, e.g. /api for same‑origin, or https://api.example.com/api when backend is separate.

VITE_API_PROXY_TARGET
Dev proxy target, usually http://127.0.0.1:5050.

VITE_DEV_HOST
Dev server host, default 127.0.0.1.

4. How to Run (Local Dev)
Assume your terminal is at:

cd C:\Users\aajay\Documents\Jetro\projects\spendlens
4.1 Backend (Flask) – Dev mode
Install dependencies (one‑time):

pip install -r scripts\requirements.txt
Run the backend:

set FLASK_DEBUG=1
set PORT=5050
python scripts\app.py
Check health:

Open http://127.0.0.1:5050/api/health
4.2 Frontend (Vite dev server)
Install dependencies (one‑time):

cd frontend
npm install
Start dev server:

npm run dev
Open:

http://127.0.0.1:5173
The dev server proxies /api/* to http://127.0.0.1:5050, so the React app and Flask API behave as same‑origin.

5. Production Build & Single‑Process Serving
5.1 Build the frontend
cd C:\Users\aajay\Documents\Jetro\projects\spendlens\frontend
npm run build
This creates frontend/dist.

5.2 Serve via Flask only
cd C:\Users\aajay\Documents\Jetro\projects\spendlens
set FLASK_DEBUG=0
set PORT=8080
python scripts\app.py
Now:

http://127.0.0.1:8080/ → React SPA (from frontend/dist)
/api/* → Flask JSON/PDF API
6. Docker & Docker Compose
From projects/spendlens:

6.1 Build image
docker build -t spendlens:local .
6.2 Run container
docker run --rm -p 8080:8080 \
  -e SPENDLENS_SECRET=change-me-in-prod \
  -e JWT_SECRET=change-me-in-prod-and-make-it-long-enough-32+ \
  spendlens:local
Open: http://127.0.0.1:8080

6.3 Using docker-compose
docker compose up --build
# or
docker-compose up --build
7. Testing & CI
7.1 Backend tests
From projects/spendlens:

pytest                      # unit tests
pytest --cov=backend --cov=scripts  # with coverage
Coverage for core runtime code is enforced in CI via:

.github/workflows/ci.yml:
Builds the frontend (npm run build).
Installs Python deps.
Runs pytest --cov=backend --cov=scripts --cov-fail-under=80.
7.2 What’s covered
Tests exercise:

CSV & PDF parsing (stdlib_pipeline.py).
Analysis service fallback logic.
Report cache JSON safety.
API flow:
/api/auth/token → /api/analyse → /api/download-pdf.
SPA routing and asset serving from Flask.
8. Typical User Flow (SpendLens)
Open the app (local URL, Docker, Render, etc.).
Upload a bank statement file (.csv or .pdf).
The app analyses transactions and shows:
KPIs (income, expenses, net savings, savings score).
Category breakdown chart.
Daily spend trend chart.
Anomaly alerts and AI‑style insights.
Click “Download Report (PDF)” to export a styled A4 dashboard.