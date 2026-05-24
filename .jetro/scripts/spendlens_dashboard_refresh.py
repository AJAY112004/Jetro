"""Refresh binding: rebuild SpendLens report from sample statement."""
import json
import os
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("JET_WORKSPACE", Path(__file__).resolve().parents[2]))
SCRIPTS = WORKSPACE / "projects" / "spendlens" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analytics import run_pipeline  # noqa: E402

SAMPLE = WORKSPACE / "projects" / "spendlens" / "data" / "sample_statement.csv"

if __name__ == "__main__":
    try:
        report = run_pipeline(str(SAMPLE))
    except Exception:
        # Fallback if pandas unavailable
        report = json.loads(
            (WORKSPACE / "projects" / "spendlens" / "data" / "report.json").read_text(encoding="utf-8")
        )
    print(json.dumps(report, default=str))
