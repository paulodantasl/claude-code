"""
City of Tampa active entitlements — PLAN.md §3 #4.

The earliest signal available anywhere in this system. 289 records, every one
a live case (`APPSTATUS` is In Process / Awaiting Client Reply / Open), each
with an address, a case type, a tentative hearing date and an Accela link.

What it does NOT carry: any business name. A rezoning application names the
applicant nowhere in this layer, so `entity` is null and the address is the
lead. The trade is likewise undeclared — nobody says what is going into the
building at rezoning — except for the AB Special Use cases, which are
alcoholic-beverage applications and therefore F&B.
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arcgis  # noqa: E402
import geo  # noqa: E402

SOURCE = "entitlement"
NAME = "Active entitlements"
SERVICE = "Planning/ActiveEntitlementLocations"
LAYER = 0

# RECORDALIAS -> the case types that precede a commercial buildout, and what
# they imply about the trade. Everything absent from this map is still
# collected, as a precursor with an undeclared trade.
AB_CASES = {"AB Special Use 2", "AB Special Use 1 - Standard"}

# Case types that are about land, not about a tenant: a right-of-way vacating
# or a residential variance will not produce a fitout.
LOW_VALUE_CASES = {"ROW Vacating", "Temp Special Event"}


def collect(days_back: int = 365) -> list[dict]:
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")

    feats = arcgis.fetch(SERVICE, LAYER,
                         where=f"CREATEDDATE >= DATE '{since}'",
                         order_by="CREATEDDATE DESC")
    out = []
    for a, lon, lat in arcgis.iter_attrs(feats):
        record_id = arcgis.clean(a.get("RECORDID"))
        if not record_id:
            continue
        alias = arcgis.clean(a.get("RECORDALIAS")) or ""
        unit = arcgis.clean(a.get("UNIT"))
        address = arcgis.clean(a.get("ADDRESS")) or ""
        hearing = arcgis.us_date_to_iso(a.get("TENTATIVEHEARING"))

        out.append({
            "id": "entitlement-" + hashlib.sha1(
                f"{SOURCE}:{record_id}".encode()).hexdigest()[:16],
            "source": SOURCE,
            "source_id": record_id,
            "source_url": arcgis.clean(a.get("URL")),
            "retrieved_at": retrieved,

            "hood": geo.hood_of(lon, lat),
            "address": f"{address} #{unit}" if unit else address,
            "zip": None,
            "lat": lat, "lon": lon,
            "city_neighborhood": arcgis.clean(a.get("NEIGHBORHOOD")),
            "cra": arcgis.clean(a.get("CRA")),
            "council_district": arcgis.clean(a.get("COUNCILDISTRICT")),

            # No applicant or business name exists in this layer.
            "entity": None,
            "brand": None,
            "trade": "restaurant" if alias in AB_CASES else "other",
            "confidence": 0.8 if alias in AB_CASES else 0.2,
            "stage_hint": "pre_permit",
            "record_type": alias,
            "occupancy_category": None,
            "occupancy_type": None,
            "is_fitout": alias not in LOW_VALUE_CASES,
            "is_dwelling": False,

            "value_est": None,
            "sqft": None,
            "seats": None,
            "filed_at": arcgis.epoch_to_date(a.get("CREATEDDATE")),
            "issued_at": None,
            "hearing_at": hearing,
            "app_status": arcgis.clean(a.get("APPSTATUS")),
            "project_name": alias or None,
            "scope": f"{alias} — hearing {hearing}" if hearing else (alias or None),
            "description": None,
            "contacts": [],
        })
    return out
