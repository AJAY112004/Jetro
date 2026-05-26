from __future__ import annotations

import logging
from pathlib import Path

from backend.services.analysis_service import analyse_file, analyse_demo


def test_analyse_file_unsupported_extension_raises(tmp_path: Path):
    logger = logging.getLogger("test")
    p = tmp_path / "stmt.txt"
    p.write_text("hello", encoding="utf-8")
    try:
        analyse_file(
            p,
            sample_csv=Path("data") / "sample_statement.csv",
            fallback_report=Path("data") / "report.json",
            logger=logger,
        )
    except ValueError as exc:
        assert "Unsupported file type" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_analyse_file_falls_back_on_bad_csv_name(tmp_path: Path):
    logger = logging.getLogger("test")
    # Trigger the hardcoded sample fallback branch.
    bad = tmp_path / "sample_statement.csv"
    bad.write_text("not,a,bank,statement", encoding="utf-8")

    report = analyse_file(
        bad,
        sample_csv=Path("data") / "sample_statement.csv",
        fallback_report=Path("data") / "report.json",
        logger=logger,
    )
    assert report.get("spend_summary")
    assert "category_breakdown" in report


def test_analyse_demo_returns_report():
    logger = logging.getLogger("test")
    report = analyse_demo(
        Path("data") / "sample_statement.csv",
        fallback_report=Path("data") / "report.json",
        logger=logger,
    )
    assert report.get("spend_summary")

