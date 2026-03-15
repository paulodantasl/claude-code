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
from .scrapers.property_appraiser import (
    HillsboroughPropertyScraper,
    PascoPropertyScraper,
    RawProperty,
)
from .storage import Permit, PropertyRecord, ScraperRun, get_session, init_db

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
        export_to_google: bool = False,
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

        summary: dict[str, Any] = {
            "counties_processed": 0,
            "total_permits_found": 0,
            "total_new": 0,
            "total_matched": 0,
            "alerts_sent": 0,
            "errors": [],
            "google_sheet_url": None,
        }

        all_matched_permits: list[Permit] = []

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
            all_matched_permits.extend(result.get("matched_permits", []))

        # ── Optional Google Drive export ──────────────────────────────────
        if export_to_google and all_matched_permits:
            try:
                from .notifications.google_drive import GoogleDriveExporter
                exporter = GoogleDriveExporter.from_env()
                sheet_rows = [self._permit_to_sheet_row(p) for p in all_matched_permits]
                url = exporter.export_matches(
                    matched_rows=sheet_rows,
                    sheet_title=(
                        f"Permit Intelligence — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
                    ),
                )
                summary["google_sheet_url"] = url
                logger.info("Google Sheet: %s", url)
            except Exception as exc:
                logger.error("Google Drive export failed: %s", exc)

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
        result: dict[str, Any] = {"found": 0, "new": 0, "matched": 0, "alerts": 0, "error": None, "matched_permits": []}

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
            result["matched_permits"] = matched_permits

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

    @staticmethod
    def _permit_to_sheet_row(p: Permit) -> dict:
        return {
            "filed_date":      p.filed_date.strftime("%Y-%m-%d") if p.filed_date else "",
            "permit_number":   p.permit_number or "",
            "county":          p.county_name or "",
            "city":            p.city or "",
            "address":         p.address or "",
            "zip_code":        p.zip_code or "",
            "permit_type":     p.permit_type or "",
            "status":          p.status or "",
            "applicant_name":  p.applicant_name or "",
            "owner_name":      p.owner_name or "",
            "contractor_name": p.contractor_name or "",
            "description":     p.description or "",
            "est_value":       f"${p.estimated_value:,.0f}" if p.estimated_value else "",
            "sqft":            f"{int(p.total_sqft):,}" if p.total_sqft else "",
            "parcel_number":   p.parcel_number or "",
            "matched_company": p.matched_company_name or "—",
            "match_score":     f"{p.match_score:.0f}%" if p.match_score else "—",
        }

    def run_property_appraisers(
        self,
        county_ids: list[str] | None = None,
        days_back: int = 90,
        cross_reference: bool = True,
    ) -> dict[str, Any]:
        """
        Scrape property appraiser data and optionally cross-reference
        recent land sales against the permit database.

        A parcel that (a) recently changed ownership AND (b) has a new
        large commercial permit is a very strong signal.

        Args:
            county_ids:       Limit to these county IDs (None = all supported).
            days_back:        How far back to look for recent sales.
            cross_reference:  If True, tag permits whose parcel had a recent sale.

        Returns:
            Summary dict.
        """
        summary = {"properties_found": 0, "cross_references": 0, "errors": []}

        # Hillsborough
        if county_ids is None or "hillsborough_county" in county_ids:
            try:
                scraper = HillsboroughPropertyScraper()
                props = scraper.scrape_recent_sales(days_back=days_back)
                self._persist_properties(props)
                summary["properties_found"] += len(props)
                if cross_reference:
                    summary["cross_references"] += self._cross_reference(props)
            except Exception as exc:
                logger.error("Hillsborough PA failed: %s", exc)
                summary["errors"].append({"county": "hillsborough_county", "error": str(exc)})

        # Pasco — owner-lookup only (no bulk API)
        if county_ids is None or "pasco_county" in county_ids:
            try:
                scraper = PascoPropertyScraper()
                # Look up known company aliases in the watch list
                aliases = [
                    alias
                    for company in self.watch_list
                    for alias in [company["display_name"]] + company.get("aliases", [])
                ]
                props = []
                for alias in aliases[:20]:   # limit to avoid hammering the site
                    props.extend(scraper.lookup_by_owner(alias))
                self._persist_properties(props)
                summary["properties_found"] += len(props)
                if cross_reference:
                    summary["cross_references"] += self._cross_reference(props)
            except Exception as exc:
                logger.error("Pasco PA failed: %s", exc)
                summary["errors"].append({"county": "pasco_county", "error": str(exc)})

        return summary

    def _persist_properties(self, props: list[RawProperty]) -> None:
        with get_session() as session:
            matcher = self.classifier.matcher
            for raw in props:
                existing = (
                    session.query(PropertyRecord)
                    .filter_by(parcel_number=raw.parcel_number, county_id=raw.county_id)
                    .first()
                )
                if existing:
                    continue

                match = matcher.match_value_str(raw.owner_name or "")
                db_prop = PropertyRecord(
                    county_id=raw.county_id,
                    parcel_number=raw.parcel_number,
                    owner_name=raw.owner_name,
                    mailing_address=raw.mailing_address,
                    site_address=raw.site_address,
                    city=raw.city,
                    zip_code=raw.zip_code,
                    land_use=raw.land_use,
                    assessed_value=raw.assessed_value,
                    land_area_sqft=raw.land_area_sqft,
                    building_area_sqft=raw.building_area_sqft,
                    last_sale_date=raw.last_sale_date,
                    last_sale_price=raw.last_sale_price,
                    matched_company_id=match.company_id if match else None,
                    matched_company_name=match.company_name if match else None,
                    match_score=match.score if match else None,
                )
                session.add(db_prop)

    def _cross_reference(self, props: list[RawProperty]) -> int:
        """
        Tag permits whose parcel_number matches a recently sold property.
        Returns count of permits updated.
        """
        updated = 0
        parcel_map = {p.parcel_number: p for p in props if p.parcel_number}
        if not parcel_map:
            return 0

        with get_session() as session:
            permits = (
                session.query(Permit)
                .filter(Permit.parcel_number.in_(list(parcel_map.keys())))
                .all()
            )
            for permit in permits:
                prop = parcel_map[permit.parcel_number]
                if prop.owner_name and not permit.owner_name:
                    permit.owner_name = prop.owner_name
                # If permit has no company match but property owner does, inherit it
                if not permit.matched_company_id and prop.owner_name:
                    from .agents.classifier import CompanyMatcher
                    m = self.classifier.matcher._match_value(prop.owner_name, "owner_name")
                    if m:
                        permit.matched_company_id = m.company_id
                        permit.matched_company_name = m.company_name
                        permit.match_score = m.score
                        updated += 1

        return updated

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        with open(path) as f:
            return yaml.safe_load(f)
