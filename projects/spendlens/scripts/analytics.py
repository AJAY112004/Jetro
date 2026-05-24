"""
SpendLens analytics engine — builds a structured `report` dict from a categorised DataFrame.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd

SUBSCRIPTION_KEYWORDS = re.compile(
    r"\b(netflix|spotify|prime video|amazon prime|jio|airtel|broadband|"
    r"cult\.?fit|cultfit|hotstar|sonyliv|youtube premium)\b",
    re.I,
)

SCORE_BANDS = [
    (90, 100, 40.0, float("inf"), "Excellent"),
    (70, 89, 25.0, 40.0, "Good"),
    (50, 69, 10.0, 25.0, "Fair"),
    (30, 49, 0.0, 10.0, "Poor"),
    (0, 29, float("-inf"), 0.0, "Critical"),
]


def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date" not in out.columns:
        return out
    out["_dt"] = pd.to_datetime(out["date"], errors="coerce")
    return out


def _extract_merchant(row: pd.Series) -> str:
    sub = str(row.get("sub_category", "") or "").strip()
    if sub and sub.lower() not in ("uncategorised", "emi", "credit", "salary"):
        return sub
    desc = str(row.get("description", "") or "")
    for part in re.split(r"[-/@]", desc):
        part = part.strip()
        if len(part) > 2 and not part.isdigit():
            return part[:40]
    return desc[:40] if desc else "Unknown"


def _savings_score_and_label(savings_rate: float) -> tuple[int, str, str]:
    """Return (score 0-100, label, colour hex)."""
    if savings_rate > 40:
        return 95, "Excellent", "#22c55e"
    if savings_rate >= 25:
        return 78, "Good", "#3b82f6"
    if savings_rate >= 10:
        return 58, "Fair", "#eab308"
    if savings_rate >= 0:
        return 38, "Poor", "#f97316"
    return 15, "Critical", "#ef4444"


def _detect_unusual_transactions(df: pd.DataFrame) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    expenses = df[df["debit"] > 0].copy()
    if expenses.empty:
        return flags

    cat_avg = expenses.groupby("category")["debit"].mean()
    for _, row in expenses.iterrows():
        cat = row.get("category", "Other")
        avg = cat_avg.get(cat, row["debit"])
        if avg > 0 and row["debit"] > 2 * avg:
            flags.append(
                {
                    "type": "unusual_amount",
                    "date": str(row.get("date", "")),
                    "description": row["description"],
                    "amount": float(row["debit"]),
                    "category": cat,
                    "message": f"₹{row['debit']:,.0f} is >2× {cat} average (₹{avg:,.0f})",
                }
            )
    return flags


def _detect_duplicates(df: pd.DataFrame) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    expenses = _ensure_datetime(df[df["debit"] > 0].copy())
    if expenses.empty or "_dt" not in expenses.columns:
        return flags

    expenses["merchant"] = expenses.apply(_extract_merchant, axis=1)
    expenses = expenses.sort_values("_dt").reset_index(drop=True)
    flagged_idx: set[int] = set()

    for i in range(1, len(expenses)):
        if i in flagged_idx:
            continue
        row = expenses.iloc[i]
        dt = row["_dt"]
        if pd.isna(dt):
            continue
        for j in range(i):
            prev = expenses.iloc[j]
            if abs(float(prev["debit"]) - float(row["debit"])) > 0.01:
                continue
            if prev["merchant"].lower() != row["merchant"].lower():
                continue
            if pd.isna(prev["_dt"]):
                continue
            if abs((dt - prev["_dt"]).total_seconds()) <= 86400:
                flags.append(
                    {
                        "type": "duplicate",
                        "date": str(row.get("date", "")),
                        "description": row["description"],
                        "amount": float(row["debit"]),
                        "category": row.get("category", "Other"),
                        "message": (
                            "Possible duplicate: same amount & merchant within 24h "
                            f"({str(prev['description'])[:35]}…)"
                        ),
                    }
                )
                flagged_idx.add(i)
                break
    return flags


def _detect_weekend_spike(df: pd.DataFrame) -> list[dict[str, Any]]:
    expenses = _ensure_datetime(df[df["debit"] > 0].copy())
    if expenses.empty or "_dt" not in expenses.columns:
        return []

    expenses["dow"] = expenses["_dt"].dt.dayofweek
    weekday = expenses[expenses["dow"] < 5]["debit"].mean()
    weekend = expenses[expenses["dow"] >= 5]["debit"].mean()
    if pd.isna(weekday) or pd.isna(weekend) or weekday <= 0:
        return []

    if weekend > weekday * 1.35:
        return [
            {
                "type": "weekend_spike",
                "date": "",
                "description": "Weekend spending pattern",
                "amount": float(weekend),
                "category": "All",
                "message": (
                    f"Weekend avg spend ₹{weekend:,.0f} is "
                    f"{((weekend / weekday) - 1) * 100:.0f}% above weekday avg ₹{weekday:,.0f}"
                ),
            }
        ]
    return []


def _detect_subscription_leaks(df: pd.DataFrame) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    expenses = df[df["debit"] > 0].copy()
    subs = expenses[expenses["description"].str.contains(SUBSCRIPTION_KEYWORDS, na=False)]
    if subs.empty:
        return flags

    grouped = subs.groupby(subs.apply(_extract_merchant, axis=1))["debit"].agg(["sum", "count", "mean"])
    for merchant, row in grouped.iterrows():
        flags.append(
            {
                "type": "subscription",
                "date": "",
                "description": merchant,
                "amount": float(row["mean"]),
                "category": "Entertainment",
                "message": f"Recurring charge ~₹{row['mean']:,.0f}/txn ({int(row['count'])}× this period)",
            }
        )
    return flags


def _daily_spend_trend(df: pd.DataFrame) -> list[dict[str, Any]]:
    expenses = _ensure_datetime(df[df["debit"] > 0].copy())
    if expenses.empty or "_dt" not in expenses.columns:
        return []

    daily = expenses.groupby(expenses["_dt"].dt.date)["debit"].sum().sort_index()
    return [{"date": str(d), "spend": float(v)} for d, v in daily.items()]


def _generate_insights(report: dict[str, Any]) -> list[str]:
    insights: list[str] = []
    cats = report.get("category_breakdown", [])
    if cats:
        top = cats[0]
        insights.append(
            f"Your biggest spend category is {top['category']} at "
            f"₹{top['amount']:,.0f} ({top['pct']:.0f}%)"
        )

    subs = report.get("subscription_summary", {})
    n = subs.get("count", 0)
    total = subs.get("monthly_total", 0)
    if n > 0:
        insights.append(
            f"You have {n} active subscription{'s' if n != 1 else ''} totalling ₹{total:,.0f}/month"
        )

    summary = report.get("spend_summary", {})
    rate = summary.get("savings_rate_pct", 0)
    income = summary.get("total_income", 0)
    target_rate = 25.0
    if income > 0 and rate < target_rate:
        gap = (target_rate / 100 * income) - summary.get("net_savings", 0)
        extra = max(0, gap)
        insights.append(
            f"Your savings rate is {rate:.0f}% — increase by ₹{extra:,.0f}/month to reach 25%"
        )
    elif rate >= 40:
        insights.append(f"Strong savings rate at {rate:.0f}% — you're on track for Excellent status")
    else:
        insights.append(
            f"Net position this month: ₹{summary.get('net_savings', 0):,.0f} "
            f"({summary.get('savings_rate_pct', 0):.0f}% savings rate)"
        )

    while len(insights) < 3:
        anomalies = report.get("anomalies", [])
        if anomalies:
            insights.append(f"{len(anomalies)} spending alert(s) need your attention this month")
        else:
            insights.append("No major anomalies detected — spending patterns look typical")
        break

    return insights[:3]


def _rebalancing_tip(report: dict[str, Any]) -> str:
    cats = report.get("category_breakdown", [])
    spend_cats = [c for c in cats if c["category"] not in ("Income",)]
    if not spend_cats:
        return "Review discretionary categories to find quick savings opportunities."
    top = spend_cats[0]
    save = top["amount"] * 0.20
    return (
        f"If you reduce {top['category']} by 20%, you save an extra ₹{save:,.0f}/month"
    )


def build_report(df: pd.DataFrame, month_label: Optional[str] = None) -> dict[str, Any]:
    """
    Build full analytics report from a categorised transaction DataFrame.

    Returns dict `report` with spend_summary, category_breakdown, savings_score,
    anomalies, daily_spend_trend, ai_insights, rebalancing_recommendation, top_merchants.
    """
    if "category" not in df.columns:
        from categorise import categorise

        df = categorise(df)

    expenses = df[df["debit"] > 0].copy()
    income_rows = df[df["credit"] > 0].copy()

    total_income = float(income_rows["credit"].sum())
    total_expenses = float(expenses["debit"].sum())
    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0
    score, label, colour = _savings_score_and_label(savings_rate)

    # Category breakdown (exclude Income)
    spend_by_cat = (
        expenses[expenses["category"] != "Income"]
        .groupby("category")["debit"]
        .sum()
        .sort_values(ascending=False)
    )
    category_breakdown = []
    for cat, amt in spend_by_cat.items():
        pct = (amt / total_expenses * 100) if total_expenses else 0
        category_breakdown.append(
            {
                "category": cat,
                "amount": float(amt),
                "pct": round(float(pct), 1),
                "vs_last_month_pct": None,
            }
        )

    # Top merchants
    expenses = expenses.copy()
    expenses["merchant"] = expenses.apply(_extract_merchant, axis=1)
    top_merchants = (
        expenses.groupby("merchant")["debit"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
    )
    top_merchants_list = [
        {"merchant": m, "amount": float(a)} for m, a in top_merchants.items()
    ]

    # Subscriptions
    sub_flags = _detect_subscription_leaks(df)
    sub_total = sum(s["amount"] for s in sub_flags)
    subscription_summary = {"count": len(sub_flags), "monthly_total": sub_total}

    # Anomalies (dedupe by message)
    all_anomalies = (
        _detect_unusual_transactions(df)
        + _detect_duplicates(df)
        + _detect_weekend_spike(df)
        + sub_flags
    )
    seen_msg: set[str] = set()
    anomalies: list[dict[str, Any]] = []
    for a in all_anomalies:
        if a["message"] not in seen_msg:
            seen_msg.add(a["message"])
            anomalies.append(a)

    daily_trend = _daily_spend_trend(df)
    ai_insights = []  # filled after partial report

    if month_label is None and not df.empty and "date" in df.columns:
        try:
            d0 = pd.to_datetime(df["date"].iloc[0])
            month_label = d0.strftime("%B %Y")
        except Exception:
            month_label = "This month"

    report: dict[str, Any] = {
        "month_label": month_label or "This month",
        "spend_summary": {
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_savings": round(net_savings, 2),
            "savings_rate_pct": round(savings_rate, 1),
        },
        "category_breakdown": category_breakdown,
        "top_merchants": top_merchants_list,
        "savings_score": {
            "score": score,
            "label": label,
            "colour": colour,
            "savings_rate_pct": round(savings_rate, 1),
        },
        "anomalies": anomalies[:12],
        "daily_spend_trend": daily_trend,
        "subscription_summary": subscription_summary,
        "ai_insights": [],
        "rebalancing_recommendation": "",
    }
    report["ai_insights"] = _generate_insights(report)
    report["rebalancing_recommendation"] = _rebalancing_tip(report)
    return report


def run_pipeline(statement_path: str) -> dict[str, Any]:
    """parse → categorise → analytics."""
    from pathlib import Path

    from categorise import categorise
    from parse_statement import parse_statement

    path = Path(statement_path)
    df = parse_statement(path)
    df = categorise(df)
    return build_report(df)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    default = Path(__file__).resolve().parents[1] / "data" / "sample_statement.csv"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    report = run_pipeline(str(path))
    print(json.dumps(report, indent=2, default=str))
