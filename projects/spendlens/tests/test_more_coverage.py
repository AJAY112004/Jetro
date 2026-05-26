from __future__ import annotations

import sys
from pathlib import Path

from app import app as flask_app
from report_cache import load_report, save_report
from stdlib_pipeline import run_pipeline
from backend.services.analysis_service import analyse_demo


def test_report_cache_save_and_load_roundtrip(tmp_path: Path):
    rid = save_report({"hello": "world"})
    loaded = load_report(rid)
    assert loaded is not None
    assert loaded["hello"] == "world"


def test_run_pipeline_pdf_with_mock_pdfplumber(tmp_path: Path):
    table = [
        ["Date", "Description", "Debit", "Credit"],
        ["01/05/2026", "Test One", "100", ""],
        ["02/05/2026", "Cafe", "50", ""],
    ]

    class FakePage:
        def extract_tables(self, table_settings=None):
            return [table]

    class FakePDF:
        def __init__(self):
            self.pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakePDFPlumberModule:
        @staticmethod
        def open(_path):
            return FakePDF()

    dummy_pdf = tmp_path / "stmt.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

    sys.modules["pdfplumber"] = FakePDFPlumberModule
    try:
        report = run_pipeline(dummy_pdf)
    finally:
        sys.modules.pop("pdfplumber", None)

    assert report["spend_summary"]["total_expenses"] >= 50
    assert report["category_breakdown"]


def test_analyse_demo_returns_empty_when_sample_and_fallback_missing():
    report = analyse_demo(
        Path("does-not-exist.csv"),
        fallback_report=Path("does-not-exist-report.json"),
        logger=flask_app.logger,
    )
    assert report == {}


def test_assets_route_serves_vite_chunks():
    client = flask_app.test_client()
    assets_dir = Path("frontend/dist/assets")
    if not assets_dir.is_dir():
        # Avoid failing local dev if frontend dist hasn't been built.
        return
    asset_files = sorted(assets_dir.glob("*"))
    assert asset_files, "Expected Vite build assets to exist"
    first = asset_files[0]
    resp = client.get(f"/assets/{first.name}")
    assert resp.status_code == 200

