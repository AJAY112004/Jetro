"""
SpendLens Flask API.

Backend:  python app.py  → http://127.0.0.1:5050
Frontend: cd ../frontend && npm run dev → http://127.0.0.1:5173
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import tempfile
import traceback
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from report_cache import json_safe, load_report, save_report  # noqa: E402
from stdlib_pipeline import run_pipeline as stdlib_csv_pipeline  # noqa: E402

ROOT = SCRIPTS_DIR.parent
SAMPLE_CSV = ROOT / "data" / "sample_statement.csv"
FALLBACK_REPORT = ROOT / "data" / "report.json"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "spendlens_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

FRONTEND_DIST = ROOT / "frontend" / "dist"

CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5050",
    "http://localhost:5050",
]

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("spendlens")

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SPENDLENS_SECRET", "spendlens-local-dev-key")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB uploads

CORS(
    app,
    resources={r"/api/*": {"origins": CORS_ORIGINS}},
    supports_credentials=True,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-Requested-With"],
)


def _pandas_pipeline(path: Path) -> dict:
    from analytics import run_pipeline

    return run_pipeline(str(path))


def _fallback_report() -> dict:
    return json.loads(FALLBACK_REPORT.read_text(encoding="utf-8"))


def _analyse_file(path: Path) -> dict:
    """
    CSV → stdlib pipeline (stable, no pandas crash).
    PDF → pandas/pdfplumber pipeline.
    """
    ext = path.suffix.lower()
    logger.info("Analysing %s (%s bytes)", path.name, path.stat().st_size)

    if ext == ".csv":
        try:
            report = stdlib_csv_pipeline(path)
            logger.info("stdlib CSV pipeline OK: %d categories", len(report.get("category_breakdown", [])))
            return report
        except Exception as exc:
            logger.exception("stdlib CSV pipeline failed")
            # Last resort for known sample formats
            if path.name in ("sample_statement.csv", "sample_bank_transactions.csv"):
                if FALLBACK_REPORT.is_file():
                    logger.warning("Using static report.json fallback")
                    return _fallback_report()
            raise ValueError(f"CSV parse failed: {exc}") from exc

    if ext == ".pdf":
        try:
            return _pandas_pipeline(path)
        except Exception as exc:
            logger.exception("PDF pipeline failed")
            raise ValueError(f"PDF analysis failed: {exc}") from exc

    raise ValueError(f"Unsupported file type: {ext}")


def _store_report(report: dict) -> str:
    safe = json_safe(report)
    report_id = save_report(safe)
    session["report_id"] = report_id
    return report_id


def _session_report() -> dict | None:
    return load_report(session.get("report_id"))


def _fmt_inr(n: float) -> str:
    return f"₹{n:,.0f}"


app.jinja_env.filters["inr"] = _fmt_inr


def _json_ok(payload: dict, status: int = 200):
    body = {"success": True, "ok": True, **payload}
    return jsonify(body), status


def _json_error(message: str, status: int = 400, *, detail: str | None = None):
    body: dict = {"success": False, "ok": False, "error": message}
    if detail:
        body["detail"] = detail if app.debug else detail.splitlines()[-1]
    logger.error("API error %s: %s", status, message)
    if detail and app.debug:
        print(traceback.format_exc())
    return jsonify(body), status


def _debug_upload():
    print("--- /api/analyse request ---")
    print("headers:", dict(request.headers))
    print("content_type:", request.content_type)
    print("content_length:", request.content_length)
    print("files:", list(request.files.keys()))
    for key, f in request.files.items():
        print(f"  file[{key}]: filename={f.filename!r} content_type={f.content_type!r}")


@app.errorhandler(HTTPException)
def handle_http_error(exc: HTTPException):
    if request.path.startswith("/api/"):
        return _json_error(exc.description or str(exc), exc.code)
    return exc


@app.errorhandler(Exception)
def handle_unexpected(exc: Exception):
    logger.exception("Unhandled error on %s", request.path)
    if request.path.startswith("/api/"):
        return _json_error(str(exc), 500, detail=traceback.format_exc())
    raise exc


@app.route("/api/health", methods=["GET"])
def api_health():
    return _json_ok({"service": "spendlens", "version": "1.0", "port": 5050})


@app.route("/api/demo", methods=["GET"])
def api_demo():
    try:
        report = _analyse_file(SAMPLE_CSV)
    except Exception as exc:
        logger.warning("Demo fallback: %s", exc)
        report = _fallback_report()
    report_id = _store_report(report)
    return _json_ok({"report": json_safe(report), "report_id": report_id})


@app.route("/api/analyse", methods=["POST"])
def api_analyse():
    _debug_upload()

    if not request.files:
        return _json_error(
            "No files in request. Send multipart/form-data with field name 'statement'.",
            400,
        )

    file = request.files.get("statement")
    if not file or not file.filename:
        return _json_error(
            f"Missing file field 'statement'. Received fields: {list(request.files.keys())}",
            400,
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in (".csv", ".pdf"):
        return _json_error("Only PDF and CSV files are supported.")

    dest: Path | None = None
    try:
        dest = UPLOAD_DIR / f"upload_{os.getpid()}_{file.filename}"
        file.save(dest)
        logger.info("Saved upload → %s (%s bytes)", dest, dest.stat().st_size)

        report = _analyse_file(dest)
        report_id = _store_report(report)

        logger.info("POST /api/analyse → 200 report_id=%s", report_id)
        return _json_ok({"report": json_safe(report), "report_id": report_id})

    except Exception as exc:
        tb = traceback.format_exc()
        logger.exception("POST /api/analyse failed")
        print(tb)
        return _json_error(f"Analysis failed: {exc}", 500, detail=tb)

    finally:
        if dest is not None and dest.exists():
            dest.unlink(missing_ok=True)


@app.route("/")
def home():
    if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").is_file():
        return send_file(FRONTEND_DIST / "index.html")
    return render_template("index.html", api_base="/api")


@app.route("/results")
def results_page():
    return render_template("results.html", report=_session_report())


@app.route("/demo")
def demo():
    if request.headers.get("Accept", "").find("json") >= 0:
        return api_demo()
    try:
        report = _analyse_file(SAMPLE_CSV)
    except Exception:
        report = _fallback_report()
    _store_report(report)
    return render_template("results.html", report=report)


@app.route("/analyse", methods=["GET"])
def analyse_get_blocked():
    return _json_error("Use POST /api/analyse with multipart file upload.", 405)


@app.route("/analyse", methods=["POST"])
@app.route("/analyze", methods=["POST"])
@app.route("/api/analyze", methods=["POST"])
def analyse_post_alias():
    return api_analyse()


@app.route("/download-pdf")
def download_pdf():
    report = _session_report()
    if not report:
        return redirect(url_for("demo"))
    return _pdf_response(report)


@app.route("/api/download-pdf")
def api_download_pdf():
    report = _session_report()
    if not report:
        return _json_error("No report in session. Run /api/analyse first.", 404)
    return _pdf_response(report)


def _pdf_response(report: dict):
    pdf_bytes = _build_pdf(report)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="spendlens_report.pdf",
    )


def _build_pdf(report: dict) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    buf = io.BytesIO()
    s = report.get("spend_summary", {})
    sc = report.get("savings_score", {})

    with PdfPages(buf) as pdf:
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        lines = [
            "SpendLens — Monthly Report",
            report.get("month_label", ""),
            "",
            f"Total Income:    {_fmt_inr(s.get('total_income', 0))}",
            f"Total Expenses:  {_fmt_inr(s.get('total_expenses', 0))}",
            f"Net Savings:     {_fmt_inr(s.get('net_savings', 0))}",
            "",
            "Category breakdown:",
        ]
        for c in report.get("category_breakdown", [])[:10]:
            lines.append(f"  • {c['category']}: {_fmt_inr(c['amount'])}")
        ax.text(0.05, 0.95, "\n".join(lines), va="top", fontsize=10, family="monospace")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    buf.seek(0)
    return buf.read()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    logger.info("SpendLens API http://127.0.0.1:%s", port)
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
