"""
Scraper for governmentjobs.com (NEOGOV) agency career portals.

Most Florida city/county HR departments host their openings on NEOGOV's
governmentjobs.com platform. Each agency has a career portal at:

    https://www.governmentjobs.com/careers/{agency_slug}

The listing page paginates with ?page=N and each posting links to a detail
page that holds the full duties / minimum-qualifications text we need for
matching against the candidate's resume.

Strategy (most→least reliable, auto-selected by the pipeline):
  1. JSON fast-path  — some NEOGOV portals answer /careers/{slug}/jobs with a
     JSON body when sent `Accept: application/json`. Cheapest when available.
  2. HTML parse      — BeautifulSoup over the standard NEOGOV listing markup.
     Selectors are configurable per agency in targets/agencies.yaml so a markup
     change is a one-line fix, not a code change.
  3. AI agent        — if both fail, the pipeline falls back to the Claude +
     Playwright agent (see agents/application_agent.py companion scraper).

This module only ever READS public postings. No login happens here.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseJobScraper, RawJob
from .browser_utils import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

BASE = "https://www.governmentjobs.com"

# Default CSS selectors for the standard NEOGOV listing card. Overridable per
# agency via the `selectors:` block in agencies.yaml.
DEFAULT_SELECTORS = {
    "card": "div.list-item, li.list-item, div.job-search-result",
    "title": "a.item-details-link, h3 a, a.job-link, .item-title a",
    "department": ".item-department, .job-department, .list-department",
    "salary": ".item-salary, .job-salary, .list-salary",
    "job_type": ".item-type, .job-type, .list-type",
    "location": ".item-location, .job-location, .list-location",
    "closing": ".item-closing, .job-closing, .list-closing-date",
}


class GovernmentJobsScraper(BaseJobScraper):
    """Read open postings from a single NEOGOV agency career portal."""

    REQUEST_DELAY_S = 1.0   # be polite — one request per second per agency
    MAX_PAGES = 25

    def __init__(self, agency_config: dict[str, Any]):
        super().__init__(agency_config)
        self.slug: str = agency_config["slug"]
        self.base_url: str = agency_config.get(
            "base_url", f"{BASE}/careers/{self.slug}"
        )
        self.selectors = {**DEFAULT_SELECTORS, **(agency_config.get("selectors") or {})}
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def scrape(
        self,
        keywords: list[str] | None = None,
        max_jobs: int | None = None,
    ) -> list[RawJob]:
        jobs = self._scrape_json(keywords, max_jobs)
        if jobs is None:
            jobs = self._scrape_html(keywords, max_jobs)
        self.logger.info("%s → %d postings", self.agency_name, len(jobs))
        return jobs

    # ── Strategy 1: JSON fast-path ──────────────────────────────────────────

    def _scrape_json(
        self, keywords: list[str] | None, max_jobs: int | None
    ) -> list[RawJob] | None:
        url = f"{self.base_url.rstrip('/')}/jobs"
        try:
            resp = self.session.get(
                url, headers={"Accept": "application/json"}, timeout=25
            )
            ctype = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or "json" not in ctype.lower():
                return None
            payload = resp.json()
        except (requests.RequestException, ValueError):
            return None

        records = (
            payload.get("jobs")
            or payload.get("data")
            or payload.get("items")
            or (payload if isinstance(payload, list) else None)
        )
        if not isinstance(records, list):
            return None

        jobs: list[RawJob] = []
        for rec in records:
            job = self._job_from_json(rec)
            if job and self._matches_keywords(job, keywords):
                jobs.append(job)
                if max_jobs and len(jobs) >= max_jobs:
                    break
        return jobs

    def _job_from_json(self, rec: dict[str, Any]) -> RawJob | None:
        if not isinstance(rec, dict):
            return None
        ext_id = str(
            rec.get("id") or rec.get("jobId") or rec.get("recruitmentId") or ""
        )
        title = rec.get("title") or rec.get("jobTitle") or rec.get("name")
        if not (ext_id or title):
            return None
        smin, smax = self._parse_salary(rec.get("salary") or rec.get("salaryRange"))
        path = rec.get("url") or rec.get("link")
        apply_url = urljoin(BASE, path) if path else f"{self.base_url}/jobs/{ext_id}"
        return RawJob(
            source_id=f"{self.agency_id}:{ext_id or title}",
            agency_id=self.agency_id,
            agency_name=self.agency_name,
            county=self.county,
            title=title,
            department=rec.get("department") or rec.get("departmentName"),
            category=rec.get("category"),
            job_type=rec.get("type") or rec.get("jobType") or rec.get("employmentType"),
            location=rec.get("location") or rec.get("workLocation"),
            salary_min=smin,
            salary_max=smax,
            salary_raw=str(rec.get("salary") or rec.get("salaryRange") or "") or None,
            description=rec.get("description") or rec.get("jobDescription"),
            requirements=rec.get("requirements") or rec.get("qualifications"),
            posted_date=self._parse_date(rec.get("postedDate") or rec.get("openDate")),
            closing_date=self._parse_date(rec.get("closingDate") or rec.get("closeDate")),
            job_id_external=str(rec.get("recruitmentNumber") or ext_id) or None,
            apply_url=apply_url,
            source_url=apply_url,
            raw_data=rec,
        )

    # ── Strategy 2: HTML parse ──────────────────────────────────────────────

    def _scrape_html(
        self, keywords: list[str] | None, max_jobs: int | None
    ) -> list[RawJob]:
        jobs: list[RawJob] = []
        for page in range(1, self.MAX_PAGES + 1):
            url = self.base_url if page == 1 else f"{self.base_url}?page={page}"
            html = self._get(url)
            if not html:
                break
            cards = BeautifulSoup(html, "lxml").select(self.selectors["card"])
            if not cards:
                break
            for card in cards:
                job = self._job_from_card(card)
                if not job or not self._matches_keywords(job, keywords):
                    continue
                jobs.append(job)
                if max_jobs and len(jobs) >= max_jobs:
                    return jobs
            time.sleep(self.REQUEST_DELAY_S)
        return jobs

    def _job_from_card(self, card) -> RawJob | None:
        title_el = card.select_one(self.selectors["title"])
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        apply_url = urljoin(BASE, href) if href else None
        ext_id = self._id_from_url(href) or title

        def text(sel_key: str) -> str | None:
            el = card.select_one(self.selectors[sel_key])
            return el.get_text(" ", strip=True) if el else None

        salary_raw = text("salary")
        smin, smax = self._parse_salary(salary_raw)
        return RawJob(
            source_id=f"{self.agency_id}:{ext_id}",
            agency_id=self.agency_id,
            agency_name=self.agency_name,
            county=self.county,
            title=title,
            department=text("department"),
            job_type=text("job_type"),
            location=text("location"),
            salary_min=smin,
            salary_max=smax,
            salary_raw=salary_raw,
            closing_date=self._parse_date(text("closing")),
            job_id_external=ext_id if ext_id != title else None,
            apply_url=apply_url,
            source_url=apply_url,
        )

    def enrich_detail(self, job: RawJob) -> RawJob:
        """Fetch the posting detail page to fill description + requirements.

        Called by the pipeline only for jobs that clear the cheap keyword gate,
        so we don't fetch a detail page for every posting.
        """
        if not job.apply_url or job.description:
            return job
        html = self._get(job.apply_url)
        if not html:
            return job
        soup = BeautifulSoup(html, "lxml")

        # NEOGOV detail pages group sections under headed panels; grab the big ones.
        def section(*headings: str) -> str | None:
            for h in soup.find_all(["h2", "h3", "h4", "strong", "label"]):
                label = h.get_text(" ", strip=True).lower()
                if any(k in label for k in headings):
                    body = h.find_next(["div", "p", "ul", "section"])
                    if body:
                        return body.get_text("\n", strip=True)
            return None

        desc = section("definition", "description", "duties", "examples of duties", "summary")
        reqs = section(
            "minimum qualification", "qualification", "requirements", "knowledge",
            "education and experience",
        )
        main = soup.select_one("#detail-content, .job-detail, #js-job-detail, main")
        if not desc and main:
            desc = main.get_text("\n", strip=True)
        job.description = desc or job.description
        job.requirements = reqs or job.requirements
        return job

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _get(self, url: str) -> str | None:
        try:
            resp = self.session.get(url, timeout=25)
            if resp.status_code == 200 and resp.text:
                return resp.text
            self.logger.debug("GET %s → HTTP %s", url, resp.status_code)
        except requests.RequestException as exc:
            self.logger.warning("GET %s failed: %s", url, exc)
        return None

    @staticmethod
    def _id_from_url(href: str) -> str | None:
        import re

        m = re.search(r"/jobs/(\d+)", href or "")
        return m.group(1) if m else None

    @staticmethod
    def _matches_keywords(job: RawJob, keywords: list[str] | None) -> bool:
        if not keywords:
            return True
        hay = (job.full_text or "").lower()
        return any(k.lower() in hay for k in keywords)
