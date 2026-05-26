"""
SpendLens Flask entrypoint.

Docker/Render expects `projects/spendlens/scripts/app.py` to expose `app: Flask`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from backend.app_factory import create_app

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent

# Keep `scripts/*.py` modules importable (analytics/categorise/parse_statement/etc).
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

app = create_app(project_root=PROJECT_ROOT, scripts_dir=SCRIPTS_DIR)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=debug, use_reloader=debug)

