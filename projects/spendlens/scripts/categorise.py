"""
Categorise parsed bank transactions using keyword and regex rules.

Input: DataFrame from parse_statement.py (date, description, debit, credit, ...)
Output: same rows with category and sub_category columns; prints spend totals.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from parse_statement import parse_statement

# (category, sub_category, compiled regex) — order matters (first match wins)
RULES: list[Tuple[str, str, re.Pattern]] = [
  # Income
    ("Income", "Salary", re.compile(r"\b(salary|sal\s*cr|payroll|acme tech)\b", re.I)),
    ("Income", "Cashback", re.compile(r"\b(cashback|rewards?)\b", re.I)),
    ("Income", "Refund", re.compile(r"\b(refund|reversal)\b", re.I)),
    ("Income", "Credit", re.compile(r"\b(neft cr|imps cr|deposit amt)\b", re.I)),
    # EMI & Loans
    ("EMI & Loans", "Home Loan", re.compile(r"\b(home loan|housing loan|hl\s*emi)\b", re.I)),
    ("EMI & Loans", "Car Loan", re.compile(r"\b(car loan|auto loan|vehicle loan)\b", re.I)),
    ("EMI & Loans", "Personal Loan", re.compile(r"\b(personal loan|pl\s*emi)\b", re.I)),
    ("EMI & Loans", "EMI", re.compile(r"\b(emi|loan repayment|ach dr-emi)\b", re.I)),
    # Food & Dining
    ("Food & Dining", "Swiggy", re.compile(r"\bswiggy\b", re.I)),
    ("Food & Dining", "Zomato", re.compile(r"\bzomato\b", re.I)),
    ("Food & Dining", "Domino's", re.compile(r"\bdominos?\b", re.I)),
    ("Food & Dining", "Restaurant", re.compile(r"\b(restaurant|barbeque nation|bbq)\b", re.I)),
    # Groceries
    ("Groceries", "BigBasket", re.compile(r"\bbigbasket\b", re.I)),
    ("Groceries", "Blinkit", re.compile(r"\bblinkit\b", re.I)),
    ("Groceries", "Zepto", re.compile(r"\bzepto\b", re.I)),
    ("Groceries", "DMart", re.compile(r"\bdmart\b", re.I)),
    ("Groceries", "Supermarket", re.compile(r"\b(reliance fresh|supermart|supermarket|grocer)\b", re.I)),
    # Shopping
    ("Shopping", "Amazon", re.compile(r"\bamazon\b", re.I)),
    ("Shopping", "Flipkart", re.compile(r"\bflipkart\b", re.I)),
    ("Shopping", "Myntra", re.compile(r"\bmyntra\b", re.I)),
    ("Shopping", "Meesho", re.compile(r"\bmeesho\b", re.I)),
    # Transport
    ("Transport", "Ride Hailing", re.compile(r"\b(ola|uber|rapido)\b", re.I)),
    ("Transport", "Metro", re.compile(r"\b(dmrc|metro)\b", re.I)),
    ("Transport", "Fuel", re.compile(r"\b(hpcl|bpcl|iocl|petrol|diesel|fuel)\b", re.I)),
    ("Transport", "Travel", re.compile(r"\b(irctc|makemytrip|mmt|flight|train ticket)\b", re.I)),
    # Entertainment (before Shopping/Amazon — "Amazon Prime" is streaming)
    ("Entertainment", "Streaming", re.compile(r"\b(netflix|spotify|prime video|amazon prime|hotstar|sonyliv)\b", re.I)),
    ("Entertainment", "Events", re.compile(r"\b(bookmyshow|bms)\b", re.I)),
    ("Entertainment", "Fitness", re.compile(r"\b(cult\.?fit|cultfit)\b", re.I)),
    # Utilities
    ("Utilities", "Electricity", re.compile(r"\b(electricity|tata power|bescom|mseb)\b", re.I)),
    ("Utilities", "Water", re.compile(r"\b(water|jal board|djb)\b", re.I)),
    ("Utilities", "Gas", re.compile(r"\b(piped gas|igl|gas bill)\b", re.I)),
    ("Utilities", "Broadband", re.compile(r"\b(broadband|airtel|jio fiber|act fibernet)\b", re.I)),
    ("Utilities", "Mobile", re.compile(r"\b(jio|vi mobile|airtel|prepaid|recharge|phonepe recharge)\b", re.I)),
    # Health
    ("Health", "Pharmacy", re.compile(r"\b(medplus|1mg|pharmacy|apollo pharmacy)\b", re.I)),
    ("Health", "Hospital", re.compile(r"\b(hospital|apollo|max healthcare|fortis)\b", re.I)),
    # Transfers
    ("Transfers", "UPI P2P", re.compile(r"\b(upi-|imps dr-|neft dr-).{0,40}@(okaxis|okicici|paytm|ybl)\b", re.I)),
    ("Transfers", "UPI Transfer", re.compile(r"\b(upi-|imps dr-|neft dr-)[a-z\s]+@(ok|paytm|ybl|ibl)\b", re.I)),
    ("Transfers", "Rent", re.compile(r"\b(rent|landlord)\b", re.I)),
    ("Transfers", "NEFT/IMPS", re.compile(r"\b(neft dr|imps dr|fund transfer)\b", re.I)),
    # ATM
    ("Other", "ATM", re.compile(r"\batm\s*wdl\b", re.I)),
]

KNOWN_CONTACTS = re.compile(
    r"\b(rahul\.?sharma|priya\.?verma|mr\s*singh)\b", re.I
)


def categorise_row(description: str) -> Tuple[str, str]:
    text = str(description or "").strip()
    if not text:
        return "Other", "Uncategorised"

    for category, sub_category, pattern in RULES:
        if pattern.search(text):
            return category, sub_category

    if KNOWN_CONTACTS.search(text) and re.search(r"\b(upi|imps|neft)\b", text, re.I):
        return "Transfers", "Known Contact"

    return "Other", "Uncategorised"


def categorise(df: pd.DataFrame) -> pd.DataFrame:
    """Add category and sub_category columns to a parsed statement DataFrame."""
    if df.empty:
        out = df.copy()
        out["category"] = pd.Series(dtype=str)
        out["sub_category"] = pd.Series(dtype=str)
        return out

    out = df.copy()
    cats = out["description"].apply(categorise_row)
    out["category"] = [c[0] for c in cats]
    out["sub_category"] = [c[1] for c in cats]
    return out


def category_spend_totals(df: pd.DataFrame) -> pd.Series:
    """Sum debit amounts by category (excludes income credits)."""
    if "category" not in df.columns:
        df = categorise(df)
    spend = df[df["debit"] > 0].groupby("category")["debit"].sum().sort_values(ascending=False)
    return spend


def print_category_totals(df: pd.DataFrame) -> None:
    totals = category_spend_totals(df)
    income = df[df["credit"] > 0]["credit"].sum()
    total_spend = df[df["debit"] > 0]["debit"].sum()

    print("\n--- Category-wise spend totals (debits) ---")
    for cat, amount in totals.items():
        pct = (amount / total_spend * 100) if total_spend else 0
        print(f"  {cat:20s}  ₹{amount:>12,.2f}  ({pct:5.1f}%)")
    print(f"\n  {'Total spend':20s}  ₹{total_spend:>12,.2f}")
    print(f"  {'Total income':20s}  ₹{income:>12,.2f}")
    print(f"  {'Net (income - spend)':20s}  ₹{income - total_spend:>12,.2f}")


if __name__ == "__main__":
    default_csv = Path(__file__).resolve().parents[1] / "data" / "sample_statement.csv"
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_csv

    parsed = parse_statement(input_path)
    labelled = categorise(parsed)

    print(f"Categorised {len(labelled)} transactions from {input_path.name}\n")
    print_category_totals(labelled)

    print("\n--- Sample rows with categories ---")
    cols = ["date", "description", "debit", "credit", "category", "sub_category"]
    pd.set_option("display.max_colwidth", 40)
    print(labelled[cols].head(10).to_string(index=False))
