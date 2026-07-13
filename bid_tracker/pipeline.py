"""
Main orchestration pipeline.

Coordinates the weekly run:
  1. Load source + criteria + company configs.
  2. Pull recent opportunities from each configured source.
  3. Qualify each against the company's bid/no-bid criteria.
  4. Persist new records to the database.
  5. Build a bid package folder (summary, requirements, submittal checklist,
     downloaded documents, first-draft proposal) for each qualified opportunity.
  6. Alert the team about new qualified bids.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .agents.qualifier import QualificationResult, Qualifier
from .notifications.alerts import AlertManager
from .packager import BidPackager
from .sources import get_source
from .sources.base import RawDocument, RawOpportunity
from .storage import Opportunity, SourceRun, get_session, init_db

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent / "targets"
COMPANY_DIR = Path(__file__).parent / "company"


class BidPipeline:
    """End-to-end pipeline: fetch → qualify → store → package → alert."""

    def __init__(
        self,
        db_url: str | None = None,
        config_dir: Path | None = None,
        company_file: Path | None = None,
        output_dir: Path | None = None,
        alert_config: dict[str, Any] | None = None,
        model: str = "claude-sonnet-4-6",
    ):
        self.config_dir = config_dir or CONFIG_DIR
        self.output_dir = Path(output_dir or os.environ.get("BID_OUTPUT_DIR", "bid_packages"))
        self.model = model
        self.alert_manager = AlertManager(alert_config or {})
        init_db(db_url)

        self.sources: list[dict] = self._load_yaml("sources.yaml").get("sources", [])
        self.criteria: dict = self._load_yaml("criteria.yaml").get("criteria", {})
        self.company: dict = self._load_company(company_file)

        self.qualifier = Qualifier(self.criteria)
        self.packager = BidPackager(
            output_dir=self.output_dir,
            company=self.company,
            download_documents=self.criteria.get("download_documents", True),
            model=self.model,
        )

    def run(
        self,
        source_ids: list[str] | None = None,
        days_back: int = 7,
        build_packages: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Run the weekly pipeline.

        Args:
            source_ids:     Limit to these source IDs (None = all configured).
            days_back:      Look back N calendar days (default 7 = weekly).
            build_packages: Build the bid package folder for qualified opps.
            dry_run:        Qualify and report without writing packages or alerts.

        Returns:
            Summary dict with counts.
        """
        targets = [
            s for s in self.sources
            if source_ids is None or s["id"] in source_ids
        ]
        keywords = self.criteria.get("keywords_include") or None

        summary: dict[str, Any] = {
            "sources_processed": 0,
            "total_found": 0,
            "total_new": 0,
            "total_qualified": 0,
            "packages_built": 0,
            "alerts_sent": 0,
            "errors": [],
            "qualified": [],
        }

        for source_cfg in targets:
            logger.info("━━ Source: %s ━━", source_cfg["name"])
            result = self._process_source(
                source_cfg, days_back, keywords, build_packages, dry_run
            )
            summary["sources_processed"] += 1
            summary["total_found"] += result["found"]
            summary["total_new"] += result["new"]
            summary["total_qualified"] += result["qualified"]
            summary["packages_built"] += result["packages"]
            summary["alerts_sent"] += result["alerts"]
            summary["qualified"].extend(result["qualified_titles"])
            if result.get("error"):
                summary["errors"].append({"source": source_cfg["id"], "error": result["error"]})

        return summary

    def _process_source(
        self,
        source_cfg: dict,
        days_back: int,
        keywords: list[str] | None,
        build_packages: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        run_record = SourceRun(source=source_cfg["id"])
        result: dict[str, Any] = {
            "found": 0, "new": 0, "qualified": 0, "packages": 0, "alerts": 0,
            "error": None, "qualified_titles": [],
        }

        try:
            cfg = self._inject_secrets(source_cfg)
            source = get_source(cfg)
            raw_opps = source.fetch(days_back=days_back, keywords=keywords)
            run_record.records_found = len(raw_opps)
            result["found"] = len(raw_opps)

            for raw in raw_opps:
                qual = self.qualifier.qualify(raw)

                with get_session() as session:
                    existing = (
                        session.query(Opportunity)
                        .filter_by(source_id=raw.source_id, source=raw.source)
                        .first()
                    )
                    if existing:
                        continue

                    db_opp = self._to_db_opportunity(raw, qual)
                    session.add(db_opp)
                    result["new"] += 1

                    if not qual.qualified:
                        db_opp.status = "skipped"
                        continue

                    result["qualified"] += 1
                    result["qualified_titles"].append(raw.title or raw.source_id)
                    db_opp.status = "qualified"

                    if dry_run:
                        continue

                    # Build the package folder.
                    if build_packages:
                        try:
                            folder = self.packager.build(raw, qual)
                            db_opp.package_path = str(folder)
                            db_opp.proposal_drafted = True
                            db_opp.status = "packaged"
                            result["packages"] += 1
                        except Exception as exc:
                            logger.error("Package build failed for %s: %s", raw.source_id, exc)

                    # Alert.
                    try:
                        self.alert_manager.send(db_opp)
                        db_opp.alert_sent = True
                        result["alerts"] += 1
                    except Exception as exc:
                        logger.error("Alert failed for %s: %s", raw.source_id, exc)

            run_record.records_new = result["new"]
            run_record.records_qualified = result["qualified"]
            run_record.packages_built = result["packages"]
            run_record.status = "success"
            run_record.finished_at = datetime.utcnow()
            with get_session() as session:
                session.add(run_record)

            logger.info(
                "%s → found=%d new=%d qualified=%d packages=%d",
                source_cfg["name"], result["found"], result["new"],
                result["qualified"], result["packages"],
            )

        except Exception as exc:
            logger.error("Source %s failed: %s", source_cfg["id"], exc, exc_info=True)
            result["error"] = str(exc)
            run_record.status = "error"
            run_record.error_message = str(exc)
            run_record.finished_at = datetime.utcnow()
            with get_session() as session:
                session.add(run_record)

        return result

    # ── helpers ───────────────────────────────────────────────────────────

    def _inject_secrets(self, source_cfg: dict) -> dict:
        """Merge env-based secrets/criteria into a source config copy."""
        cfg = dict(source_cfg)
        if cfg.get("type") == "sam_gov":
            cfg.setdefault("api_key", os.environ.get("SAM_GOV_API_KEY"))
            cfg.setdefault("naics_codes", self.criteria.get("naics_codes", []))
            cfg.setdefault("states", self.criteria.get("states", []))
        if cfg.get("type") == "opengov":
            cfg.setdefault("api_key", os.environ.get("OPENGOV_API_KEY"))
            cfg.setdefault("email", os.environ.get("OPENGOV_EMAIL"))
        return cfg

    @staticmethod
    def _to_db_opportunity(raw: RawOpportunity, qual: QualificationResult) -> Opportunity:
        return Opportunity(
            source_id=raw.source_id,
            source=raw.source,
            source_name=raw.source_name,
            solicitation_number=raw.solicitation_number,
            title=raw.title,
            agency=raw.agency,
            opportunity_type=raw.opportunity_type,
            description=raw.description,
            naics_code=raw.naics_code,
            psc_code=raw.psc_code,
            set_aside=raw.set_aside,
            state=raw.state,
            city=raw.city,
            zip_code=raw.zip_code,
            estimated_value=raw.estimated_value,
            posted_date=raw.posted_date,
            question_due_date=raw.question_due_date,
            due_date=raw.due_date,
            contact_name=raw.contact_name,
            contact_email=raw.contact_email,
            contact_phone=raw.contact_phone,
            qualified=qual.qualified,
            qual_score=qual.score,
            qual_reasons=json.dumps(qual.reasons),
            disqualifiers=json.dumps(qual.disqualifiers),
            source_url=raw.source_url,
            documents=json.dumps([{"name": d.name, "url": d.url} for d in raw.documents]),
            raw_data=json.dumps(raw.raw_data, default=str) if raw.raw_data else None,
        )

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        if not path.exists():
            logger.warning("Config %s not found — using empty config", path)
            return {}
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def _load_company(self, company_file: Path | None) -> dict:
        path = company_file or (COMPANY_DIR / "profile.yaml")
        if not Path(path).exists():
            logger.warning("Company profile %s not found — proposals will use placeholders", path)
            return {}
        with open(path) as f:
            return yaml.safe_load(f) or {}
