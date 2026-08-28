from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ideal_apis.client import IdealAPIs
from ideal_apis.pipeline.models import Brand, LeadRecord, Priority, Source


def _lead_id(source: Source, key: str) -> str:
    digest = hashlib.sha256(f"{source}:{key}".encode()).hexdigest()[:12]
    return f"{source}_{digest}"


def _pick_address(addresses: list[dict[str, Any]], purpose: str = "LOCATION") -> dict[str, Any] | None:
    for addr in addresses:
        if addr.get("address_purpose") == purpose:
            return addr
    return addresses[0] if addresses else None


def nppes_to_leads(data: dict[str, Any], *, brand: Brand, taxonomy: str) -> list[LeadRecord]:
    leads: list[LeadRecord] = []
    for row in data.get("results", []):
        basic = row.get("basic", {})
        name = basic.get("organization_name") or " ".join(
            filter(None, [basic.get("first_name"), basic.get("last_name")])
        )
        if not name:
            continue
        npi = row.get("number")
        addr = _pick_address(row.get("addresses", []))
        if not addr:
            continue
        phone = addr.get("telephone_number")
        lead = LeadRecord(
            id=_lead_id("nppes", str(npi or name)),
            source="nppes",
            brand=brand,
            name=name.strip(),
            phone=phone,
            street=addr.get("address_1"),
            city=addr.get("city"),
            state=addr.get("state"),
            zip_code=(addr.get("postal_code") or "")[:5] or None,
            taxonomy=taxonomy,
            npi=str(npi) if npi else None,
            priority="high" if taxonomy.lower().startswith("dent") else "medium",
            raw={"nppes": row},
        )
        if lead.has_contact_channel():
            leads.append(lead)
    return leads


def yelp_to_leads(data: dict[str, Any], *, brand: Brand, term: str) -> list[LeadRecord]:
    leads: list[LeadRecord] = []
    for biz in data.get("businesses", []):
        loc = biz.get("location", {})
        address_parts = loc.get("display_address") or []
        street = address_parts[0] if address_parts else None
        city = loc.get("city")
        state = loc.get("state")
        zip_code = loc.get("zip_code")
        lead = LeadRecord(
            id=_lead_id("yelp", biz.get("id", biz.get("name", ""))),
            source="yelp",
            brand=brand,
            name=biz.get("name", "Unknown"),
            phone=biz.get("phone"),
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            taxonomy=term,
            priority="medium",
            notes=biz.get("url"),
            raw={"yelp": biz},
        )
        if lead.has_contact_channel():
            leads.append(lead)
    return leads


def openfema_to_leads(data: dict[str, Any], *, brand: Brand = "ideal_remodeling") -> list[LeadRecord]:
    leads: list[LeadRecord] = []
    for row in data.get("DisasterDeclarationsSummaries", []):
        title = row.get("declarationTitle") or row.get("femaDeclarationString", "Disaster")
        incident = row.get("incidentType", "")
        decl = (row.get("declarationDate") or "")[:10]
        key = row.get("femaDeclarationString") or title
        lead = LeadRecord(
            id=_lead_id("openfema", key),
            source="openfema",
            brand=brand,
            name=f"FEMA {incident}: {title}",
            state=row.get("state"),
            priority="high" if incident in ("Hurricane", "Flood", "Severe Storm", "Tornado") else "medium",
            notes=f"Declaration {decl}; IA={row.get('iaProgramDeclared')} PA={row.get('paProgramDeclared')}",
            raw={"openfema": row},
        )
        leads.append(lead)
    return leads


def usaspending_to_leads(data: dict[str, Any], *, brand: Brand = "ideal_cgc") -> list[LeadRecord]:
    leads: list[LeadRecord] = []
    for row in data.get("results", []):
        recipient = row.get("Recipient Name") or row.get("recipient_name") or "Unknown"
        award_id = row.get("Award ID") or row.get("generated_internal_id") or recipient
        lead = LeadRecord(
            id=_lead_id("usaspending", str(award_id)),
            source="usaspending",
            brand=brand,
            name=str(recipient),
            state=row.get("Place of Performance State Code"),
            priority="medium",
            notes=str(row.get("Description") or row.get("Awarding Agency") or "")[:200],
            raw={"usaspending": row},
        )
        leads.append(lead)
    return leads


