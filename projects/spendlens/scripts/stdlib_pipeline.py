"""
SpendLens standard-library pipeline.

Design goals:
- No pandas dependency at runtime.
- Handles CSV statements robustly.
- Best-effort PDF table extraction via `pdfplumber` (no pandas).
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Shared categorisation rules (keep in sync with categorise.py)
RULES: list[tuple[str, str]] = [
    ("Income", r"salary|cashback|refund|neft cr|imps cr|deposit"),
    ("EMI & Loans", r"emi|loan"),
    ("Food & Dining", r"swiggy|zomato|dominos|barbeque|restaurant"),
    ("Groceries", r"bigbasket|blinkit|zepto|dmart|reliance fresh|grocery"),
    ("Shopping", r"amazon|flipkart|myntra|meesho"),
    ("Transport", r"ola|uber|rapido|hpcl|fuel|dmrc|metro|irctc|makemytrip"),
    ("Entertainment", r"netflix|spotify|prime|bookmyshow|cultfit"),
    ("Utilities", r"electricity|water|gas|broadband|jio|recharge|billpay"),
    ("Health", r"medplus|apollo|1mg|pharmacy|hospital"),
    ("Transfers", r"rent|landlord|neft dr|imps dr|transfer"),
    ("Other", r"atm"),
]

DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y")


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _parse_float(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip().replace(",", "")
    if not s or s in ("-", "—", "nan", "None"):
        return 0.0
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s == "-":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_date(val: str):
    val = (val or "").strip()
    if not val:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(val[:10]).date()
    except ValueError:
        return None


def _pick_column(headers: list[str], aliases: list[str]) -> str | None:
    normed = {_norm_header(h): h for h in headers}
    for alias in aliases:
        for nk, orig in normed.items():
            # Avoid false positives for short tokens like "cr"/"dr" matching words like "description".
            if alias == nk:
                return orig
            if len(alias) >= 4 and alias in nk:
                return orig
    return None


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(path, newline="", encoding=encoding) as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ValueError("CSV has no header row")
                rows = [dict(r) for r in reader if any(str(v).strip() for v in r.values())]
                return rows, list(reader.fieldnames)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not read CSV: {path}")


def parse_csv_file(path: Path) -> list[dict[str, Any]]:
    """Parse CSV into normalised rows: date, description, debit, credit."""
    raw_rows, headers = _read_csv_rows(path)

    col_date = _pick_column(headers, ["date", "txn date", "transaction date", "value dt", "value date"])
    col_desc = _pick_column(
        headers, ["narration", "description", "particulars", "remarks", "transaction remarks"]
    )
    col_debit = _pick_column(
        headers, ["withdrawal amt.", "withdrawal", "debit", "debit amount", "dr", "withdrawal amount"]
    )
    col_credit = _pick_column(
        headers, ["deposit amt.", "deposit", "credit", "credit amount", "cr", "deposit amount"]
    )
    col_amount = _pick_column(headers, ["amount", "amount(inr)", "transaction amount"])
    col_type = _pick_column(headers, ["transaction type", "dr/cr", "type"])

    if not col_desc:
        raise ValueError(
            f"Could not find description column. Headers: {headers}. "
            "Expected Narration, Description, or Particulars."
        )

    transactions: list[dict[str, Any]] = []

    for row in raw_rows:
        desc = (row.get(col_desc) or "").strip()
        if not desc:
            continue
        if re.match(r"^(opening|closing) balance", desc, re.I):
            continue

        debit = credit = 0.0
        if col_debit or col_credit:
            debit = _parse_float(row.get(col_debit or "", 0))
            credit = _parse_float(row.get(col_credit or "", 0))
        elif col_amount:
            amt = _parse_float(row.get(col_amount))
            typ = (row.get(col_type) or "").strip().upper() if col_type else ""
            if typ in ("DR", "DEBIT", "D", "WITHDRAWAL"):
                debit = amt
            elif typ in ("CR", "CREDIT", "C", "DEPOSIT"):
                credit = amt
            elif amt < 0:
                debit = abs(amt)
            else:
                debit = amt

        if debit == 0 and credit == 0:
            continue

        dt = _parse_date(row.get(col_date or "", "")) if col_date else None

        transactions.append(
            {
                "date": dt,
                "description": desc,
                "debit": debit,
                "credit": credit,
            }
        )

    if not transactions:
        raise ValueError("No transactions found in CSV. Check column headers and data rows.")

    # Deduplicate identical rows (some exports repeat headers/rows mid-file).
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for t in transactions:
        key = (
            f"{t.get('date')}|{t.get('description')}|"
            f"{round(float(t.get('debit') or 0), 2)}|{round(float(t.get('credit') or 0), 2)}"
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)

    return unique


def parse_pdf_file(path: Path) -> list[dict[str, Any]]:
    """
    Best-effort PDF parsing via pdfplumber table extraction.

    Note: This is intentionally kept pandas-free to avoid native-library crashes.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber is required for PDF parsing.") from exc

    all_tables: list[list[list[Any]]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 4,
                    "join_tolerance": 4,
                }
            )
            if tables:
                all_tables.extend(tables)

    transactions: list[dict[str, Any]] = []

    for table in all_tables:
        if not table or len(table) < 2:
            continue
        header = [str(c or "").strip() for c in table[0]]
        rows = table[1:]

        col_date = _pick_column(header, ["date", "txn date", "transaction date", "value dt", "value date"])
        col_desc = _pick_column(
            header,
            ["narration", "description", "particulars", "remarks", "transaction remarks"],
        )
        col_debit = _pick_column(
            header,
            ["withdrawal amt.", "withdrawal", "debit", "debit amount", "dr", "withdrawal amount"],
        )
        col_credit = _pick_column(
            header,
            ["deposit amt.", "deposit", "credit", "credit amount", "cr", "deposit amount"],
        )
        col_amount = _pick_column(header, ["amount", "amount(inr)", "transaction amount"])
        col_type = _pick_column(header, ["transaction type", "dr/cr", "type"])

        for r in rows:
            row = list(r) + [None] * max(0, len(header) - len(r))

            desc = (row[header.index(col_desc)] if col_desc and col_desc in header else "") or ""
            desc = str(desc).strip()
            if not desc:
                continue
            if re.match(r"^(opening|closing) balance", desc, re.I):
                continue

            debit = credit = 0.0
            if col_debit or col_credit:
                if col_debit and col_debit in header:
                    debit = _parse_float(row[header.index(col_debit)])
                if col_credit and col_credit in header:
                    credit = _parse_float(row[header.index(col_credit)])
            elif col_amount and col_type:
                idx_amt = header.index(col_amount)
                idx_type = header.index(col_type)
                amt = _parse_float(row[idx_amt])
                typ = (str(row[idx_type]) if row[idx_type] is not None else "").strip().upper()
                if typ in ("DR", "DEBIT", "D", "WITHDRAWAL"):
                    debit = amt
                elif typ in ("CR", "CREDIT", "C", "DEPOSIT"):
                    credit = amt
                elif amt < 0:
                    debit = abs(amt)
                else:
                    debit = amt

            if debit == 0 and credit == 0:
                continue

            dt = _parse_date(row[header.index(col_date)]) if col_date and col_date in header else None
            transactions.append({"date": dt, "description": desc, "debit": debit, "credit": credit})

    if not transactions:
        raise ValueError("No transactions found in PDF. Check table extraction quality.")

    # Deduplicate identical rows.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for t in transactions:
        key = (
            f"{t.get('date')}|{t.get('description')}|{round(float(t.get('debit') or 0),2)}|{round(float(t.get('credit') or 0),2)}"
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)

    return unique


