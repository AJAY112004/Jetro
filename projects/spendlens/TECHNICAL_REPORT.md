# SpendLens — Technical Evaluation Report

**Project:** `projects/spendlens`  
**Platform:** Jetro Research Workspace  
**Report date:** 26 May 2026  
**Prepared for:** Senior technical review / architecture evaluation  
**Status:** Development-ready (local); production hardening recommended  

---

## 1. Executive summary

SpendLens is a **local-first bank statement analyser** for Indian retail users. Users upload PDF or CSV statements; the backend categorises transactions, computes savings metrics, detects anomalies, and returns a structured JSON report. The React UI visualises results; a **server-side ReportLab PDF** exports a dashboard-style report.

The application is designed to run **inside Jetro** (iframe/canvas) and as a **standalone dev stack** (Flask + Vite). It does **not** use Django REST Framework or MySQL—the live stack is **Flask 3 + React 18 + Vite 8**, with file-based report caching and optional pandas/pdfplumber for PDF statements.

| Area | Assessment |
|------|------------|
| Core functionality | **Complete** for CSV; PDF via pandas pipeline |
| Jetro embedding | **Supported** with fetch-based API (no iframe navigation) |
| PDF export | **Working** (`pdf_report styled-v3`, verified HTTP 200) |
| Production readiness | **Beta** — secrets, auth, and ops gaps documented below |
| Test automation | **Minimal** — manual + Flask test client only |

---

## 2. Technology stack (actual vs assumed)

| Layer | Documented assumption | **Actual implementation** |
|-------|----------------------|---------------------------|
| Frontend | React + Vite | React 18.3, Vite 8.0, Chart.js 4 |
| Backend | Django REST + MySQL | **Flask 3** on port **5050** |
| Persistence | MySQL | **JSON files** in `.cache/reports/` + Flask **signed cookie** (`report_id`) |
| PDF | jsPDF / html2canvas | **ReportLab** (`pdf_report.py`) — server-side only |
| Client PDF lib | — | `html2pdf.js` in `package.json` but **not used in `src/`** |
| AI | Jetro skills (signed-in) | Rule-based insights + keyword categorisation (no LLM in pipeline) |

---

