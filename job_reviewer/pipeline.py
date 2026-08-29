"""
End-to-end pipeline: scrape → score → store → tailor → flag for review.

    profile/  ─┐
               ├─► JobReviewPipeline.run()
    agencies ──┘        │
                        ├─ scrape each agency (governmentjobs.com)
                        ├─ enrich detail pages for keyword-passing jobs
                        ├─ score fit (lexical gate → Claude semantic)
                        ├─ persist new jobs
                        ├─ for jobs ≥ flag threshold: tailor a packet + alert
                        └─ everything lands in the review queue (never submitted)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .matching import JobMatcher
from .notifications import AlertManager
from .profile_loader import ProfileLoader
from .scrapers import RawJob, get_scraper
from .scrapers.governmentjobs import GovernmentJobsScraper
from .storage import Job, ScraperRun, get_session, init_db
from .tailor import ApplicationTailor

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).parent
CONFIG_DIR = PACKAGE_DIR / "targets"
PROFILE_DIR = PACKAGE_DIR / "profile"
PACKETS_DIR = PACKAGE_DIR / "packets"


class JobReviewPipeline:
    def __init__(
        self,
        db_url: str | None = None,
        config_dir: Path | None = None,
        profile_dir: Path | None = None,
        packets_dir: Path | None = None,
        use_ai: bool = True,
        alert_config: dict[str, Any] | None = None,
    ):
        self.config_dir = config_dir or CONFIG_DIR
        self.profile_dir = profile_dir or PROFILE_DIR
        self.packets_dir = packets_dir or PACKETS_DIR
        init_db(db_url)

        self.agencies: list[dict] = self._load_yaml("agencies.yaml").get("agencies", [])
        self.profile = ProfileLoader(self.profile_dir).load()
        self.matcher = JobMatcher(self.profile, use_ai=use_ai)
        self.tailor = ApplicationTailor(self.profile)
        self.alerts = AlertManager(alert_config or {})

    # ── Public API ──────────────────────────────────────────────────────────

    def run(
        self,
        agency_ids: list[str] | None = None,
        counties: list[str] | None = None,
        keywords: list[str] | None = None,
        flag_threshold: float = 60.0,
        max_jobs_per_agency: int | None = None,
        make_packets: bool = True,
    ) -> dict[str, Any]:
        keywords = keywords or self.profile.keywords or None
        targets = [
            a
            for a in self.agencies
            if (agency_ids is None or a["id"] in agency_ids)
            and (counties is None or a.get("county") in counties)
        ]

        summary = {
            "agencies_processed": 0,
            "jobs_found": 0,
            "jobs_new": 0,
            "jobs_flagged": 0,
            "packets_written": 0,
            "errors": [],
        }

        for agency in targets:
            logger.info("━━ %s ━━", agency["name"])
            try:
                result = self._process_agency(
                    agency, keywords, flag_threshold, max_jobs_per_agency, make_packets
                )
                summary["agencies_processed"] += 1
                summary["jobs_found"] += result["found"]
                summary["jobs_new"] += result["new"]
                summary["jobs_flagged"] += result["flagged"]
                summary["packets_written"] += result["packets"]
            except Exception as exc:
                logger.error("Agency %s failed: %s", agency["id"], exc, exc_info=True)
                summary["errors"].append({"agency": agency["id"], "error": str(exc)})

        return summary

    # ── Per-agency ──────────────────────────────────────────────────────────

    def _process_agency(
        self,
        agency: dict,
        keywords: list[str] | None,
        flag_threshold: float,
        max_jobs: int | None,
        make_packets: bool,
    ) -> dict[str, Any]:
        run = ScraperRun(agency_id=agency["id"])
        result = {"found": 0, "new": 0, "flagged": 0, "packets": 0}

        scraper = get_scraper(agency)
        raw_jobs = scraper.scrape(keywords=keywords, max_jobs=max_jobs)
        run.jobs_found = result["found"] = len(raw_jobs)

        flagged_jobs: list[Job] = []
        with get_session() as session:
            for raw in raw_jobs:
                if session.query(Job).filter_by(source_id=raw.source_id).first():
                    continue  # already seen

                # Enrich detail page (only for jobs that passed the keyword gate).
                if isinstance(scraper, GovernmentJobsScraper):
                    raw = scraper.enrich_detail(raw)

                fit = self.matcher.score(raw)
                job = self._to_db_job(raw, fit)
                if fit.score >= flag_threshold:
                    job.flagged = True
                    job.review_status = "flagged"
                    flagged_jobs.append(job)
                session.add(job)
                result["new"] += 1

            run.jobs_new = result["new"]
            run.jobs_flagged = len(flagged_jobs)
            run.status = "success"
            run.finished_at = datetime.utcnow()
            session.add(run)

        result["flagged"] = len(flagged_jobs)

        # Tailor packets + alert for flagged jobs (outside the write txn above
        # so a slow API call doesn't hold the DB session open).
        for job in flagged_jobs:
            if make_packets and self.tailor.available:
                try:
                    packet = self.tailor.tailor(self._job_to_rawjob(job), self._fit_from_job(job))
                    path = self.tailor.write_packet(packet, self.packets_dir)
                    with get_session() as session:
                        db = session.get(Job, job.id)
                        if db:
                            db.packet_path = str(path)
                            db.review_status = "flagged"
                    job.packet_path = str(path)
                    result["packets"] += 1
                except Exception as exc:
                    logger.warning("Tailoring failed for '%s': %s", job.title, exc)
            try:
                self.alerts.send(job)
                with get_session() as session:
                    db = session.get(Job, job.id)
                    if db:
                        db.alert_sent = True
            except Exception as exc:
                logger.error("Alert failed for '%s': %s", job.title, exc)

        logger.info(
            "%s → found=%d new=%d flagged=%d packets=%d",
            agency["name"], result["found"], result["new"],
            result["flagged"], result["packets"],
        )
        return result

    # ── Mapping helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _to_db_job(raw: RawJob, fit) -> Job:
        return Job(
            source_id=raw.source_id,
            agency_id=raw.agency_id,
            agency_name=raw.agency_name,
            county=raw.county,
            title=raw.title,
            department=raw.department,
            category=raw.category,
            job_type=raw.job_type,
            location=raw.location,
            salary_min=raw.salary_min,
            salary_max=raw.salary_max,
            salary_raw=raw.salary_raw,
            description=raw.description,
            requirements=raw.requirements,
            posted_date=raw.posted_date,
            closing_date=raw.closing_date,
            job_id_external=raw.job_id_external,
            apply_url=raw.apply_url,
            source_url=raw.source_url,
            fit_score=fit.score,
            lexical_score=fit.lexical_score,
            semantic_score=fit.semantic_score,
            recommendation=fit.recommendation,
            matched_skills=json.dumps(fit.matched_skills),
            gaps=json.dumps(fit.gaps),
            fit_reasons=fit.reasons,
            raw_data=json.dumps(raw.raw_data) if raw.raw_data else None,
        )

    @staticmethod
    def _job_to_rawjob(job: Job) -> RawJob:
        return RawJob(
            source_id=job.source_id,
            agency_id=job.agency_id,
            agency_name=job.agency_name,
            county=job.county,
            title=job.title,
            department=job.department,
            job_type=job.job_type,
            location=job.location,
            salary_raw=job.salary_raw,
            description=job.description,
            requirements=job.requirements,
            apply_url=job.apply_url,
            source_url=job.source_url,
        )

    @staticmethod
    def _fit_from_job(job: Job):
        from .matching import FitResult

        return FitResult(
            score=job.fit_score or 0.0,
            lexical_score=job.lexical_score or 0.0,
            semantic_score=job.semantic_score,
            matched_skills=json.loads(job.matched_skills) if job.matched_skills else [],
            gaps=json.loads(job.gaps) if job.gaps else [],
            reasons=job.fit_reasons or "",
            recommendation=job.recommendation or "",
        )

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        with open(path) as f:
            return yaml.safe_load(f) or {}
