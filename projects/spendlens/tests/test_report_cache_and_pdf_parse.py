from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from report_cache import json_safe, _json_default
from stdlib_pipeline import parse_pdf_file


def test_json_safe_converts_datetime_and_decimal():
    payload = {"d": datetime(2026, 5, 1, 12, 30, 0), "x": Decimal("12.34"), "n": 1}
    safe = json_safe(payload)
    assert isinstance(safe["d"], str)
    assert isinstance(safe["x"], float)

    # _json_default is exercised via json_safe, but sanity-check one path.
    assert _json_default(date(2026, 1, 1)) == "2026-01-01"


def test_report_cache_load_report_none_and_missing():
    from report_cache import load_report

    assert load_report(None) is None
    assert load_report("does-not-exist") is None


def test_json_default_handles_item_and_tolist_attributes():
    class HasItem:
        def item(self):
            return 123

    class HasToList:
        def tolist(self):
            return [1, 2, 3]

    assert _json_default(HasItem()) == 123
    assert _json_default(HasToList()) == [1, 2, 3]


def test_parse_pdf_file_dedupes_identical_rows(tmp_path: Path):
    # Build a minimal table that resembles a bank export.
    table = [
        ["Date", "Description", "Debit", "Credit"],
        ["01/05/2026", "Test One", "100", ""],
        ["01/05/2026", "Test One", "100", ""],
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
        txs = parse_pdf_file(dummy_pdf)
    finally:
        sys.modules.pop("pdfplumber", None)

    assert len(txs) == 1
    assert float(txs[0]["debit"]) == 100.0
    assert float(txs[0]["credit"]) == 0.0
    assert txs[0]["description"] == "Test One"

