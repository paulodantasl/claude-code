"""
LeadPipeline — scan portals for newly ISSUED permits and emit sales leads.

For each configured county:
  1. Scrape recent permits (lazy per-portal scraper, or an injected factory).
  2. Keep only issued permits that match your scope (commercial + residential
     projects; trade/low-value noise filtered out).
  3. Drop any already surfaced (dedupe store) so you only see NEW leads.
  4. Build a Lead (GC of record + owner as contacts) and append to the CSV
     call-list (and optionally a Google Sheet).

Runs as a scheduled job (cron / systemd / the CLI ``--interval`` loop). The
dedupe store guarantees each permit becomes a lead exactly once.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import yaml

from .classifier import LeadClassifier
from .exporters import export_google_sheet, write_csv
from .models import Lead, LeadConfig, utcnow_iso
from .store import LeadStore

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "targets"


def load_lead_config(
    config_dir: Path | None = None,
    leads_file: str = "leads.yaml",
    counties_file: str = "counties.yaml",
) -> tuple[LeadConfig, list[dict]]:
    """Load the lead scope config and the county/portal list."""
    cdir = config_dir or CONFIG_DIR

    lead_cfg = LeadConfig()
    leads_path = cdir / leads_file
    if leads_path.exists():
        raw = yaml.safe_load(leads_path.read_text(encoding="utf-8")) or {}
        lead_cfg = LeadConfig.from_dict(raw.get("leads", raw))

    counties: list[dict] = []
    counties_path = cdir / counties_file
    if counties_path.exists():
        data = yaml.safe_load(counties_path.read_text(encoding="utf-8")) or {}
        counties = data.get("targets", [])

    return lead_cfg, counties


class LeadPipeline:
    """Scrape → filter issued+scope → dedupe → build leads → export."""

    def __init__(
        self,
        config: LeadConfig | None = None,
        store: LeadStore | None = None,
        counties: list[dict] | None = None,
        scraper_factory: Callable[[dict], Any] | None = None,
    ):
        self.config = config or LeadConfig()
        self.classifier = LeadClassifier(self.config)
        self.store = store or LeadStore()
        self.counties = counties if counties is not None else []
        self._scraper_factory = scraper_factory

    def _get_scraper(self, county_cfg: dict):
        if self._scraper_factory:
            return self._scraper_factory(county_cfg)
        from ..scrapers import get_scraper  # lazy: keeps Playwright out of import

        return get_scraper(county_cfg)

    def run(
        self,
        county_ids: list[str] | None = None,
        days_back: int = 30,
        csv_path: str | Path = "permit_leads.csv",
        google_sheet: bool = False,
        permit_types: list[str] | None = None,
    ) -> dict[str, Any]:
        self.store.load()
        targets = [
            c for c in self.counties
            if county_ids is None or c.get("id") in county_ids
        ]

        summary: dict[str, Any] = {
            "counties_processed": 0,
            "permits_scanned": 0,
            "qualified": 0,
            "new_leads": 0,
            "duplicates": 0,
            "errors": [],
            "csv_path": None,
            "google_sheet_url": None,
            "new_lead_rows": [],
        }
        new_leads: list[Lead] = []

        for county in targets:
            try:
                scraper = self._get_scraper(county)
                raws = scraper.scrape(days_back=days_back, permit_types=permit_types)
            except Exception as exc:
                logger.error("Lead scan failed for %s: %s", county.get("id"), exc)
                summary["errors"].append({"county": county.get("id"), "error": str(exc)})
                continue

            summary["counties_processed"] += 1
            for raw in raws:
                summary["permits_scanned"] += 1
                ok, reason = self.classifier.qualifies(raw)
                if not ok:
                    logger.debug("skip %s: %s", raw.permit_number, reason)
                    continue
                summary["qualified"] += 1

                lead = self.classifier.build_lead(raw)
                if not self.store.is_new(lead.lead_id):
                    summary["duplicates"] += 1
                    continue
                self.store.add(lead)
                new_leads.append(lead)

        summary["new_leads"] = len(new_leads)
        summary["new_lead_rows"] = [lead.to_dict() for lead in new_leads]

        if new_leads:
            path = write_csv(new_leads, csv_path, append=True)
            summary["csv_path"] = str(path)
            if google_sheet:
                summary["google_sheet_url"] = export_google_sheet(
                    new_leads,
                    sheet_title=f"Issued-Permit Leads — {utcnow_iso()[:10]}",
                )

        self.store.save()
        return summary


def build_pipeline(
    config_dir: str | Path | None = None,
    state_file: str | Path = "permit_leads_state.json",
) -> LeadPipeline:
    """Factory: load leads.yaml + counties.yaml + .env and wire the pipeline."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    cfg, counties = load_lead_config(Path(config_dir) if config_dir else None)
    return LeadPipeline(config=cfg, store=LeadStore(state_file), counties=counties)
