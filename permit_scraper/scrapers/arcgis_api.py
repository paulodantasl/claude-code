"""
ArcGIS FeatureServer REST API scraper.

Used by City of Tampa permits (fully public, no auth required) and
Hillsborough County Property Appraiser data.

ArcGIS REST query syntax:
  GET {serviceUrl}/{layerId}/query
    ?where=<SQL-where>
    &outFields=*
    &resultOffset=0
    &resultRecordCount=2000
    &f=json

Docs: https://developers.arcgis.com/rest/services-reference/
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, RawPermit

logger = logging.getLogger(__name__)

# Known Tampa FeatureServer layer IDs
TAMPA_PERMITS_SERVICE = "https://arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer"
TAMPA_INSPECTIONS_SERVICE = "https://arcgis.tampagov.net/arcgis/rest/services/Planning/ConstructionInspections/FeatureServer"


class ArcGISPermitScraper(BaseScraper):
    """
    Scrapes permit records from an ArcGIS FeatureServer endpoint.

    Works without any authentication for public services (e.g. Tampa).
    """

    def __init__(self, county_config: dict[str, Any]):
        super().__init__(county_config)
        self.service_url = county_config["arcgis_service_url"].rstrip("/")
        self.layer_id = county_config.get("arcgis_layer_id", 0)
        self.date_field = county_config.get("arcgis_date_field", "APPLICATIONDATE")
        self.max_records = county_config.get("arcgis_max_records", 2000)

    @property
    def query_url(self) -> str:
        return f"{self.service_url}/{self.layer_id}/query"

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_page(self, params: dict) -> dict:
        resp = requests.get(self.query_url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def scrape(self, days_back: int = 7, permit_types: list[str] | None = None) -> list[RawPermit]:
        since = datetime.utcnow() - timedelta(days=days_back)
        # ArcGIS uses Unix epoch milliseconds for date comparisons
        since_epoch_ms = int(since.timestamp() * 1000)

        where = f"{self.date_field} >= DATE '{since.strftime('%Y-%m-%d')}'"

        if permit_types:
            type_conditions = " OR ".join(
                f"UPPER(PERMITTYPE) LIKE '%{pt.upper()}%'" for pt in permit_types
            )
            where += f" AND ({type_conditions})"

        all_records: list[RawPermit] = []
        offset = 0

        # First: discover available fields by querying layer metadata
        fields = self._get_layer_fields()
        date_field = self._find_date_field(fields)
        if date_field and date_field != self.date_field:
            self.logger.info("Using detected date field: %s", date_field)
            where = f"{date_field} >= DATE '{since.strftime('%Y-%m-%d')}'"

        while True:
            params = {
                "where": where,
                "outFields": "*",
                "resultOffset": offset,
                "resultRecordCount": self.max_records,
                "orderByFields": f"{date_field or self.date_field} DESC",
                "f": "json",
            }
            self.logger.info("ArcGIS query offset=%d for %s", offset, self.county_name)

            try:
                data = self._fetch_page(params)
            except Exception as exc:
                self.logger.error("ArcGIS fetch failed: %s", exc)
                break

            if "error" in data:
                self.logger.error("ArcGIS API error: %s", data["error"])
                # Retry with a broader where clause
                if "date" in str(data["error"]).lower() or "field" in str(data["error"]).lower():
                    params["where"] = "1=1"
                    try:
                        data = self._fetch_page(params)
                    except Exception:
                        break
                else:
                    break

            features = data.get("features", [])
            if not features:
                break

            for feature in features:
                attrs = feature.get("attributes", {})
                geom = feature.get("geometry", {})
                permit = self._normalise(attrs, geom)
                if permit:
                    all_records.append(permit)

            # ArcGIS paginates when exceededTransferLimit is True
            if not data.get("exceededTransferLimit", False):
                break
            offset += self.max_records

        self.logger.info("Fetched %d permits from %s (ArcGIS)", len(all_records), self.county_name)
        return all_records

    def _get_layer_fields(self) -> list[str]:
        """Query layer metadata to get available field names."""
        try:
            resp = requests.get(
                f"{self.service_url}/{self.layer_id}",
                params={"f": "json"},
                timeout=15,
            )
            data = resp.json()
            return [f["name"] for f in data.get("fields", [])]
        except Exception:
            return []

    def _find_date_field(self, fields: list[str]) -> str | None:
        """Pick the best date field from available fields."""
        candidates = [
            "APPLICATIONDATE", "APPLIEDDATE", "FILEDDATE", "ISSUEDDATE",
            "OPENEDDATE", "CREATEDATE", "CREATEDDATE", "SUBMITDATE",
            "ApplicationDate", "AppliedDate", "FiledDate",
        ]
        field_upper = {f.upper(): f for f in fields}
        for c in candidates:
            if c.upper() in field_upper:
                return field_upper[c.upper()]
        return None

    def _normalise(self, attrs: dict, geom: dict) -> RawPermit | None:
        def g(*keys: str) -> Any:
            for k in keys:
                v = attrs.get(k)
                if v is not None and v != "" and v != "N/A":
                    return v
            return None

        source_id = str(
            g("PERMITNUM", "PERMIT_NUM", "OBJECTID", "GLOBALID", "PERMITNUMBER",
              "PermitNum", "PermitNumber", "RECORDID") or ""
        )
        if not source_id:
            return None

        # Convert ArcGIS epoch ms to datetime
        raw_date = g("APPLICATIONDATE", "APPLIEDDATE", "FILEDDATE", "ISSUEDDATE",
                     "OPENEDDATE", "CREATEDATE", "ApplicationDate", "AppliedDate")
        filed_date = None
        if isinstance(raw_date, (int, float)) and raw_date > 0:
            filed_date = datetime.utcfromtimestamp(raw_date / 1000)
        else:
            filed_date = self._parse_date(raw_date)

        # Coordinates from geometry
        lat = lon = None
        if geom:
            lon = geom.get("x")
            lat = geom.get("y")

        return RawPermit(
            source_id=source_id,
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=str(source_id),
            permit_type=str(g("PERMITTYPE", "PERMIT_TYPE", "WORKTYPE", "PermitType", "WorkType") or ""),
            status=str(g("STATUSDESC", "STATUS", "PERMITSTATUS", "StatusDesc", "Status") or ""),
            description=str(g("DESCRIPTION", "WORKDESCRIPTION", "SCOPE", "Description") or ""),
            applicant_name=str(g("APPLICANTNAME", "APPLICANT", "OWNERNAME", "OWNER",
                                  "ApplicantName", "Applicant") or ""),
            owner_name=str(g("OWNERNAME", "OWNER", "PROPERTYOWNER", "OwnerName") or ""),
            contractor_name=str(g("CONTRACTORNAME", "CONTRACTOR", "ContractorName") or ""),
            address=str(g("ADDRESS", "SITEADDRESS", "STREETADDRESS", "FULLADDRESS",
                           "JOBADDRESS", "Address", "SiteAddress") or ""),
            city=str(g("CITY", "MUNICIPALITY", "City") or self.county_name),
            state="FL",
            zip_code=str(g("ZIP", "ZIPCODE", "ZIP_CODE", "POSTALCODE", "Zip") or ""),
            parcel_number=str(g("PARCELID", "PARCEL", "FOLIO", "ParcelId", "Folio") or ""),
            estimated_value=self._parse_float(
                g("ESTIMATEDVALUE", "JOBVALUE", "DECLAREDVALUATION", "PROJECTVALUE",
                  "EstimatedValue", "JobValue")
            ),
            total_sqft=self._parse_float(g("SQFT", "TOTALSQFT", "SQUAREFEET", "SqFt")),
            filed_date=filed_date,
            latitude=lat,
            longitude=lon,
            source_url=self.query_url,
            raw_data=attrs,
        )
