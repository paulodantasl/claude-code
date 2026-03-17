"""
Property Appraiser scrapers for Central FL and Central West FL counties.

Two implementations:
  1. ArcGISPropertyScraper   — for counties with public ArcGIS services
                               (Hillsborough: gis.hcpafl.org)
  2. WebPropertyScraper      — for counties with HTML-only search
                               (Pasco: search.pascopa.com)

The property appraiser data is used to cross-reference permit applicants
with recent land sales — a company that just bought a parcel and then
immediately pulls a large commercial permit is a very strong signal.

Dataclass returned: RawProperty (mapped to PropertyRecord in DB)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class RawProperty:
    parcel_number: str
    county_id: str
    county_name: str
    owner_name: str | None = None
    mailing_address: str | None = None
    site_address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    land_use: str | None = None
    zoning: str | None = None
    assessed_value: float | None = None
    land_area_sqft: float | None = None
    building_area_sqft: float | None = None
    last_sale_date: datetime | None = None
    last_sale_price: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    raw_data: dict = field(default_factory=dict)


# ── Hillsborough County Property Appraiser (ArcGIS) ─────────────────────────

HCPA_ARCGIS_BASE = "https://gis.hcpafl.org/arcgis/rest/services"

# Known layer endpoints for Hillsborough PA
# (Layer IDs discovered from ArcGIS Hub at hcpafl.org)
HCPA_LAYERS = {
    "parcels": f"{HCPA_ARCGIS_BASE}/Property/PropertySales/FeatureServer/0",
    "sales":   f"{HCPA_ARCGIS_BASE}/Property/PropertySales/FeatureServer/1",
}


class HillsboroughPropertyScraper:
    """
    Fetches recent property sales from Hillsborough County Property Appraiser
    via ArcGIS FeatureServer.

    Focus: parcels with recent ownership changes — signals a company
    acquiring land before a development project.
    """

    COUNTY_ID = "hillsborough_county"
    COUNTY_NAME = "Hillsborough County, FL"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=15))
    def _query(self, url: str, params: dict) -> dict:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def scrape_recent_sales(self, days_back: int = 90) -> list[RawProperty]:
        """Fetch parcels with sales recorded in the last N days."""
        since = datetime.utcnow() - timedelta(days=days_back)
        since_str = since.strftime("%Y-%m-%d")
        results: list[RawProperty] = []

        for layer_name, url in HCPA_LAYERS.items():
            offset = 0
            while True:
                params = {
                    "where": f"SALEDATE >= DATE '{since_str}'",
                    "outFields": "*",
                    "resultOffset": offset,
                    "resultRecordCount": 2000,
                    "orderByFields": "SALEDATE DESC",
                    "f": "json",
                }
                try:
                    data = self._query(url, params)
                except Exception as exc:
                    logger.error("HCPA %s query failed: %s", layer_name, exc)
                    break

                if "error" in data:
                    logger.warning("HCPA error on %s: %s", layer_name, data["error"])
                    break

                features = data.get("features", [])
                if not features:
                    break

                for f in features:
                    prop = self._normalise(f.get("attributes", {}), f.get("geometry", {}))
                    if prop:
                        results.append(prop)

                if not data.get("exceededTransferLimit"):
                    break
                offset += 2000

        logger.info("Hillsborough PA: fetched %d recent sales", len(results))
        return results

    def scrape_by_owner(self, owner_names: list[str]) -> list[RawProperty]:
        """Look up parcels owned by specific names (fuzzy LIKE search)."""
        results: list[RawProperty] = []
        for name in owner_names:
            safe = name.upper().replace("'", "''")
            params = {
                "where": f"UPPER(OWNERNAME) LIKE '%{safe}%'",
                "outFields": "*",
                "resultRecordCount": 500,
                "f": "json",
            }
            try:
                data = self._query(HCPA_LAYERS["parcels"], params)
                for feat in data.get("features", []):
                    prop = self._normalise(feat.get("attributes", {}), feat.get("geometry", {}))
                    if prop:
                        results.append(prop)
            except Exception as exc:
                logger.error("HCPA owner search failed for %r: %s", name, exc)

        return results

    def _normalise(self, attrs: dict, geom: dict) -> RawProperty | None:
        def g(*keys: str) -> Any:
            for k in keys:
                v = attrs.get(k)
                if v is not None and str(v).strip() not in ("", "N/A", "null"):
                    return v
            return None

        parcel = str(g("FOLIO", "PARCELID", "PARCEL_ID", "OBJECTID") or "")
        if not parcel:
            return None

        sale_date = None
        raw_sale = g("SALEDATE", "LASTDATE", "SALE_DATE")
        if isinstance(raw_sale, (int, float)) and raw_sale > 0:
            sale_date = datetime.utcfromtimestamp(raw_sale / 1000)
        elif raw_sale:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    sale_date = datetime.strptime(str(raw_sale)[:10], fmt[:len(str(raw_sale)[:10])])
                    break
                except ValueError:
                    continue

        lat = geom.get("y") if geom else None
        lon = geom.get("x") if geom else None

        return RawProperty(
            parcel_number=parcel,
            county_id=self.COUNTY_ID,
            county_name=self.COUNTY_NAME,
            owner_name=str(g("OWNERNAME", "OWNER_NAME", "OWNER") or ""),
            mailing_address=str(g("MAILINGADDRESS", "MAILING_ADDRESS") or ""),
            site_address=str(g("SITEADDRESS", "SITE_ADDRESS", "ADDRESS") or ""),
            city=str(g("CITY", "SITECITY") or ""),
            zip_code=str(g("ZIP", "ZIPCODE", "SITEZIP") or ""),
            land_use=str(g("LANDUSE", "LAND_USE", "DORCDE", "USECD") or ""),
            assessed_value=_to_float(g("JUSTVALUE", "JUST_VALUE", "ASSESSEDVALUE", "TOTALVALUE")),
            land_area_sqft=_to_float(g("LANDSIZE", "LAND_SIZE", "LANDAREA")),
            building_area_sqft=_to_float(g("BUILDINGAREA", "BUILDING_AREA", "LIVINGAREA")),
            last_sale_date=sale_date,
            last_sale_price=_to_float(g("SALEPRICE", "SALE_PRICE", "SALAMT")),
            latitude=lat,
            longitude=lon,
            raw_data=attrs,
        )


# ── Pasco County Property Appraiser (Playwright web scraper) ────────────────

class PascoPropertyScraper:
    """
    Scrapes the Pasco County Property Appraiser at search.pascopa.com.
    Uses Playwright since there's no public API.

    Primary use case: look up a specific parcel after finding it in a
    permit record, to see recent ownership/sale info.
    """

    BASE_URL = "https://search.pascopa.com"
    COUNTY_ID = "pasco_county"
    COUNTY_NAME = "Pasco County, FL"

    def lookup_by_owner(self, owner_name: str) -> list[RawProperty]:
        """Search for all parcels owned by a given name."""
        from playwright.sync_api import sync_playwright
        from .browser_utils import CHROMIUM_PATH

        results: list[RawProperty] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=CHROMIUM_PATH)
            page = browser.new_page()
            page.set_default_timeout(20_000)
            try:
                page.goto(f"{self.BASE_URL}/search.aspx", wait_until="networkidle")
                # Switch to Name search tab
                name_tab = page.locator("a:has-text('Name'), button:has-text('Name'), li:has-text('Owner Name')")
                if name_tab.count():
                    name_tab.first.click()
                    page.wait_for_load_state("networkidle")

                # Fill owner name field
                name_input = page.locator("input[name*='name' i], input[placeholder*='name' i], #txtOwnerName")
                if name_input.count():
                    name_input.first.fill(owner_name)
                    page.keyboard.press("Enter")
                    page.wait_for_load_state("networkidle")
                    results = self._parse_results(page)
            except Exception as exc:
                logger.error("Pasco PA scrape failed: %s", exc)
            finally:
                browser.close()

        return results

    def lookup_by_parcel(self, parcel_id: str) -> RawProperty | None:
        """Look up a single parcel by ID."""
        from playwright.sync_api import sync_playwright
        from .browser_utils import CHROMIUM_PATH

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=CHROMIUM_PATH)
            page = browser.new_page()
            page.set_default_timeout(20_000)
            try:
                page.goto(f"{self.BASE_URL}/search.aspx", wait_until="networkidle")
                parcel_input = page.locator("input[name*='parcel' i], #txtParcelID, input[placeholder*='parcel' i]")
                if parcel_input.count():
                    parcel_input.first.fill(parcel_id)
                    page.keyboard.press("Enter")
                    page.wait_for_load_state("networkidle")
                    props = self._parse_results(page)
                    return props[0] if props else None
            except Exception as exc:
                logger.error("Pasco PA parcel lookup failed: %s", exc)
                return None
            finally:
                browser.close()

    def _parse_results(self, page: Any) -> list[RawProperty]:
        results = []
        rows = page.locator("table tr[class*='result'], table.search-results tr:not(:first-child), tbody tr")
        for i in range(min(rows.count(), 200)):
            row = rows.nth(i)
            cells = row.locator("td")
            if cells.count() < 3:
                continue
            texts = [cells.nth(j).inner_text().strip() for j in range(cells.count())]
            parcel = texts[0] if texts else ""
            if not parcel or not any(c.isdigit() for c in parcel):
                continue
            results.append(RawProperty(
                parcel_number=parcel,
                county_id=self.COUNTY_ID,
                county_name=self.COUNTY_NAME,
                owner_name=texts[1] if len(texts) > 1 else None,
                site_address=texts[2] if len(texts) > 2 else None,
                raw_data={"cells": texts},
            ))
        return results


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None
