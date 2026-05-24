"""Generate report.json without pandas (stdlib only) for dashboard bootstrap."""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "sample_statement.csv"
OUT_PATH = ROOT / "data" / "report.json"

RULES = [
    ("Income", r"salary|cashback|refund|neft cr|imps cr"),
    ("EMI & Loans", r"emi|loan"),
    ("Food & Dining", r"swiggy|zomato|dominos|barbeque|restaurant"),
    ("Groceries", r"bigbasket|blinkit|zepto|dmart|reliance fresh"),
    ("Shopping", r"amazon|flipkart|myntra|meesho"),
    ("Transport", r"ola|uber|rapido|hpcl|fuel|dmrc|metro|irctc|makemytrip"),
    ("Entertainment", r"netflix|spotify|prime|bookmyshow|cultfit"),
    ("Utilities", r"electricity|water|gas|broadband|jio|recharge|billpay"),
    ("Health", r"medplus|apollo|1mg|pharmacy|hospital"),
    ("Transfers", r"rent|landlord|rahul|priya|neft dr|imps dr"),
    ("Other", r"atm"),
]


def cat(desc: str) -> str:
    d = desc.lower()
    for name, pat in RULES:
        if re.search(pat, d):
            return name
    return "Other"


def merchant(desc: str) -> str:
    for token in re.split(r"[-/@]", desc):
        t = token.strip()
        if len(t) > 3 and not t.isdigit():
            return t[:36]
    return desc[:36]


def main() -> None:
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            w = float(r["Withdrawal Amt."] or 0)
            d = float(r["Deposit Amt."] or 0)
            dt = datetime.strptime(r["Date"], "%d/%m/%Y").date()
            rows.append({"date": dt, "desc": r["Narration"], "debit": w, "credit": d})

    income = sum(r["credit"] for r in rows)
    expenses = sum(r["debit"] for r in rows)
    net = income - expenses
    rate = (net / income * 100) if income else 0
    score = 15 if rate < 0 else (38 if rate < 10 else 58)
    label = "Critical" if rate < 0 else "Poor"
    colour = "#ef4444" if rate < 0 else "#f97316"

    by_cat: dict[str, float] = defaultdict(float)
    by_merch: dict[str, float] = defaultdict(float)
    daily: dict[str, float] = defaultdict(float)
    debits = []

    for r in rows:
        if r["debit"] <= 0:
            continue
        c = cat(r["desc"])
        by_cat[c] += r["debit"]
        by_merch[merchant(r["desc"])] += r["debit"]
        daily[str(r["date"])] += r["debit"]
        debits.append({**r, "category": c})

    cats = sorted(
        [{"category": k, "amount": v, "pct": round(v / expenses * 100, 1), "vs_last_month_pct": None}
         for k, v in by_cat.items() if k != "Income"],
        key=lambda x: -x["amount"],
    )
    top_m = sorted(by_merch.items(), key=lambda x: -x[1])[:5]

    anomalies = []
    cat_avg = {k: v / max(1, sum(1 for d in debits if d["category"] == k)) for k, v in by_cat.items()}
    for d in debits:
        avg = cat_avg.get(d["category"], d["debit"])
        if d["debit"] > 2 * avg and d["debit"] > 5000:
            anomalies.append({
                "type": "unusual_amount",
                "date": str(d["date"]),
                "description": d["desc"][:60],
                "amount": d["debit"],
                "category": d["category"],
                "message": f"₹{d['debit']:,.0f} is >2× {d['category']} average (₹{avg:,.0f})",
            })

    subs = [d for d in debits if re.search(r"netflix|spotify|prime|jio|airtel|cultfit", d["desc"], re.I)]
    sub_merchants = {merchant(d["desc"]) for d in subs}

    report = {
        "month_label": "April 2026",
        "spend_summary": {
            "total_income": round(income, 2),
            "total_expenses": round(expenses, 2),
            "net_savings": round(net, 2),
            "savings_rate_pct": round(rate, 1),
        },
        "category_breakdown": cats,
        "top_merchants": [{"merchant": m, "amount": a} for m, a in top_m],
        "savings_score": {"score": score, "label": label, "colour": colour, "savings_rate_pct": round(rate, 1)},
        "anomalies": anomalies[:8],
        "daily_spend_trend": [{"date": k, "spend": v} for k, v in sorted(daily.items())],
        "subscription_summary": {"count": len(sub_merchants), "monthly_total": sum(d["debit"] for d in subs)},
        "ai_insights": [
            f"Your biggest spend category is {cats[0]['category']} at ₹{cats[0]['amount']:,.0f} ({cats[0]['pct']:.0f}%)",
            f"You have {len(sub_merchants)} active subscriptions totalling ₹{sum(d['debit'] for d in subs):,.0f}/month",
            f"Your savings rate is {rate:.0f}% — increase by ₹{max(0, income * 0.25 - net):,.0f}/month to reach 25%",
        ],
        "rebalancing_recommendation": (
            f"If you reduce {cats[0]['category']} by 20%, you save an extra ₹{cats[0]['amount'] * 0.2:,.0f}/month"
        ),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(OUT_PATH)


if __name__ == "__main__":
    main()
