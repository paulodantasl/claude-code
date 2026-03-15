"""
OpenGov Permitting & Licensing scraper (Playwright-based).

OpenGov is the second-most common SaaS permitting platform after Accela.
Portal URLs follow: https://<jurisdiction>.opengov.com/permits
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from playwright.sync_api import sync_playwright

from .base import BaseScraper, RawPermit
from .browser_utils import CHROMIUM_PATH

logger = logging.getLogger(__name__)


class OpenGovScraper(BaseScraper):
    """Scrapes permit data from OpenGov Permitting & Licensing portals."""

    def __init__(self, county_config: dict[str, Any]):
        super().__init__(county_config)
        self.base_url = county_config["base_url"].rstrip("/")
        self.headless = county_config.get("headless", True)

    def scrape(self, days_back: int = 7, permit_types: list[str] | None = None) -> list[RawPermit]:
        since = datetime.utcnow() - timedelta(days=days_back)
        results: list[RawPermit] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, executable_path=CHROMIUM_PATH)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.set_default_timeout(30_000)

            try:
                results = self._scrape_permits(page, since)
            except Exception as exc:
                self.logger.error("OpenGov scrape failed for %s: %s", self.county_name, exc)
            finally:
                browser.close()

        return results

    def _scrape_permits(self, page: Any, since: datetime) -> list[RawPermit]:
        # OpenGov public permit search endpoint pattern
        search_url = f"{self.base_url}/permits"
        self.logger.info("Navigating to %s", search_url)
        page.goto(search_url)
        page.wait_for_load_state("networkidle")

        results: list[RawPermit] = []

        # OpenGov uses React, so we intercept API calls to get JSON data
        api_responses: list[dict] = []

        def capture_response(response: Any) -> None:
            if "/api/permits" in response.url or "/permits/search" in response.url:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        api_responses.extend(data)
                    elif isinstance(data, dict) and "data" in data:
                        api_responses.extend(data["data"])
                except Exception:
                    pass

        page.on("response", capture_response)

        # Try the date filter UI
        date_str = since.strftime("%m/%d/%Y")
        filter_btn = page.locator("button:has-text('Filter'), button:has-text('Date')")
        if filter_btn.count():
            filter_btn.first.click()
            page.wait_for_selector("input[placeholder*='date'], input[type='date']")
            date_inputs = page.locator("input[placeholder*='date'], input[type='date']")
            if date_inputs.count():
                date_inputs.first.fill(date_str)
                apply_btn = page.locator("button:has-text('Apply')")
                if apply_btn.count():
                    apply_btn.first.click()
                    page.wait_for_load_state("networkidle")

        # If we captured API responses, use those
        if api_responses:
            for rec in api_responses:
                permit = self._normalise_api(rec)
                if permit:
                    results.append(permit)
        else:
            # Fall back to HTML parsing
            results = self._parse_html_results(page)

        return results

    def _parse_html_results(self, page: Any) -> list[RawPermit]:
        results: list[RawPermit] = []
        rows = page.locator("[data-testid='permit-row'], .permit-list-item, tr[class*='permit']")
        count = rows.count()
        self.logger.info("HTML fallback: %d rows found", count)

        for i in range(count):
            row = rows.nth(i)
            text = row.inner_text()
            cells = row.locator("td, [class*='cell']")
            cell_texts = [cells.nth(j).inner_text().strip() for j in range(cells.count())]
            raw = {"text": text, "cells": cell_texts}

            results.append(RawPermit(
                source_id=str(hash(text))[:16],
                county_id=self.county_id,
                county_name=self.county_name,
                description=text[:256],
                address=cell_texts[1] if len(cell_texts) > 1 else None,
                permit_type=cell_texts[0] if cell_texts else None,
                source_url=self.base_url,
                raw_data=raw,
            ))

        return results

    def _normalise_api(self, rec: dict) -> RawPermit | None:
        source_id = str(rec.get("id") or rec.get("permitNumber") or rec.get("number") or "")
        if not source_id:
            return None

        applicant = rec.get("applicant") or rec.get("contactInfo") or {}
        if isinstance(applicant, str):
            applicant_name = applicant
        else:
            applicant_name = applicant.get("name") or applicant.get("businessName") or ""

        location = rec.get("location") or rec.get("address") or {}
        if isinstance(location, str):
            address = location
            city = zip_code = None
        else:
            address = location.get("streetAddress") or location.get("address1") or ""
            city = location.get("city")
            zip_code = location.get("zip") or location.get("postalCode")

        return RawPermit(
            source_id=source_id,
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=str(rec.get("permitNumber") or rec.get("number") or source_id),
            permit_type=rec.get("type") or rec.get("permitType"),
            status=rec.get("status"),
            description=rec.get("description") or rec.get("workDescription"),
            applicant_name=applicant_name,
            address=address,
            city=city,
            state=self.config.get("state"),
            zip_code=zip_code,
            estimated_value=self._parse_float(rec.get("estimatedValue") or rec.get("value")),
            filed_date=self._parse_date(rec.get("filedDate") or rec.get("applicationDate") or rec.get("createdAt")),
            source_url=self.base_url,
            raw_data=rec,
        )
