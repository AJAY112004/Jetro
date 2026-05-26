from __future__ import annotations

import logging
import os
import sys
import tempfile
import traceback
from pathlib import Path

from flask import Flask, abort, render_template, send_file
from flask_cors import CORS

from backend.routes.api import api_bp
from backend.utils.errors import register_error_handlers
from backend.utils.security import init_jwt, init_limiter, init_security_headers


def create_app(*, project_root: Path, scripts_dir: Path) -> Flask:
    """
    Backend factory. Keeps a stable API surface while allowing modular code in `backend/`.
    """
    # Ensure existing analytics/csv/pdf modules (still under `scripts/`) resolve.
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    app_version = os.environ.get("SPENDLENS_APP_VERSION")
    try:
        from pdf_report import PDF_BUILD_ID

        app_version = app_version or PDF_BUILD_ID
    except Exception:
        app_version = app_version or "1.0"

    logger = logging.getLogger("spendlens")
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    app = Flask(__name__, template_folder=str(scripts_dir / "templates"))
    app.logger = logger
    app.config["APP_VERSION"] = app_version

    # App paths used by services.
    app.config["SAMPLE_CSV"] = project_root / "data" / "sample_statement.csv"
    app.config["FALLBACK_REPORT"] = project_root / "data" / "report.json"
    app.config["UPLOAD_DIR"] = Path(tempfile.gettempdir()) / "spendlens_uploads"

    # Security / session.
    app.secret_key = os.environ.get("SPENDLENS_SECRET", "spendlens-local-dev-key")
    app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_BYTES", 16 * 1024 * 1024))

    if os.environ.get("SESSION_COOKIE_SECURE", "0") == "1":
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # CORS: cross-origin only when explicitly configured.
    cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "") or ""
    origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    if origins:
        CORS(
            app,
            resources={r"/api/*": {"origins": origins}},
            supports_credentials=True,
            methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Accept", "Authorization", "X-Requested-With"],
            expose_headers=["Content-Disposition", "Content-Type", "Content-Length"],
        )

    # Security headers and auth/rate limiting.
    init_security_headers(app)
    init_jwt(app)
    init_limiter(app)

    register_error_handlers(app)

    # API routes.
    app.register_blueprint(api_bp)

    # Frontend serving (React build).
    frontend_dist = project_root / "frontend" / "dist"
    if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
        index_file = frontend_dist / "index.html"

        assets_dir = frontend_dist / "assets"

        def serve_frontend():
            return send_file(index_file)

        @app.route("/", methods=["GET"])
        def home():
            return serve_frontend()

        @app.route("/results", methods=["GET"])
        def results_page():
            return serve_frontend()

        @app.route("/demo", methods=["GET"])
        def demo_page():
            return serve_frontend()

        # Serve Vite static assets; without this, hashed chunks won't load.
        @app.route("/assets/<path:filename>", methods=["GET"])
        def assets(filename: str):
            if not assets_dir.is_dir():
                abort(404)
            return send_file(assets_dir / filename)

        @app.route("/<path:path>", methods=["GET"])
        def spa_fallback(path: str):
            if path.startswith("api/") or path.startswith("api"):
                abort(404)

            # If a real file exists in dist (e.g. favicon), serve it.
            candidate = frontend_dist / path
            if candidate.is_file():
                return send_file(candidate)

            return serve_frontend()

    else:
        # Dev fallback: server renders the static templates.
        @app.route("/", methods=["GET"])
        def home():
            return render_template("index.html", api_base="/api")

        @app.route("/results", methods=["GET"])
        def results_page():
            return render_template("results.html", report=None)

    return app

