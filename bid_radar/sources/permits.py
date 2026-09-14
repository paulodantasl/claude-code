"""
City of Tampa building permits — PLAN.md §3 #1.

What this source can and cannot tell us, established by querying the layer on
2026-09-14 rather than assumed:

  * `PROJECTSTATUS` only ever reads `Issued` or `Revision`. The layer publishes
    at issuance and has no application or in-review stage, so it cannot be
    asked what is coming out to bid. `EARLY START` records are the exception:
    the city has released interior non-structural work while the main permit is
    still pending, so the rest of the scope is still being bought out.
  * There is no valuation, applicant, owner or contractor field. The tenant has
    to be parsed out of PROJECTNAME2 / PROJECTDESCRIPTION.
  * `CREATEDDATE` is intake and `LASTUPDATE` issue; the gap ran 15-66 days
    (median 35) across the 25 most recent commercial records.
  * `OCCUPANCYCATEGORY` is the filed FBC occupancy and is the best classifier
    input in the layer.
  * `URL` is a genuine per-permit Accela link.
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arcgis  # noqa: E402
import classify  # noqa: E402
import geo  # noqa: E402

SOURCE = "permit"
NAME = "Building permits"
SERVICE = "Planning/PermitsAll"
LAYER = 0


def to_signal(feat: dict, retrieved: str | None = None) -> dict | None:
    retrieved = retrieved or datetime.now(timezone.utc).isoformat(timespec="seconds")
    a = feat.get("attributes", {})
    g = feat.get("geometry") or {}
    lon, lat = g.get("x"), g.get("y")
    record_id = arcgis.clean(a.get("RECORD_ID"))
    if not record_id:
        return None

    name2 = arcgis.clean(a.get("PROJECTNAME2")) or ""
    name1 = arcgis.clean(a.get("PROJECTNAME1")) or ""
    desc = arcgis.clean(a.get("PROJECTDESCRIPTION")) or ""
    occ = arcgis.clean(a.get("OCCUPANCYCATEGORY")) or ""
    record_type = arcgis.clean(a.get("RECORDTYPE")) or ""

    trade, confidence = classify.trade_of(occ, name2, desc, record_type=record_type)
    address = arcgis.clean(a.get("ADDRESS")) or ""
    unit = arcgis.clean(a.get("UNIT"))

    return {
        "id": "permit-" + hashlib.sha1(f"permit:{record_id}".encode()).hexdigest()[:16],
        "source": SOURCE,
        "source_id": record_id,
        "source_url": arcgis.clean(a.get("URL")),
        "retrieved_at": retrieved,

        "hood": geo.hood_of(lon, lat),
        "address": f"{address} #{unit}" if unit else address,
        "zip": arcgis.clean(a.get("ZIP")),
        "lat": lat, "lon": lon,
        "city_neighborhood": arcgis.clean(a.get("NEIGHBORHOOD")),
        "cra": arcgis.clean(a.get("CRA")),
        "council_district": arcgis.clean(a.get("COUNCIL")),

        "entity": classify.entity_of(name2, desc),
        "brand": None,
        "trade": trade,
        "confidence": confidence,
        "stage_hint": classify.stage_of(a.get("PROJECTSTATUS"), name2, desc),
        "record_type": record_type,
        "occupancy_category": occ or None,
        "occupancy_type": arcgis.clean(a.get("OCCUPANCYTYPE")),
        "is_fitout": classify.is_fitout(record_type, occ),
        "is_dwelling": classify.is_dwelling(occ),

        "value_est": None,                 # field does not exist in this layer
        "sqft": a.get("NEWCONSTRUCTIONSF") or None,
        "seats": None,
        "filed_at": arcgis.epoch_to_date(a.get("CREATEDDATE")),
        "issued_at": arcgis.epoch_to_date(a.get("LASTUPDATE")),
        "project_name": name2 or name1 or None,
        "scope": classify.scope_label(name2, desc),
        "description": desc or None,
        "private_provider": arcgis.clean(a.get("PRIVATEPROVIDER")),
        "stop_work_order": arcgis.clean(a.get("STOPWORKORDER")),
        "contacts": [],                    # no contact field in this source
    }


def collect(days_back: int = 365) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    types = "','".join(sorted(classify.COMMERCIAL_RECORD_TYPES))
    where = f"CREATEDDATE >= DATE '{since}' AND RECORDTYPE IN ('{types}')"
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    feats = arcgis.fetch(SERVICE, LAYER, where=where, order_by="CREATEDDATE DESC")
    return [s for s in (to_signal(f, retrieved) for f in feats) if s]
