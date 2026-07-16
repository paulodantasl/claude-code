"""
Lead output: a dated CSV call-list and an optional Google Sheet.

The CSV is the primary deliverable — one row per new issued-permit lead, columns
ordered for a sales team to work top-to-bottom (issue date, project, GC contact,
owner contact). Google Sheets export reuses the package's existing
``GoogleDriveExporter`` and is best-effort (only runs if Drive creds are set).
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

from .models import LEAD_FIELDS, Lead

logger = logging.getLogger(__name__)


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    if isinstance(value, float):
        # Whole dollars / sqft read better without trailing .0
        return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"
    return str(value)


def write_csv(leads: list[Lead], path: str | Path, append: bool = True) -> Path:
    """Write (or append) leads to a CSV call-list. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not (append and path.exists())
    mode = "a" if append else "w"
    with open(path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for lead in leads:
            writer.writerow({k: _fmt(v) for k, v in lead.to_dict().items()})
    logger.info("Wrote %d lead(s) to %s", len(leads), path)
    return path


def to_sheet_rows(leads: list[Lead]) -> list[dict]:
    """Display rows for Google Sheets (string-formatted)."""
    rows = []
    for lead in leads:
        d = lead.to_dict()
        row = {k: _fmt(v) for k, v in d.items()}
        if lead.estimated_value:
            row["estimated_value"] = f"${lead.estimated_value:,.0f}"
        rows.append(row)
    return rows


def export_google_sheet(leads: list[Lead], sheet_title: str | None = None) -> str | None:
    """Best-effort push to Google Sheets. Returns the sheet URL, or None."""
    if not leads:
        return None
    if not (os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
            or os.environ.get("GOOGLE_OAUTH_CLIENT_FILE")):
        logger.info("Google Drive creds not set — skipping Sheet export")
        return None
    try:
        from ..notifications.google_drive import GoogleDriveExporter

        exporter = GoogleDriveExporter.from_env()
        return exporter.export_matches(
            matched_rows=to_sheet_rows(leads),
            sheet_title=sheet_title or "Issued-Permit Leads",
        )
    except Exception as exc:
        logger.error("Google Sheet export failed: %s", exc)
        return None
