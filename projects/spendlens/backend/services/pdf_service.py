from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO


def build_pdf_bytes(report: dict) -> bytes:
    import io

    from pdf_report import build_styled_pdf

    buffer = io.BytesIO()
    build_styled_pdf(report, buffer)
    buffer.seek(0)
    return buffer.getvalue()