## 3. System architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Jetro Desktop (optional)                                        │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │ Canvas               │  │ iframe / embedded browser         │ │
│  │ spendlens-dashboard  │  │ http://127.0.0.1:5173 (React)    │ │
│  │ .json + frame HTML   │  └───────────────┬──────────────────┘ │
│  └──────────────────────┘                  │ fetch /api/*       │
└────────────────────────────────────────────┼────────────────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Vite dev server :5173                                           │
│  proxy /api → http://127.0.0.1:5050                              │
└────────────────────────────────────────────┬────────────────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Flask API :5050 (app.py)                                        │
│  ├── POST /api/analyse  → stdlib_pipeline (CSV) | analytics (PDF)│
│  ├── GET  /api/download-pdf → pdf_report.build_styled_pdf        │
│  └── session[report_id] → report_cache.load_report               │
└────────────────────────────────────────────┬────────────────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  .cache/reports/{uuid}.json   (full report payload)              │
│  tempfile/spendlens_uploads/  (uploaded files, deleted after)   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Dual UI surfaces

| Surface | Entry | Use case |
|---------|-------|----------|
| **React SPA** | `frontend/` → `:5173` | Primary UX; charts; PDF download |
| **Flask templates** | `:5050/` | Fallback without Node; same API patterns |
| **Jetro canvas** | `canvases/spendlens-dashboard.json` | Research dashboard frame + 5 min refresh |

### 3.2 Jetro integration points

| Asset | Path | Role |
|-------|------|------|
| Canvas definition | `projects/spendlens/canvases/spendlens-dashboard.json` | Layout: note + frame |
| Workspace canvas copy | `.jetro/canvases/spendlens-dashboard.json` | Jetro workspace binding |
| Frame HTML | `.jetro/frames/spendlens_dashboard.html` | Static dashboard shell |
| Refresh script | `.jetro/scripts/spendlens_dashboard_refresh.py` | Runs `analytics.run_pipeline` on sample CSV; emits JSON for canvas binding (`intervalMs`: 300000) |

**Jetro agent context (from workspace rules):** Finance features enabled; user may be offline (no Jetro cloud auth). SpendLens runs fully local without Jetro sign-in.

---

## 4. Repository layout

```
projects/spendlens/
├── frontend/                 # React + Vite
│   ├── src/
│   │   ├── App.jsx           # Upload + results + charts
│   │   ├── api.js            # fetch client, blob PDF download
│   │   └── main.jsx
│   ├── vite.config.js        # /api proxy → :5050
│   └── dist/                 # Production build (served by Flask /)
├── scripts/                  # Flask backend + analytics
│   ├── app.py                # HTTP API, CORS, sessions
│   ├── pdf_report.py         # Dashboard PDF (ReportLab, styled-v3)
│   ├── stdlib_pipeline.py    # CSV parser (no pandas)
│   ├── analytics.py          # PDF + pandas pipeline
│   ├── parse_statement.py    # Bank PDF/CSV normalisation
│   ├── categorise.py         # Keyword/regex categories
│   ├── report_cache.py       # UUID JSON file cache
│   └── requirements.txt
├── data/
│   ├── sample_statement.csv
│   └── report.json           # Static fallback
├── canvases/                 # Jetro canvas JSON
├── .cache/reports/           # Runtime report store (gitignored)
├── dev.ps1                   # Start Flask + Vite (Windows)
├── README.md
└── TECHNICAL_REPORT.md       # This document
```

---

## 5. API contract

Base URL (dev): `http://127.0.0.1:5173/api` (proxied) or `http://127.0.0.1:5050/api` (direct).

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/api/health` | None | — | `{ success, ok, service, version, port }` |
| GET | `/api/demo` | Session optional | — | `{ report, report_id }` |
| POST | `/api/analyse` | Session cookie | `multipart/form-data`, field `statement` (.csv/.pdf) | `{ report, report_id }` |
| GET | `/api/download-pdf` | Session (`report_id`) | `Accept: application/pdf` | `application/pdf` attachment |
| POST | `/api/analyze` | Alias | Same as analyse | Same |

**Error envelope:** `{ success: false, ok: false, error: string, detail?: string }`

**Session model:** Flask cookie stores `report_id` only; full report lives on disk (avoids 4KB cookie limit).

---

## 6. Data model (report JSON)

Key fields produced by `stdlib_pipeline` / `analytics`:

| Field | Type | Description |
|-------|------|-------------|
| `month_label` | string | e.g. "April 2026" |
| `spend_summary` | object | `total_income`, `total_expenses`, `net_savings`, `savings_rate_pct` |
| `category_breakdown` | array | `{ category, amount, pct }` |
| `daily_spend_trend` | array | `{ date, spend }` |
| `savings_score` | object | `{ score, label, colour }` |
| `anomalies` | array | `{ message, amount, category, ... }` |
| `ai_insights` | array | Rule-generated strings (not LLM) |
| `rebalancing_recommendation` | string | Heuristic savings tip |
| `transaction_count` | int | CSV pipeline only |
| `stats` | object | avg daily spend, high/low days |

---

## 7. Processing pipelines

### 7.1 CSV path (default, stable)

`stdlib_pipeline.run_pipeline` → parse CSV → `categorise` rules → aggregates → report dict.

- **Pros:** No pandas; fast; survived Windows dev crashes.
- **Cons:** Bank-specific column detection may need extension for new formats.

### 7.2 PDF path

`analytics.run_pipeline` → `parse_statement` (pdfplumber) → pandas → same report shape.

- **Pros:** Supports scanned/text PDF statements.
- **Cons:** Heavier deps; matplotlib removed from PDF path after native crash (`0xC0000005`).

### 7.3 PDF export path

`app._build_pdf` → `io.BytesIO()` → `pdf_report.build_styled_pdf(report, buffer)` → `send_file`.

- Landscape A4 dashboard: KPI cards, pie + line charts (ReportLab graphics), alerts, insights, tables.
- **Build ID:** `styled-v3` (logged at Flask startup).

---

## 8. Frontend design decisions

| Decision | Rationale |
|----------|-----------|
| `fetch` + `FormData` for upload | Avoids iframe navigation / `chrome-error://chromewebdata/` in Jetro |
| `fetch` + `blob` for PDF | Same-origin safe download; no `<a target="_blank">` |
| `credentials: "include"` | Session cookie for `report_id` |
| `VITE_API_URL` optional | Production / split-host override |
| Dev health check | Warns when Flask down (502 proxy errors) |
| Chart.js | Matches dashboard visuals; data from API only |

---

## 9. Security & privacy review

| Topic | Current state | Risk | Recommendation |
|-------|---------------|------|----------------|
| Data residency | Local disk + temp uploads | Low for dev | Document retention; encrypt cache at rest for prod |
| Secret key | Default `spendlens-local-dev-key` | **High** if exposed | `SPENDLENS_SECRET` env var mandatory in prod |
| AuthN/AuthZ | None on API | **High** public deploy | Add auth or network isolation |
| CORS | Allowlist localhost origins | OK for dev | Restrict to prod frontend origin |
| Upload limit | 16 MB | OK | Virus scan if accepting arbitrary files |
| Session fixation | Standard Flask session | Medium | HTTPS-only cookies in prod |
| PII in logs | Debug logs print upload metadata | Medium | Redact in production logging |
| Jetro iframe | Same-origin proxy helps | Medium | CSP headers for embedded deploy |

**Privacy claim in UI:** “Processed locally. Never stored.” — **Partially accurate:** files are temporarily stored in `%TEMP%/spendlens_uploads` and reports in `.cache/reports/` until overwritten.

---

## 10. Operational runbook

### 10.1 Local development (required: two processes)

```powershell
# Terminal 1
cd projects\spendlens\scripts
pip install -r requirements.txt
python app.py
# Expect: SpendLens API http://127.0.0.1:5050 (pdf_report styled-v3)

# Terminal 2
cd projects\spendlens\frontend
npm install --legacy-peer-deps   # if peer conflict with vite@8
npm run dev
# Open http://127.0.0.1:5173
```

Or: `projects\spendlens\dev.ps1`

### 10.2 Production-style

```powershell
cd projects\spendlens\frontend && npm run build
cd ..\scripts && python app.py
# Flask serves frontend/dist at /
```

### 10.3 Verification checklist

| Check | Expected |
|-------|----------|
| `GET /api/health` | 200, `ok: true` |
| Upload CSV → analyse | 200, `report` object |
| Download PDF | 200, `application/pdf`, ~80KB |
| Flask stopped + Vite running | 502 on `/api/*` with user-friendly message |

---

## 11. Incidents resolved (this development cycle)

| Issue | Root cause | Fix |
|-------|------------|-----|
| iframe “Unsafe attempt to load URL” | `<a href>` / form navigation in embedded frame | `fetch` + in-app render; blob PDF download |
| 502 Bad Gateway | Flask not running on :5050 | Document dual-server; `apiUnreachableMessage()` |
| 500 PDF `io` not defined | Missing import + stale Python process | `io.BytesIO` only in `app.py`; `build_styled_pdf(report, buffer)` |
| Flask crash on PDF | matplotlib `PdfPages` on Windows | ReportLab-only `pdf_report.py` |
| ECONNRESET on download | Server crash mid-request | Same as above |
| CORS / proxy | Cross-origin in dev | Vite proxy `/api` + `credentials: include` |

---

## 12. Quality & testing gaps

| Area | Status |
|------|--------|
| Unit tests | **None** in repo |
| Integration tests | Ad-hoc `app.test_client()` only |
| E2E | Manual browser |
| CI/CD | Not configured for SpendLens |
| Linting | Not enforced |
| Type checking | Python type hints partial; JS untyped |

**Recommended minimum for production gate:**

- pytest: `test_api_health`, `test_analyse_csv`, `test_download_pdf`
- GitHub Action: `pip install` + `npm run build` + tests
- Pin `reportlab`, `flask` in lockfile / `requirements.lock`

---

## 13. Dependency notes

### Python (`scripts/requirements.txt`)

- `flask`, `flask-cors`, `reportlab` — core API + PDF
- `pandas`, `pdfplumber` — PDF statement path only

### Node (`frontend/package.json`)

- `vite@8` vs `@vitejs/plugin-react@4` peer mismatch — use `npm install --legacy-peer-deps`
- `html2pdf.js` present but unused — **candidate for removal** to reduce bundle size

---

## 14. Scalability & limitations

| Limitation | Impact |
|------------|--------|
| File-based report cache | Not multi-instance safe without shared storage |
| Single Flask worker | Concurrent uploads block |
| No queue for large PDFs | Long requests may timeout |
| Rule-based categories | No ML; misclassification on novel merchants |
| INR / India-focused parsers | International banks need new rules |
| Offline Jetro | Skills/API cloud features unavailable |

---

## 15. Recommendations (prioritised)

### P0 — Before any public deploy

1. Set `SPENDLENS_SECRET` and disable Flask debug.
2. Add authentication or VPN-only access.
3. Auto-expire `.cache/reports` and upload temp files (TTL job).
4. Use gunicorn/waitress behind reverse proxy; not `app.run()` debug server.

### P1 — Engineering quality

5. Add pytest suite for API + PDF generation.
6. Remove unused `html2pdf.js` dependency.
7. Align Jetro canvas refresh script with `stdlib_pipeline` (currently uses `analytics` only).

### P2 — Product

8. Unify React dark UI with PDF light theme (brand consistency).
9. Add explicit “data deleted” endpoint for privacy compliance.
10. Optional Jetro skill: “Analyse statement” calling local API when finance features enabled.

---

## 16. Sign-off matrix for technical review

| Reviewer focus | Verdict | Notes |
|----------------|---------|-------|
| Architecture | **Approve for local/Jetro dev** | Clear separation: React / Flask / cache |
| Security | **Conditional** | Fix secrets, auth, retention before prod |
| Reliability | **Approve dev** | Restart Flask after backend changes (`styled-v3`) |
| Maintainability | **Good** | Modular pipelines; PDF isolated in `pdf_report.py` |
| Jetro fit | **Strong** | Canvas + fetch patterns iframe-safe |

---

## 17. Appendix — verified runtime snapshot

```
GET /api/health          → 200 { ok: true, service: spendlens, version: 1.0 }
GET /api/download-pdf    → 200 application/pdf (~79,189 bytes)
PDF_BUILD_ID             → styled-v3
```

---

*This report reflects the repository state at evaluation time. For stack changes, update Section 2 and re-run the verification checklist in Section 10.3.*
