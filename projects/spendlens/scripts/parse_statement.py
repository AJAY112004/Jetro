"""
Parse Indian bank statements (PDF or CSV) into a normalised transaction DataFrame.

Supported CSV layouts: HDFC, SBI, ICICI, Axis, Kotak (header auto-detection).
PDF extraction uses pdfplumber table detection.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

# ---------------------------------------------------------------------------
# Column aliases per bank (normalised key -> possible header strings)
# ---------------------------------------------------------------------------
COLUMN_ALIASES: dict[str, list[str]] = {
    "date": [
        "date",
        "txn date",
        "transaction date",
        "tran date",
        "posting date",
        "value date",
        "value dt",
    ],
    "description": [
        "narration",
        "description",
        "particulars",
        "part transactions",
        "transaction remarks",
        "remarks",
    ],
    "debit": [
        "withdrawal amt.",
        "withdrawal amount",
        "withdrawal",
        "debit",
        "debit amount",
        "dr",
        "dr amount",
    ],
    "credit": [
        "deposit amt.",
        "deposit amount",
        "deposit",
        "credit",
        "credit amount",
        "cr",
        "cr amount",
    ],
    "balance": [
        "closing balance",
        "balance",
        "bal/inr",
        "available balance",
        "running balance",
    ],
    "transaction_id": [
        "chq./ref.no.",
        "chq/ref no",
        "ref no./cheque no.",
        "ref no",
        "cheque no",
        "reference no",
        "transaction id",
        "txn id",
    ],
    "amount": ["amount(inr)", "amount", "transaction amount"],
    "dr_cr": ["transaction type", "dr/cr", "type"],
}

BANK_HINTS: dict[str, list[str]] = {
    "hdfc": ["narration", "withdrawal amt.", "deposit amt.", "closing balance"],
    "sbi": ["txn date", "ref no./cheque no.", "debit", "credit"],
    "icici": ["transaction date", "amount(inr)", "transaction type"],
    "axis": ["part transactions", "bal/inr", "tran date"],
    "kotak": ["dr/cr", "transaction date"],
}

OUTPUT_COLUMNS = ["date", "description", "debit", "credit", "balance", "transaction_id"]

DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d %B %Y",
]

SKIP_ROW_PATTERNS = re.compile(
    r"^(opening balance|closing balance|statement period|account no|"
    r"customer id|branch|page \d|total\b|brought forward|carried forward)",
    re.I,
)


def _normalise_header(name: Any) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    text = str(name).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _map_columns(headers: list[str]) -> dict[str, int]:
    """Map normalised column keys to column indices."""
    normalised = [_normalise_header(h) for h in headers]
    mapping: dict[str, int] = {}

    for key, aliases in COLUMN_ALIASES.items():
        for idx, header in enumerate(normalised):
            if not header:
                continue
            for alias in aliases:
                if header == alias or alias in header:
                    if key not in mapping:
                        mapping[key] = idx
                    break

    return mapping


def _detect_bank(headers: list[str]) -> Optional[str]:
    joined = " ".join(_normalise_header(h) for h in headers)
    for bank, hints in BANK_HINTS.items():
        if sum(1 for h in hints if h in joined) >= 2:
            return bank
    return None


def _parse_amount(value: Any) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    text = str(value).strip()
    if not text or text in ("-", "—", "nan", "None"):
        return 0.0
    text = text.replace(",", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text or text == "-":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_dates(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    if parsed.notna().sum() >= len(series) * 0.5:
        return parsed.dt.date
    for fmt in DATE_FORMATS:
        try:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
            if parsed.notna().sum() >= len(series) * 0.5:
                return parsed.dt.date
        except (ValueError, TypeError):
            continue
    return pd.to_datetime(series, errors="coerce", dayfirst=True).dt.date


def _make_transaction_id(row: dict[str, Any], index: int | None = None) -> str:
    ref = row.get("transaction_id")
    if ref is not None and str(ref).strip() and str(ref).lower() != "nan":
        return str(ref).strip()
    # Keep transaction identity stable across duplicated CSV rows.
    payload = f"{row.get('date')}|{row.get('description')}|{row.get('debit')}|{row.get('credit')}"
    return hashlib.md5(payload.encode()).hexdigest()[:12]


def _rows_to_dataframe(rows: list[list[Any]], header_row_idx: int) -> pd.DataFrame:
    headers = [str(c) if c is not None else "" for c in rows[header_row_idx]]
    data_rows = rows[header_row_idx + 1 :]
    if not data_rows:
        return pd.DataFrame()
    max_cols = max(len(headers), max((len(r) for r in data_rows), default=0))
    headers = headers + [""] * (max_cols - len(headers))
    padded = []
    for row in data_rows:
        row = list(row) + [None] * (max_cols - len(row))
        padded.append(row[:max_cols])
    return pd.DataFrame(padded, columns=headers)


def _find_header_row(df_raw: pd.DataFrame) -> int:
    best_idx = 0
    best_score = -1
    for idx in range(min(30, len(df_raw))):
        row = [_normalise_header(c) for c in df_raw.iloc[idx].tolist()]
        score = _map_columns(row)
        quality = len(score)
        if "date" in score and ("description" in score or "debit" in score or "credit" in score):
            quality += 2
        if quality > best_score:
            best_score = quality
            best_idx = idx
    return best_idx


def _clean_raw_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    header_idx = _find_header_row(df)
    headers = df.iloc[header_idx].tolist()
    body = df.iloc[header_idx + 1 :].copy()
    body.columns = headers
    body = body.dropna(how="all")
    body = body[~body.apply(lambda r: r.astype(str).str.strip().eq("").all(), axis=1)]
    return body.reset_index(drop=True)


def _normalise_icici_axis_amount(df: pd.DataFrame, col_map: dict[str, int]) -> pd.DataFrame:
    """ICICI / Kotak: single amount + DR/CR type column."""
    if "amount" not in col_map or "dr_cr" not in col_map:
        return df
    amount_col = df.columns[col_map["amount"]]
    type_col = df.columns[col_map["dr_cr"]]
    debits, credits = [], []
    for _, row in df.iterrows():
        amt = _parse_amount(row[amount_col])
        typ = str(row[type_col]).strip().upper()
        if typ in ("DR", "DEBIT", "D", "WITHDRAWAL"):
            debits.append(amt)
            credits.append(0.0)
        elif typ in ("CR", "CREDIT", "C", "DEPOSIT"):
            debits.append(0.0)
            credits.append(amt)
        else:
            debits.append(amt if amt > 0 else 0.0)
            credits.append(0.0)
    df = df.copy()
    df["_debit"] = debits
    df["_credit"] = credits
    return df


def _body_to_standard(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    col_map = _map_columns(df.columns.tolist())
    bank = _detect_bank(df.columns.tolist())

    # DR/CR amount split (PhonePe + many exports use a single Amount column).
    # Only apply when we don't already have explicit debit/credit columns.
    if "amount" in col_map and "dr_cr" in col_map and "debit" not in col_map and "credit" not in col_map:
        df = _normalise_icici_axis_amount(df, col_map)

    records = []
    desc_col = df.columns[col_map["description"]] if "description" in col_map else None
    date_col = df.columns[col_map["date"]] if "date" in col_map else None
    debit_col = "_debit" if "_debit" in df.columns else (df.columns[col_map["debit"]] if "debit" in col_map else None)
    credit_col = "_credit" if "_credit" in df.columns else (df.columns[col_map["credit"]] if "credit" in col_map else None)
    balance_col = df.columns[col_map["balance"]] if "balance" in col_map else None
    ref_col = df.columns[col_map["transaction_id"]] if "transaction_id" in col_map else None

    for idx, row in df.iterrows():
        desc = str(row[desc_col]).strip() if desc_col is not None else ""
        if not desc or SKIP_ROW_PATTERNS.match(desc):
            continue
        if re.match(r"^[\s\-]+$", desc):
            continue

        debit = _parse_amount(row[debit_col]) if debit_col is not None else 0.0
        credit = _parse_amount(row[credit_col]) if credit_col is not None else 0.0
        balance = _parse_amount(row[balance_col]) if balance_col is not None else None
        date_val = row[date_col] if date_col is not None else None
        ref = row[ref_col] if ref_col is not None else None

        records.append(
            {
                "date": date_val,
                "description": desc,
                "debit": debit,
                "credit": credit,
                "balance": balance if balance_col is not None else None,
                "transaction_id": ref,
            }
        )

    if not records:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    out = pd.DataFrame(records)
    out["date"] = _parse_dates(out["date"].astype(str))
    out["debit"] = out["debit"].astype(float)
    out["credit"] = out["credit"].astype(float)
    if out["balance"].notna().any():
        out["balance"] = pd.to_numeric(out["balance"], errors="coerce")
    out["transaction_id"] = [_make_transaction_id(out.iloc[i].to_dict()) for i in range(len(out))]
    out = out.dropna(subset=["description"], how="all")
    out = out[~((out["debit"] == 0) & (out["credit"] == 0))]
    out = out.drop_duplicates(subset=["transaction_id"], keep="first")
    return out[OUTPUT_COLUMNS].reset_index(drop=True)


def parse_csv(path: Union[str, Path]) -> pd.DataFrame:
    path = Path(path)
    raw = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            # Read without assuming header — detect mid-file headers
            raw = pd.read_csv(path, header=None, dtype=str, encoding=encoding, on_bad_lines="skip")
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise ValueError(f"Could not read CSV: {path}")

    cleaned = _clean_raw_table(raw)
    return _body_to_standard(cleaned)


def _extract_pdf_tables(path: Path) -> list[list[list[Any]]]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber is required for PDF parsing. pip install pdfplumber") from exc

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
            else:
                # Fallback: text-based table extraction
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
    return all_tables


def _merge_pdf_tables(tables: list[list[list[Any]]]) -> pd.DataFrame:
    frames = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        df = _rows_to_dataframe(table, 0)
        if df.empty:
            continue
        # Re-scan for header inside table (merged cells / repeated headers)
        cleaned = _clean_raw_table(df)
        if not cleaned.empty:
            frames.append(cleaned)

    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    combined = pd.concat(frames, ignore_index=True)
    # Drop duplicate header rows that appear mid-statement
    desc_col = None
    col_map = _map_columns(combined.columns.tolist())
    if "description" in col_map:
        desc_col = combined.columns[col_map["description"]]

    if desc_col:
        mask = combined[desc_col].astype(str).apply(
            lambda x: _normalise_header(x) not in COLUMN_ALIASES["description"]
            and not SKIP_ROW_PATTERNS.match(str(x))
        )
        combined = combined[mask]

    return _body_to_standard(combined)


def parse_pdf(path: Union[str, Path]) -> pd.DataFrame:
    path = Path(path)
    tables = _extract_pdf_tables(path)
    if not tables:
        raise ValueError(f"No tables found in PDF: {path}")
    return _merge_pdf_tables(tables)


def parse_statement(path: Union[str, Path]) -> pd.DataFrame:
    """
    Parse a bank statement file (PDF or CSV) and return a normalised DataFrame.

    Columns: date, description, debit, credit, balance, transaction_id
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv(path)
    if suffix == ".pdf":
        return parse_pdf(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use .csv or .pdf")


if __name__ == "__main__":
    import sys

    default_csv = Path(__file__).resolve().parents[1] / "data" / "sample_statement.csv"
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_csv

    df = parse_statement(input_path)
    print(f"Parsed {len(df)} transactions from {input_path.name}\n")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 50)
    print(df.head(10).to_string(index=False))
