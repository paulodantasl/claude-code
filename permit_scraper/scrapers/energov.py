"""
Tyler Technologies EnerGov / GovHub scraper (Playwright-based).

EnerGov (now marketed as Tyler GovHub) is widely deployed across the
Tampa Bay area: Hillsborough County, City of Tampa, Pasco County,
Manatee County, and others.

Portal URL pattern: https://<jurisdiction>.governmentwindow.com/
                or: https://<jurisdiction>govhub.com/
                or: https://energov.<jurisdiction>.gov/

Strategy:
  1. Navigate to the public permit search page.
  2. Intercept internal REST calls (/api/Records, /api/Permits).
  3. Fall back to HTML table parsing if API interception fails.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from playwright.sync_api import sync_playwright

from .base import BaseScraper, RawPermit
from .browser_utils import CHROMIUM_PATH

logger = logging.getLogger(__name__)


class EnerGovScraper(BaseScraper):
    """Scrapes permit data from Tyler Technologies EnerGov / GovHub portals."""

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
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.set_default_timeout(30_000)

            api_records: list[dict] = []

            def capture_response(response: Any) -> None:
                url = response.url.lower()
                if any(seg in url for seg in ["/api/permits", "/api/records", "/permitlist",
                                               "/searchresults", "/publicsearch"]):
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            api_records.extend(data)
                        elif isinstance(data, dict):
                            for key in ("Result", "result", "items", "data", "permits", "records"):
                                if key in data and isinstance(data[key], list):
                                    api_records.extend(data[key])
                                    break
                    except Exception:
                        pass

            page.on("response", capture_response)

            try:
                # EnerGov public search URL patterns
                for path in ["/GovHub/Permits/PublicSearch", "/EnerGov/Permits/Search",
                              "/SelfService/Permits", "/SelfService#/permits"]:
                    url = f"{self.base_url}{path}"
                    try:
                        page.goto(url, wait_until="networkidle", timeout=15_000)
                        if "permit" in page.title().lower() or page.locator("input, select").count() > 2:
                            self.logger.info("Found search page at %s", url)
                            break
                    except Exception:
                        continue

                since_str = since.strftime("%m/%d/%Y")

                # Try filling date fields
                for sel in ["#dateFrom", "#startDate", "input[placeholder*='from' i]",
                             "input[placeholder*='start' i]", "input[aria-label*='from' i]"]:
                    loc = page.locator(sel)
                    if loc.count():
                        loc.first.fill(since_str)
                        break

                # Submit
                submit = page.locator("button[type='submit'], button:has-text('Search')")
                if submit.count():
                    submit.first.click()
                    page.wait_for_load_state("networkidle")

                # Paginate
                for _ in range(50):
                    page.wait_for_load_state("networkidle")
                    next_btn = page.locator(
                        "button:has-text('Next'), [aria-label='Next page'], "
                        ".pagination-next:not(.disabled), li.next:not(.disabled) a"
                    )
                    if next_btn.count() and next_btn.first.is_enabled():
                        next_btn.first.click()
                    else:
                        break

            except Exception as exc:
                self.logger.error("EnerGov scrape failed for %s: %s", self.county_name, exc)
            finally:
                browser.close()

        if api_records:
            self.logger.info("Captured %d records via API intercept from %s", len(api_records), self.county_name)
            for rec in api_records:
                permit = self._normalise(rec)
                if permit:
                    results.append(permit)
        else:
            self.logger.warning("No API records captured for %s — set use_ai_agent: true to retry", self.county_name)

        return results

    def _normalise(self, rec: dict) -> RawPermit | None:
        # EnerGov uses PascalCase and camelCase inconsistently across versions
        def g(*keys: str) -> Any:
            for k in keys:
                if k in rec:
                    return rec[k]
            return None

        source_id = str(g("PermitNum", "permitNum", "RecordNumber", "Id", "id") or "")
        if not source_id:
            return None

        address_parts = [
            g("AddressLine1", "addressLine1", "StreetAddress", "streetAddress") or "",
        ]
        address = " ".join(p for p in address_parts if p).strip()

        applicant = g("Applicant", "applicant", "ContactName", "contactName")
        if isinstance(applicant, dict):
            applicant_name = applicant.get("Name") or applicant.get("name") or applicant.get("BusinessName") or ""
        else:
            applicant_name = str(applicant or "")

        return RawPermit(
            source_id=source_id,
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=source_id,
            permit_type=str(g("PermitType", "permitType", "WorkType", "workType", "Type", "type") or ""),
            status=str(g("StatusDesc", "statusDesc", "Status", "status") or ""),
            description=str(g("Description", "description", "WorkDescription", "workDescription", "Scope") or ""),
            applicant_name=applicant_name,
            owner_name=str(g("OwnerName", "ownerName", "Owner") or ""),
            contractor_name=str(g("ContractorName", "contractorName", "Contractor") or ""),
            address=address or str(g("FullAddress", "fullAddress") or ""),
            city=str(g("City", "city") or ""),
            state="FL",
            zip_code=str(g("Zip", "zip", "PostalCode", "postalCode") or ""),
            parcel_number=str(g("ParcelId", "parcelId", "Folio", "folio") or ""),
            estimated_value=self._parse_float(g("EstimatedValue", "estimatedValue", "JobValue", "jobValue")),
            filed_date=self._parse_date(g("FiledDate", "filedDate", "ApplicationDate", "applicationDate", "OpenedDate")),
            source_url=self.base_url,
            raw_data=rec,
        )
