"""
Jetro deploy entrypoint for SpendLens.

Jetro expects: projects/spendlens/deploy/server.py
Runs the Flask app from projects/spendlens/scripts/app.py on 0.0.0.0:PORT.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
os.chdir(PROJECT_ROOT)

os.environ.setdefault("FLASK_DEBUG", "0")
os.environ.setdefault("SESSION_COOKIE_SECURE", "1")
os.environ.setdefault("LOG_LEVEL", "INFO")


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    workers = os.environ.get("GUNICORN_WORKERS", "2")
    threads = os.environ.get("GUNICORN_THREADS", "4")

    # Prefer gunicorn in Linux containers (Jetro deploy uses Docker).
    if os.environ.get("USE_GUNICORN", "1") == "1":
        try:
            from gunicorn.app.wsgiapp import run

            sys.argv = [
                "gunicorn",
                "--bind",
                f"0.0.0.0:{port}",
                "--workers",
                workers,
                "--threads",
                threads,
                "--timeout",
                "120",
                "--chdir",
                str(SCRIPTS_DIR),
                "app:app",
            ]
            run()
            return
        except ImportError:
            pass

    from app import app  # noqa: E402

    from waitress import serve

    print(f"SpendLens (waitress) http://0.0.0.0:{port}", flush=True)
    serve(app, host="0.0.0.0", port=port, threads=4)


if __name__ == "__main__":
    main()