def federal_contracts_to_leads(data: dict[str, Any], *, brand: Brand = "ideal_cgc") -> list[LeadRecord]:
    leads: list[LeadRecord] = []
    items = data if isinstance(data, list) else data.get("data") or data.get("contracts") or []
    for row in items:
        if not isinstance(row, dict):
            continue
        name = row.get("recipient") or row.get("vendor_name") or row.get("title") or "Federal contract"
        cid = row.get("id") or row.get("contract_id") or name
        lead = LeadRecord(
            id=_lead_id("federal_contracts", str(cid)),
            source="federal_contracts",
            brand=brand,
            name=str(name),
            priority="medium",
            notes=str(row.get("description") or row.get("agency") or "")[:200],
            raw={"contract": row},
        )
        leads.append(lead)
    return leads


def weather_to_leads(alerts: dict[str, Any], hail_reports: list[dict[str, Any]]) -> list[LeadRecord]:
    leads: list[LeadRecord] = []
    for feature in alerts.get("features", []):
        props = feature.get("properties", {})
        event = props.get("event") or "Weather Alert"
        area = props.get("areaDesc") or "FL"
        key = props.get("id") or f"{event}:{area}"
        leads.append(
            LeadRecord(
                id=_lead_id("weather", key),
                source="weather",
                brand="ideal_remodeling",
                name=f"NWS Alert: {event}",
                state="FL",
                priority="high" if event in ("Tornado Warning", "Flash Flood Warning", "Hurricane Warning") else "medium",
                notes=f"{area} — {props.get('headline', '')[:180]}",
                raw={"alert": props},
            )
        )
    for report in hail_reports:
        leads.append(
            LeadRecord(
                id=_lead_id("weather", f"hail:{report['name']}:{report.get('count', 0)}"),
                source="weather",
                brand="ideal_remodeling",
                name=f"Hail activity near {report['name']}",
                priority="high" if report.get("count", 0) > 0 else "low",
                notes=f"{report.get('count', 0)} NOAA hail signatures in last {report.get('days', 180)} days",
                raw={"hail": report},
            )
        )
    return leads


class LeadSources:
    """Fetch leads from all configured public API sources."""

    def __init__(self, api: IdealAPIs):
        self.api = api

    def fetch_nppes(self, cfg: dict[str, Any]) -> list[LeadRecord]:
        brand: Brand = cfg["brand"]
        taxonomy = cfg["taxonomy"]
        state = cfg.get("state", "FL")
        limit = int(cfg.get("limit", 25))
        cities = cfg.get("cities") or [None]
        per_city = max(5, limit // max(len(cities), 1))
        all_leads: list[LeadRecord] = []
        for city in cities:
            data = self.api.leads.nppes_search(
                state=state,
                city=city,
                taxonomy_description=taxonomy,
                enumeration_type="NPI-2",
                limit=per_city,
            )
            all_leads.extend(nppes_to_leads(data, brand=brand, taxonomy=taxonomy))
        return all_leads[:limit]

    def fetch_yelp(self, cfg: dict[str, Any]) -> list[LeadRecord]:
        data = self.api.leads.yelp_search(
            cfg["term"],
            cfg["location"],
            limit=int(cfg.get("limit", 10)),
        )
        return yelp_to_leads(data, brand=cfg["brand"], term=cfg["term"])

    def fetch_openfema(self, cfg: dict[str, Any]) -> list[LeadRecord]:
        data = self.api.government.openfema_disasters(
            states=cfg.get("states", ["FL"]),
            incident_types=cfg.get("incident_types"),
            days_back=int(cfg.get("days_back", 90)),
        )
        return openfema_to_leads(data)

    def fetch_usaspending(self, limit: int = 10) -> list[LeadRecord]:
        data = self.api.government.usaspending_florida_construction(limit=limit)
        return usaspending_to_leads(data)

    def fetch_federal_contracts(self, state: str = "FL", limit: int = 10) -> list[LeadRecord]:
        data = self.api.government.federal_contracts(state=state, limit=limit)
        return federal_contracts_to_leads(data)

    def fetch_weather(self, cfg: dict[str, Any]) -> list[LeadRecord]:
        alerts = self.api.weather.nws_alerts(state=cfg.get("alert_state", "FL"))
        hail_reports: list[dict[str, Any]] = []
        days = int(cfg.get("hail_days_back", 180))
        for point in cfg.get("hail_points", []):
            try:
                result = self.api.weather.hail_near(
                    point["lat"], point["lon"], days_back=days, radius_deg=0.2,
                )
                count = len(result) if isinstance(result, list) else 0
                hail_reports.append({"name": point["name"], "count": count, "days": days})
            except Exception:
                hail_reports.append({"name": point["name"], "count": 0, "days": days, "error": True})
        return weather_to_leads(alerts, hail_reports)
