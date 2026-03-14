"""
Tyler Technologies CityView scraper (Playwright-based).

Used by the City of Orlando and some other Central FL municipalities.
CityView is a React SPA — we intercept its internal API calls to get
structured JSON rather than parsing HTML.

Portal pattern: https://<city>.gov/CityViewWeb/
API pattern:    https://<city>.gov/CityViewWeb/api/Permits/Search
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from playwright.sync_api import sync_playwright

from .base import BaseScraper, RawPermit

logger = logging.getLogger(__name__)


class CityViewScraper(BaseScraper):
    """Scrapes permit data from Tyler Technologies CityView portals."""

    def __init__(self, county_config: dict[str, Any]):
        super().__init__(county_config)
        self.base_url = county_config["base_url"].rstrip("/")
        self.headless = county_config.get("headless", True)

    def scrape(self, days_back: int = 7, permit_types: list[str] | None = None) -> list[RawPermit]:
        since = datetime.utcnow() - timedelta(days=days_back)
        results: list[RawPermit] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.set_default_timeout(30_000)

            # Intercept CityView internal API calls
            api_records: list[dict] = []

            def capture_response(response: Any) -> None:
                url = response.url.lower()
                if any(p in url for p in ["/api/permit", "/permits/search", "/permitlist", "/records"]):
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            api_records.extend(data)
                        elif isinstance(data, dict):
                            for key in ("items", "data", "results", "permits", "records"):
                                if key in data and isinstance(data[key], list):
                                    api_records.extend(data[key])
                                    break
                    except Exception:
                        pass

            page.on("response", capture_response)

            try:
                # Navigate and trigger permit search
                search_url = f"{self.base_url}/Permits"
                self.logger.info("Navigating to %s", search_url)
                page.goto(search_url, wait_until="networkidle")

                # Fill in date filter if present
                since_str = since.strftime("%m/%d/%Y")
                date_inputs = page.locator("input[type='date'], input[placeholder*='date' i], input[placeholder*='from' i]")
                if date_inputs.count():
                    date_inputs.first.fill(since_str)

                # Submit search or wait for auto-load
                search_btn = page.locator("button:has-text('Search'), button[type='submit']")
                if search_btn.count():
                    search_btn.first.click()
                    page.wait_for_load_state("networkidle")

                # Paginate through results
                for _ in range(50):  # max 50 pages
                    page.wait_for_load_state("networkidle")
                    next_btn = page.locator(
                        "button:has-text('Next'), [aria-label='Next page'], button[title='Next']"
                    )
                    if next_btn.count() and next_btn.first.is_enabled():
                        next_btn.first.click()
                    else:
                        break

            except Exception as exc:
                self.logger.error("CityView scrape failed for %s: %s", self.county_name, exc)
            finally:
                browser.close()

        # Parse intercepted API records
        if api_records:
            self.logger.info("Captured %d records via API intercept", len(api_records))
            for rec in api_records:
                permit = self._normalise(rec)
                if permit:
                    results.append(permit)
        else:
            self.logger.warning("No API records captured for %s — try use_ai_agent: true", self.county_name)

        return results

    def _normalise(self, rec: dict) -> RawPermit | None:
        # CityView uses camelCase field names
        source_id = str(
            rec.get("permitNumber") or rec.get("recordNumber")
            or rec.get("id") or rec.get("permitId") or ""
        )
        if not source_id:
            return None

        applicant = rec.get("applicant") or rec.get("owner") or {}
        if isinstance(applicant, str):
            applicant_name = applicant
        else:
            applicant_name = (
                applicant.get("name")
                or applicant.get("businessName")
                or f"{applicant.get('firstName', '')} {applicant.get('lastName', '')}".strip()
            )

        address = rec.get("address") or rec.get("siteAddress") or rec.get("workLocation") or {}
        if isinstance(address, str):
            addr_str = address
            city = zip_code = None
        else:
            addr_str = address.get("streetAddress") or address.get("address1") or ""
            city = address.get("city")
            zip_code = address.get("zip") or address.get("postalCode")

        return RawPermit(
            source_id=source_id,
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=source_id,
            permit_type=rec.get("permitType") or rec.get("type") or rec.get("workType"),
            status=rec.get("status") or rec.get("permitStatus"),
            description=rec.get("description") or rec.get("workDescription") or rec.get("scopeOfWork"),
            applicant_name=applicant_name,
            owner_name=(rec.get("owner") or {}).get("name") if isinstance(rec.get("owner"), dict) else None,
            contractor_name=(rec.get("contractor") or {}).get("name") if isinstance(rec.get("contractor"), dict) else None,
            address=addr_str,
            city=city or self.county_name,
            state="FL",
            zip_code=zip_code,
            parcel_number=rec.get("parcelNumber") or rec.get("folio"),
            estimated_value=self._parse_float(rec.get("estimatedValue") or rec.get("jobValue")),
            filed_date=self._parse_date(rec.get("filedDate") or rec.get("applicationDate") or rec.get("createdDate")),
            source_url=self.base_url,
            raw_data=rec,
        )
