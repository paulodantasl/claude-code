"""
Accela Automation portal scraper (Playwright-based).

Accela is the most widely deployed permitting platform in the US.
This scraper handles the Citizen Access portal UI used by most counties.

Strategy:
  1. Navigate to the permit search page.
  2. Set date range filter.
  3. Paginate through results.
  4. Extract permit details from result rows + detail pages.

Note: Some Accela installations expose a REST API (/api/v4/records).
      Use AccelaApiScraper below if the county has the API enabled.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from playwright.sync_api import Page, sync_playwright

from .base import BaseScraper, RawPermit
from .browser_utils import CHROMIUM_PATH

logger = logging.getLogger(__name__)

# Accela Citizen Access URL patterns
SEARCH_PATH = "/GeneralInquiry/GeneralInquiry.aspx"
RESULT_PATH = "/Cap/CapList.aspx"


class AccelaPlaywrightScraper(BaseScraper):
    """
    Browser-based scraper for Accela Citizen Access portals.
    Falls back to AI-guided navigation for non-standard setups.
    """

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

            try:
                results = self._run_search(page, since, permit_types)
            except Exception as exc:
                self.logger.error("Accela scrape failed for %s: %s", self.county_name, exc)
            finally:
                browser.close()

        return results

    def _run_search(
        self, page: Page, since: datetime, permit_types: list[str] | None
    ) -> list[RawPermit]:
        search_url = f"{self.base_url}{SEARCH_PATH}?module=Building&Type=Cap"
        self.logger.info("Navigating to %s", search_url)
        page.goto(search_url)
        page.wait_for_load_state("networkidle")

        # Fill in the date range
        self._fill_date_fields(page, since)

        # Submit search
        submit_btn = page.locator("input[type=submit][value*='Search'], button:has-text('Search')")
        if submit_btn.count():
            submit_btn.first.click()
            page.wait_for_load_state("networkidle")

        return self._extract_results(page)

    def _fill_date_fields(self, page: Page, since: datetime) -> None:
        date_str = since.strftime("%m/%d/%Y")
        today_str = datetime.utcnow().strftime("%m/%d/%Y")

        # Common Accela field IDs
        for field_id in ["ctl00_PlaceHolderMain_txtDateFrom", "DateRangePicker1_dateFrom", "txtDateFrom"]:
            locator = page.locator(f"#{field_id}")
            if locator.count():
                locator.fill(date_str)
                break

        for field_id in ["ctl00_PlaceHolderMain_txtDateTo", "DateRangePicker1_dateTo", "txtDateTo"]:
            locator = page.locator(f"#{field_id}")
            if locator.count():
                locator.fill(today_str)
                break

    def _extract_results(self, page: Page) -> list[RawPermit]:
        results: list[RawPermit] = []

        while True:
            rows = page.locator("table.ACA_Grid_HeaderFooter tr.ACA_TabRow_Odd, table.ACA_Grid_HeaderFooter tr.ACA_TabRow_Even")
            count = rows.count()
            self.logger.info("Found %d rows on current page", count)

            for i in range(count):
                row = rows.nth(i)
                permit = self._parse_row(row, page)
                if permit:
                    results.append(permit)

            # Pagination — try to click "Next"
            next_btn = page.locator("a:has-text('Next'), a[title='Go to next page']")
            if next_btn.count() and next_btn.first.is_enabled():
                next_btn.first.click()
                page.wait_for_load_state("networkidle")
            else:
                break

        return results

    def _parse_row(self, row: Any, page: Page) -> RawPermit | None:
        cells = row.locator("td")
        if cells.count() < 3:
            return None

        texts = [cells.nth(i).inner_text().strip() for i in range(cells.count())]
        raw = {"cells": texts}

        # Try to get a permit number from any cell
        permit_number = None
        for cell in texts:
            if re.match(r"[A-Z]{2,4}[-/]\d{4}[-/]\d+", cell):
                permit_number = cell
                break

        # Click into detail page if there's a link
        detail_link = row.locator("a").first
        detail_data: dict = {}
        if detail_link.count():
            href = detail_link.get_attribute("href")
            if href and "CapDetail" in href:
                try:
                    with page.context.expect_page() as new_page_info:
                        detail_link.click()
                    detail_page = new_page_info.value
                    detail_page.wait_for_load_state("networkidle")
                    detail_data = self._parse_detail_page(detail_page)
                    detail_page.close()
                except Exception as exc:
                    self.logger.debug("Could not open detail page: %s", exc)

        raw.update(detail_data)
        source_id = permit_number or texts[0] or str(hash(str(texts)))

        return RawPermit(
            source_id=source_id,
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=permit_number or detail_data.get("permit_number"),
            permit_type=detail_data.get("permit_type") or (texts[1] if len(texts) > 1 else None),
            status=detail_data.get("status") or (texts[-1] if texts else None),
            description=detail_data.get("description"),
            applicant_name=detail_data.get("applicant_name") or detail_data.get("owner_name"),
            owner_name=detail_data.get("owner_name"),
            contractor_name=detail_data.get("contractor_name"),
            contractor_license=detail_data.get("contractor_license"),
            contractor_phone=detail_data.get("contractor_phone"),
            owner_mailing_address=detail_data.get("owner_mailing_address"),
            address=detail_data.get("address"),
            city=detail_data.get("city"),
            state=self.config.get("state"),
            zip_code=detail_data.get("zip_code"),
            parcel_number=detail_data.get("parcel_number"),
            estimated_value=self._parse_float(detail_data.get("estimated_value")),
            filed_date=self._parse_date(detail_data.get("filed_date") or texts[2] if len(texts) > 2 else None),
            source_url=self.base_url,
            raw_data=raw,
        )

    def _parse_detail_page(self, page: Page) -> dict:
        """Extract labelled fields from an Accela detail page."""
        data: dict = {}
        # NOTE: matching is first-substring-wins, so more specific labels MUST
        # precede the generic ones they contain (e.g. "owner mailing" before
        # "owner", "contractor license" before "contractor", "…" before
        # "address").
        label_map = {
            "record number": "permit_number",
            "permit number": "permit_number",
            "project name": "description",
            "description": "description",
            "type": "permit_type",
            "status": "status",
            # parties — specific contact fields before generic name fields
            "owner mailing": "owner_mailing_address",
            "owner address": "owner_mailing_address",
            "mailing address": "owner_mailing_address",
            "primary owner": "owner_name",
            "owner": "owner_name",
            "contractor license": "contractor_license",
            "license number": "contractor_license",
            "state license": "contractor_license",
            "license #": "contractor_license",
            "business phone": "contractor_phone",
            "phone": "contractor_phone",
            "contractor": "contractor_name",
            "applicant": "applicant_name",
            # location / identifiers
            "parcel": "parcel_number",
            "folio": "parcel_number",
            "address": "address",
            # money
            "valuation": "estimated_value",
            "value": "estimated_value",
            # dates
            "issued date": "issued_date",
            "issue date": "issued_date",
            "date issued": "issued_date",
            "expiration date": "expiry_date",
            "expiration": "expiry_date",
            "expires": "expiry_date",
            "application date": "filed_date",
            "opened date": "filed_date",
            "filed date": "filed_date",
        }

        rows = page.locator("table tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            cells = row.locator("td, th")
            if cells.count() >= 2:
                label = cells.nth(0).inner_text().strip().lower().rstrip(":")
                value = cells.nth(1).inner_text().strip()
                for key, mapped in label_map.items():
                    if key in label:
                        data[mapped] = value
                        break

        return data

    # ── Per-permit lookup (monitoring) ──────────────────────────────────────

    def fetch_permits(self, refs: list[Any], lookback_days: int = 180) -> dict[str, RawPermit | None]:
        """
        Look up specific permits by record number via the Accela search page.

        More precise than the bulk scrape and reaches permits filed before the
        lookback window (important for long-pending projects). Falls back to the
        generic bulk-scrape indexing if the targeted search is unavailable or
        finds nothing.
        """
        results: dict[str, RawPermit | None] = {
            getattr(r, "permit_number", None): None for r in refs
        }
        try:
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
                try:
                    for ref in refs:
                        pnum = getattr(ref, "permit_number", None)
                        if not pnum:
                            continue
                        try:
                            results[pnum] = self._search_by_record_number(page, pnum)
                        except Exception as exc:
                            self.logger.debug("Record search failed for %s: %s", pnum, exc)
                finally:
                    browser.close()
        except Exception as exc:
            self.logger.error("Accela targeted lookup failed (%s); using bulk fallback", exc)
            return super().fetch_permits(refs, lookback_days=lookback_days)

        # Safety net: if nothing resolved, try the bulk approach once.
        if not any(results.values()):
            self.logger.info("Targeted search matched nothing; trying bulk scrape fallback")
            return super().fetch_permits(refs, lookback_days=lookback_days)
        return results

    def _search_by_record_number(self, page: Page, permit_number: str) -> RawPermit | None:
        search_url = f"{self.base_url}{SEARCH_PATH}?module=Building&Type=Cap"
        page.goto(search_url)
        page.wait_for_load_state("networkidle")

        # Fill the record/permit-number field (IDs vary across Accela versions).
        filled = False
        for field_id in [
            "ctl00_PlaceHolderMain_generalSearchForm_txtGSPermitNumber",
            "ctl00_PlaceHolderMain_txtGSPermitNumber",
            "ctl00_PlaceHolderMain_txtPermitNumber",
            "txtGSPermitNumber",
        ]:
            loc = page.locator(f"#{field_id}")
            if loc.count():
                loc.fill(permit_number)
                filled = True
                break
        if not filled:
            generic = page.locator(
                "input[id*='PermitNumber'], input[id*='RecordNumber'], input[name*='PermitNumber']"
            )
            if generic.count():
                generic.first.fill(permit_number)

        submit = page.locator("input[type=submit][value*='Search'], button:has-text('Search')")
        if submit.count():
            submit.first.click()
            page.wait_for_load_state("networkidle")

        # If we landed on a results list, click into the first detail link.
        detail_link = page.locator("a[href*='CapDetail'], table.ACA_Grid_HeaderFooter a")
        if detail_link.count():
            try:
                detail_link.first.click()
                page.wait_for_load_state("networkidle")
            except Exception:
                pass

        detail_data = self._parse_detail_page(page)
        if not detail_data:
            return None

        return RawPermit(
            source_id=permit_number,
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=detail_data.get("permit_number") or permit_number,
            permit_type=detail_data.get("permit_type"),
            status=detail_data.get("status"),
            description=detail_data.get("description"),
            applicant_name=detail_data.get("applicant_name") or detail_data.get("owner_name"),
            owner_name=detail_data.get("owner_name"),
            contractor_name=detail_data.get("contractor_name"),
            contractor_license=detail_data.get("contractor_license"),
            contractor_phone=detail_data.get("contractor_phone"),
            owner_mailing_address=detail_data.get("owner_mailing_address"),
            address=detail_data.get("address"),
            state=self.config.get("state"),
            zip_code=detail_data.get("zip_code"),
            parcel_number=detail_data.get("parcel_number"),
            estimated_value=self._parse_float(detail_data.get("estimated_value")),
            filed_date=self._parse_date(detail_data.get("filed_date")),
            issued_date=self._parse_date(detail_data.get("issued_date")),
            expiry_date=self._parse_date(detail_data.get("expiry_date")),
            source_url=f"{self.base_url}{SEARCH_PATH}",
            raw_data=detail_data,
        )


class AccelaApiScraper(BaseScraper):
    """
    REST API scraper for Accela installations that expose /api/v4/records.
    Requires an API key (contact the county IT department or register on
    the Accela developer portal).
    """

    def __init__(self, county_config: dict[str, Any]):
        super().__init__(county_config)
        self.api_base = county_config.get("api_url", county_config["base_url"].rstrip("/") + "/api/v4")
        self.api_token = county_config.get("accela_api_token")

    def scrape(self, days_back: int = 7, permit_types: list[str] | None = None) -> list[RawPermit]:
        import requests

        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z")
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
        results: list[RawPermit] = []
        offset = 0
        limit = 100

        while True:
            params: dict[str, Any] = {
                "openedDateFrom": since,
                "limit": limit,
                "offset": offset,
                "fields": "id,type,status,description,applicant,location,value,openedDate",
            }
            resp = requests.get(f"{self.api_base}/records", headers=headers, params=params, timeout=30)
            if resp.status_code == 401:
                self.logger.error("Accela API: unauthorized. Set accela_api_token in config.")
                break
            resp.raise_for_status()

            data = resp.json()
            records = data.get("result", [])
            if not records:
                break

            for rec in records:
                permit = self._normalise_api(rec)
                if permit:
                    results.append(permit)

            if len(records) < limit:
                break
            offset += limit

        return results

    def fetch_permits(self, refs: list[Any], lookback_days: int = 180) -> dict[str, RawPermit | None]:
        """Look up specific permits directly by their customId (record number)."""
        import requests

        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
        fields = (
            "id,customId,type,status,description,applicant,location,value,"
            "openedDate,issuedDate,expiredDate"
        )
        results: dict[str, RawPermit | None] = {
            getattr(r, "permit_number", None): None for r in refs
        }
        for ref in refs:
            pnum = getattr(ref, "permit_number", None)
            if not pnum:
                continue
            try:
                resp = requests.get(
                    f"{self.api_base}/records",
                    headers=headers,
                    params={"customId": pnum, "limit": 1, "fields": fields},
                    timeout=30,
                )
                if resp.status_code == 401:
                    self.logger.error("Accela API: unauthorized. Set accela_api_token in config.")
                    break
                resp.raise_for_status()
                records = resp.json().get("result", [])
                if records:
                    results[pnum] = self._normalise_api(records[0])
            except Exception as exc:
                self.logger.debug("Accela API lookup for %s failed: %s", pnum, exc)
        return results

    def _normalise_api(self, rec: dict) -> RawPermit | None:
        loc = rec.get("location", {})
        applicant = rec.get("applicant", {})
        return RawPermit(
            source_id=str(rec.get("customId") or rec.get("id", "")),
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=rec.get("customId") or rec.get("id"),
            permit_type=rec.get("type", {}).get("text"),
            status=rec.get("status", {}).get("text"),
            description=rec.get("description"),
            applicant_name=f"{applicant.get('firstName', '')} {applicant.get('lastName', '')}".strip()
            or applicant.get("businessName"),
            address=loc.get("streetAddress"),
            city=loc.get("city"),
            state=loc.get("stateProvinceCode"),
            zip_code=loc.get("postalCode"),
            parcel_number=loc.get("parcel"),
            estimated_value=self._parse_float(rec.get("value")),
            filed_date=self._parse_date(rec.get("openedDate")),
            issued_date=self._parse_date(rec.get("issuedDate")),
            expiry_date=self._parse_date(rec.get("expiredDate")),
            source_url=self.api_base,
            raw_data=rec,
        )
