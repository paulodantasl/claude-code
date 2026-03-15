"""
Main orchestration pipeline.

Coordinates:
  1. Load county/company configs
  2. Select and run the right scraper for each county
  3. Fall back to AI agent for complex portals
  4. Run classifier to match companies
  5. Persist new records to the database
  6. Send alerts for new matches
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.exc import IntegrityError

from .agents.classifier import CompanyMatcher, PermitClassifier
from .agents.permit_agent import PermitAgent
from .notifications.alerts import AlertManager
from .scrapers import get_scraper
from .scrapers.base import RawPermit
from .storage import Permit, ScraperRun, get_session, init_db

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent / "targets"


class PermitPipeline:
    """End-to-end pipeline: scrape → classify → store → alert."""

    def __init__(
        self,
        db_url: str | None = None,
        config_dir: Path | None = None,
        alert_config: dict[str, Any] | None = None,
    ):
        self.config_dir = config_dir or CONFIG_DIR
        self.alert_manager = AlertManager(alert_config or {})
        init_db(db_url)

        # Load configs
        self.counties: list[dict] = self._load_yaml("counties.yaml").get("targets", [])
        watch_data = self._load_yaml("companies.yaml")
        self.watch_list: list[dict] = watch_data.get("watch_list", [])

        # Build classifier
        matcher = CompanyMatcher(self.watch_list)
        self.classifier = PermitClassifier(matcher)

        # AI agent (lazy init — only when needed)
        self._agent: PermitAgent | None = None

    def run(
        self,
        county_ids: list[str] | None = None,
        days_back: int = 7,
        permit_types: list[str] | None = None,
        use_ai_agent: bool = False,
        min_match_score: float = 85.0,
    ) -> dict[str, Any]:
        """
        Run the pipeline for selected counties.

        Args:
            county_ids:      Limit to these county IDs (None = all).
            days_back:       Look back N calendar days.
            permit_types:    Permit type keywords to filter on.
            use_ai_agent:    Force AI agent even for supported portals.
            min_match_score: Minimum fuzzy score to record a company match.

        Returns:
            Summary dict with counts.
        """
        targets = [
            c for c in self.counties
            if county_ids is None or c["id"] in county_ids
        ]

        summary = {
            "counties_processed": 0,
            "total_permits_found": 0,
            "total_new": 0,
            "total_matched": 0,
            "alerts_sent": 0,
            "errors": [],
        }

        for county in targets:
            logger.info("━━ Processing %s ━━", county["name"])
            result = self._process_county(
                county, days_back, permit_types, use_ai_agent, min_match_score
            )
            summary["counties_processed"] += 1
            summary["total_permits_found"] += result["found"]
            summary["total_new"] += result["new"]
            summary["total_matched"] += result["matched"]
            summary["alerts_sent"] += result["alerts"]
            if result.get("error"):
                summary["errors"].append({"county": county["id"], "error": result["error"]})

        return summary

    def _process_county(
        self,
        county: dict,
        days_back: int,
        permit_types: list[str] | None,
        use_ai_agent: bool,
        min_match_score: float,
    ) -> dict[str, Any]:
        run_record = ScraperRun(
            county_id=county["id"],
            scraper_type="ai_agent" if use_ai_agent else county.get("type", "accela"),
        )
        result = {"found": 0, "new": 0, "matched": 0, "alerts": 0, "error": None}

        try:
            # ── Scrape ────────────────────────────────────────────────────
            want_ai = use_ai_agent or county.get("use_ai_agent")
            has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

            if want_ai and not has_api_key:
                logger.warning(
                    "%s: use_ai_agent=true but ANTHROPIC_API_KEY not set — "
                    "falling back to rule-based scraper",
                    county["name"],
                )
                want_ai = False

            if want_ai:
                raw_permits = self._run_ai_agent(county, days_back, permit_types)
            else:
                scraper = get_scraper(county)
                raw_permits = scraper.scrape(days_back=days_back, permit_types=permit_types)

            run_record.records_found = len(raw_permits)
            result["found"] = len(raw_permits)

            # ── Classify + persist ────────────────────────────────────────
            new_permits: list[Permit] = []
            matched_permits: list[Permit] = []

            with get_session() as session:
                for raw in raw_permits:
                    enrichment = self.classifier.classify(raw)

                    if enrichment.get("skip"):
                        continue

                    db_permit = self._to_db_permit(raw, enrichment)

                    # Upsert (skip duplicates)
                    existing = (
                        session.query(Permit)
                        .filter_by(source_id=raw.source_id, county_id=raw.county_id)
                        .first()
                    )
                    if existing:
                        continue

                    session.add(db_permit)
                    new_permits.append(db_permit)

                    if db_permit.match_score and db_permit.match_score >= min_match_score:
                        matched_permits.append(db_permit)

                run_record.records_new = len(new_permits)
                run_record.records_matched = len(matched_permits)
                run_record.status = "success"
                run_record.finished_at = datetime.utcnow()
                session.add(run_record)

            result["new"] = len(new_permits)
            result["matched"] = len(matched_permits)

            # ── Alerts ────────────────────────────────────────────────────
            for permit in matched_permits:
                try:
                    self.alert_manager.send(permit)
                    result["alerts"] += 1
                    # Mark alert sent
                    with get_session() as session:
                        p = session.get(Permit, permit.id)
                        if p:
                            p.alert_sent = True
                except Exception as exc:
                    logger.error("Alert failed for %s: %s", permit.permit_number, exc)

            logger.info(
                "%s → found=%d  new=%d  matched=%d",
                county["name"], result["found"], result["new"], result["matched"],
            )

        except Exception as exc:
            logger.error("County %s failed: %s", county["id"], exc, exc_info=True)
            result["error"] = str(exc)
            run_record.status = "error"
            run_record.error_message = str(exc)
            run_record.finished_at = datetime.utcnow()
            with get_session() as session:
                session.add(run_record)

        return result

    def _run_ai_agent(
        self, county: dict, days_back: int, permit_types: list[str] | None
    ) -> list[RawPermit]:
        if self._agent is None:
            self._agent = PermitAgent()
        return self._agent.run(county, days_back=days_back, permit_types=permit_types)

    @staticmethod
    def _to_db_permit(raw: RawPermit, enrichment: dict) -> Permit:
        return Permit(
            source_id=raw.source_id,
            county_id=raw.county_id,
            county_name=raw.county_name,
            permit_number=raw.permit_number,
            permit_type=raw.permit_type,
            permit_subtype=raw.permit_subtype,
            status=raw.status,
            description=raw.description,
            applicant_name=raw.applicant_name,
            owner_name=raw.owner_name,
            contractor_name=raw.contractor_name,
            address=raw.address,
            city=raw.city,
            state=raw.state,
            zip_code=raw.zip_code,
            parcel_number=raw.parcel_number,
            latitude=raw.latitude,
            longitude=raw.longitude,
            estimated_value=raw.estimated_value,
            total_sqft=raw.total_sqft,
            filed_date=raw.filed_date,
            issued_date=raw.issued_date,
            source_url=raw.source_url,
            raw_data=json.dumps(raw.raw_data) if raw.raw_data else None,
            matched_company_id=enrichment.get("matched_company_id"),
            matched_company_name=enrichment.get("matched_company_name"),
            match_score=enrichment.get("match_score"),
        )

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        with open(path) as f:
            return yaml.safe_load(f)
