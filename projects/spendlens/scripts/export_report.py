"""Export analytics report JSON (for dashboard embed / refresh binding)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from analytics import run_pipeline


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data" / "sample_statement.csv"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "data" / "report.json"

    report = run_pipeline(str(src))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
