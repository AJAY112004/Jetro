"""Server-side report cache (Flask session cookies are too small for full reports)."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "reports"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    # numpy/pandas scalars without importing numpy
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return obj.item()
        except Exception:
            pass
    if hasattr(obj, "tolist") and callable(obj.tolist):
        try:
            return obj.tolist()
        except Exception:
            pass
    return str(obj)


def json_safe(value: Any) -> Any:
    """Round-trip through JSON to ensure Flask jsonify compatibility."""
    return json.loads(json.dumps(value, default=_json_default))


def save_report(report: dict) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    report_id = uuid.uuid4().hex
    path = CACHE_DIR / f"{report_id}.json"
    path.write_text(
        json.dumps(json_safe(report), indent=2),
        encoding="utf-8",
    )
    return report_id


def load_report(report_id: str | None) -> dict | None:
    if not report_id:
        return None
    path = CACHE_DIR / f"{report_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
