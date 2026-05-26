from __future__ import annotations

from pathlib import Path

from stdlib_pipeline import parse_csv_file, run_pipeline


def test_parse_csv_dedupes_identical_rows(tmp_path: Path):
    csv_text = """Date,Description,Debit,Credit
01/05/2026,Test One,100,
01/05/2026,Test One,100,
"""
    p = tmp_path / "stmt.csv"
    p.write_text(csv_text, encoding="utf-8")

    txs = parse_csv_file(p)
    assert len(txs) == 1
    assert txs[0]["description"] == "Test One"
    assert float(txs[0]["debit"]) == 100.0
    assert float(txs[0]["credit"]) == 0.0


def test_run_pipeline_csv_returns_report(tmp_path: Path):
    csv_text = """Date,Description,Debit,Credit
01/05/2026,Salary,,50000
02/05/2026,Cafe,250,
"""
    p = tmp_path / "stmt.csv"
    p.write_text(csv_text, encoding="utf-8")

    report = run_pipeline(p)
    assert report["spend_summary"]["total_income"] >= 50000
    assert report["spend_summary"]["total_expenses"] >= 250
    assert "category_breakdown" in report


def test_parse_csv_amount_and_transaction_type_splits_debit_credit(tmp_path: Path):
    # Layout with Amount + Transaction Type only (no explicit Debit/Credit columns).
    csv_text = (
        "Date,Description,Amount,Transaction Type\n"
        "01/05/2026,Cafe,250,DR\n"
        "02/05/2026,Salary,50000,CR\n"
    )
    p = tmp_path / "stmt.csv"
    p.write_text(csv_text, encoding="utf-8")

    report = run_pipeline(p)
    assert report["spend_summary"]["total_expenses"] >= 250
    assert report["spend_summary"]["total_income"] >= 50000

