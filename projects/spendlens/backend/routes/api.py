from __future__ import annotations

import io
import os
import traceback
from pathlib import Path

from flask import Blueprint, Response, current_app, request, send_file, session
from werkzeug.utils import secure_filename

from backend.services.analysis_service import analyse_demo, analyse_file
from backend.services.pdf_service import build_pdf_bytes
from backend.services.report_service import load_session_report, store_report
from backend.utils.errors import json_error, json_ok
from backend.utils.security import issue_jwt_token, require_auth

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/health")
def health():
    return json_ok({"service": "spendlens", "version": current_app.config.get("APP_VERSION", "1.0")})


@api_bp.get("/demo")
def demo():
    try:
        report = analyse_demo(
            current_app.config["SAMPLE_CSV"],
            fallback_report=current_app.config["FALLBACK_REPORT"],
            logger=current_app.logger,
        )
    except Exception as exc:
        return json_error(current_app, f"Demo failed: {exc}", 500, detail=traceback.format_exc())

    # Store so /api/download-pdf can work.
    report_id = store_report(report, logger=current_app.logger)
    return json_ok({"report": report, "report_id": report_id})


@api_bp.get("/auth/token")
def auth_token():
    if not current_app.config.get("JWT_ENABLED", False):
        # Still return a compatible shape.
        return json_ok({"token": None, "expiresIn": 0, "jwtEnabled": False})

    user_id = session.get("user_id")
    if not user_id:
        import uuid

        user_id = uuid.uuid4().hex
        session["user_id"] = user_id

    token = issue_jwt_token(current_app, user_id)
    return json_ok({"token": token, "expiresIn": 60 * 60 * 24 * 7, "jwtEnabled": True})


@api_bp.post("/analyse")
@require_auth  # protected when JWT_ENABLED=1
def analyse():
    if "statement" not in request.files:
        return json_error(current_app, "No files in request. Expected multipart/form-data field 'statement'.", 400)

    file = request.files.get("statement")
    if not file or not file.filename:
        return json_error(current_app, "Missing file field 'statement'.", 400)

    ext = Path(file.filename).suffix.lower()
    if ext not in (".csv", ".pdf"):
        return json_error(current_app, "Only PDF and CSV files are supported.", 400)

    uploads_dir: Path = current_app.config["UPLOAD_DIR"]
    uploads_dir.mkdir(parents=True, exist_ok=True)

    dest = None
    try:
        safe_name = secure_filename(file.filename) or "statement"
        dest = uploads_dir / f"upload_{os.getpid()}_{session.get('user_id','anon')}_{safe_name}"
        file.save(dest)

        report = analyse_file(
            dest,
            sample_csv=current_app.config["SAMPLE_CSV"],
            fallback_report=current_app.config["FALLBACK_REPORT"],
            logger=current_app.logger,
        )

        report_id = store_report(report, logger=current_app.logger)
        return json_ok({"report": report, "report_id": report_id})
    except Exception as exc:
        return json_error(current_app, f"Analysis failed: {exc}", 500, detail=traceback.format_exc())
    finally:
        if dest is not None and dest.exists():
            dest.unlink(missing_ok=True)


@api_bp.post("/analyze")
@require_auth
def analyse_alias_analyze():
    return analyse()


@api_bp.get("/download-pdf")
@require_auth
def download_pdf():
    report = load_session_report()
    if not report:
        return json_error(current_app, "No report found in session. Run /api/analyse first.", 404)

    try:
        pdf_bytes = build_pdf_bytes(report)
        return _pdf_response_from_bytes(pdf_bytes, filename="spendlens_report.pdf")
    except Exception as exc:
        return json_error(current_app, f"PDF generation failed: {exc}", 500, detail=traceback.format_exc())


def _pdf_response_from_bytes(pdf_bytes: bytes, *, filename: str) -> Response:
    resp = send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    # For fetch()+blob download: ensure browser can read filename.
    resp.headers.setdefault("Access-Control-Expose-Headers", "Content-Disposition, Content-Type, Content-Length")
    return resp

