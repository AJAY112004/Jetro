import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Ensure `import stdlib_pipeline` and friends resolve during tests.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Backend auth + sessions.
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("SPENDLENS_SECRET", "test-spendlens-secret-change-me")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-change-me-change-me-please-32+")
os.environ.setdefault("SESSION_COOKIE_SECURE", "0")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "")

