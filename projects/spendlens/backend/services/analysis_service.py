from __future__ import annotations

from pathlib import Path


def analyse_file(path: Path, *, sample_csv: Path, fallback_report: Path, logger) -> dict:
    """
    Analyse uploaded statement and return the normalized dashboard `report` dict.
    """
    import json

    # Imports here so sys.path setup in app_factory can control where modules load from.
    from stdlib_pipeline import run_pipeline as stdlib_pipeline
    from report_cache import json_safe

    ext = path.suffix.lower()
    logger.info("Analysing %s (%s bytes)", path.name, path.stat().st_size)

    if ext in (".csv", ".pdf"):
        try:
            report = stdlib_pipeline(path)
            logger.info(
                "stdlib CSV pipeline OK: %d categories",
                len(report.get("category_breakdown", [])),
            )
            return json_safe(report)
        except Exception as exc:
            logger.exception("stdlib CSV pipeline failed")
            if path.name in ("sample_statement.csv", "sample_bank_transactions.csv"):
                if fallback_report.is_file():
                    logger.warning("Using static report.json fallback")
                    return json_safe(json.loads(fallback_report.read_text(encoding="utf-8")))
            # Fallback: attempt pandas pipeline if parsing failed.
            raise ValueError(f"CSV parse failed: {exc}") from exc

    raise ValueError(f"Unsupported file type: {ext}")


def analyse_demo(sample_csv: Path, *, fallback_report: Path, logger) -> dict:
    try:
        return analyse_file(
            sample_csv,
            sample_csv=sample_csv,
            fallback_report=fallback_report,
            logger=logger,
        )
    except Exception as exc:
        logger.warning("Demo fallback: %s", exc)
        if fallback_report.is_file():
            import json

            return json.loads(fallback_report.read_text(encoding="utf-8"))
        return {}

