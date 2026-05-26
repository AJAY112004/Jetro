from __future__ import annotations

from pathlib import Path

from flask import session


def store_report(report: dict, *, logger=None) -> str:
    from report_cache import json_safe, save_report

    safe = json_safe(report)
    report_id = save_report(safe)
    session["report_id"] = report_id
    if logger:
        logger.info("Stored report_id=%s", report_id)
    return report_id


def load_session_report() -> dict | None:
    from report_cache import load_report

    return load_report(session.get("report_id"))