def categorise_desc(desc: str) -> str:
    d = desc.lower()
    for name, pat in RULES:
        if re.search(pat, d):
            return name
    return "Other"


def _merchant(desc: str) -> str:
    for token in re.split(r"[-/@]", desc):
        t = token.strip()
        if len(t) > 3 and not t.isdigit():
            return t[:36]
    return desc[:36] if desc else "Unknown"


def _savings_score(rate: float) -> tuple[int, str, str]:
    if rate > 40:
        return 95, "Excellent", "#22c55e"
    if rate >= 25:
        return 78, "Good", "#3b82f6"
    if rate >= 10:
        return 58, "Fair", "#eab308"
    if rate >= 0:
        return 38, "Poor", "#f97316"
    return 15, "Critical", "#ef4444"


def build_report_from_transactions(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    income = sum(t["credit"] for t in transactions)
    expenses = sum(t["debit"] for t in transactions)
    net = income - expenses
    rate = (net / income * 100) if income else 0.0
    score, label, colour = _savings_score(rate)

    by_cat: dict[str, float] = defaultdict(float)
    by_merch: dict[str, float] = defaultdict(float)
    daily: dict[str, float] = defaultdict(float)
    debits: list[dict[str, Any]] = []

    for t in transactions:
        if t["debit"] <= 0:
            continue
        c = categorise_desc(t["description"])
        by_cat[c] += t["debit"]
        by_merch[_merchant(t["description"])] += t["debit"]
        if t["date"]:
            daily[str(t["date"])] += t["debit"]
        debits.append({**t, "category": c})

    cats = sorted(
        [
            {
                "category": k,
                "amount": round(v, 2),
                "pct": round(v / expenses * 100, 1) if expenses else 0,
                "vs_last_month_pct": None,
            }
            for k, v in by_cat.items()
            if k != "Income"
        ],
        key=lambda x: -x["amount"],
    )

    top_m = sorted(by_merch.items(), key=lambda x: -x[1])[:5]

    anomalies: list[dict[str, Any]] = []
    cat_counts: dict[str, int] = defaultdict(int)
    for d in debits:
        cat_counts[d["category"]] += 1
    cat_avg = {k: by_cat[k] / max(1, cat_counts[k]) for k in by_cat}

    for d in debits:
        avg = cat_avg.get(d["category"], d["debit"])
        if avg > 0 and d["debit"] > 2 * avg and d["debit"] > 1000:
            anomalies.append(
                {
                    "type": "unusual_amount",
                    "date": str(d.get("date") or ""),
                    "description": d["description"][:80],
                    "amount": d["debit"],
                    "category": d["category"],
                    "message": f"₹{d['debit']:,.0f} is >2× {d['category']} average (₹{avg:,.0f})",
                }
            )

    subs = [
        d
        for d in debits
        if re.search(r"netflix|spotify|prime|jio|airtel|cultfit|broadband", d["description"], re.I)
    ]
    sub_merchants = {_merchant(d["description"]) for d in subs}

    month_label = "This month"
    dates = [t["date"] for t in transactions if t["date"]]
    if dates:
        month_label = dates[0].strftime("%B %Y")

    insights: list[str] = []
    if cats:
        insights.append(
            f"Your biggest spend category is {cats[0]['category']} at "
            f"₹{cats[0]['amount']:,.0f} ({cats[0]['pct']:.0f}%)"
        )
    if sub_merchants:
        insights.append(
            f"You have {len(sub_merchants)} active subscriptions totalling "
            f"₹{sum(d['debit'] for d in subs):,.0f}/month"
        )
    if income > 0:
        extra = max(0, income * 0.25 - net)
        insights.append(
            f"Your savings rate is {rate:.0f}% — increase by ₹{extra:,.0f}/month to reach 25%"
        )
    while len(insights) < 3:
        insights.append("Review discretionary spending to improve your savings rate.")
        break

    rebal = (
        f"If you reduce {cats[0]['category']} by 20%, you save an extra ₹{cats[0]['amount'] * 0.2:,.0f}/month"
        if cats
        else "Track spending weekly to spot savings opportunities."
    )

    hi_day = lo_day = None
    if daily:
        hi_key = max(daily, key=daily.get)
        lo_key = min(daily, key=daily.get)
        hi_day = {"date": hi_key, "spend": daily[hi_key]}
        lo_day = {"date": lo_key, "spend": daily[lo_key]}

    return {
        "month_label": month_label,
        "transaction_count": len(transactions),
        "stats": {
            "transaction_count": len(transactions),
            "avg_daily_spend": round(expenses / max(1, len(daily)), 0),
            "highest_spend_day": hi_day,
            "lowest_spend_day": lo_day,
        },
        "spend_summary": {
            "total_income": round(income, 2),
            "total_expenses": round(expenses, 2),
            "net_savings": round(net, 2),
            "savings_rate_pct": round(rate, 1),
        },
        "category_breakdown": cats,
        "top_merchants": [{"merchant": m, "amount": round(a, 2)} for m, a in top_m],
        "savings_score": {
            "score": score,
            "label": label,
            "colour": colour,
            "savings_rate_pct": round(rate, 1),
        },
        "anomalies": anomalies[:12],
        "daily_spend_trend": [{"date": k, "spend": round(v, 2)} for k, v in sorted(daily.items())],
        "subscription_summary": {
            "count": len(sub_merchants),
            "monthly_total": round(sum(d["debit"] for d in subs), 2),
        },
        "ai_insights": insights[:3],
        "rebalancing_recommendation": rebal,
    }


def run_pipeline(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        txs = parse_csv_file(path)
        return build_report_from_transactions(txs)
    if path.suffix.lower() == ".pdf":
        txs = parse_pdf_file(path)
        return build_report_from_transactions(txs)
    raise ValueError("Unsupported file type for stdlib pipeline (use .csv or .pdf)")
