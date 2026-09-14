"""
Tampa CRA Commercial Initiative grants — PLAN.md §3 #5.

38 records, and the only source in the system that yields a real dollar figure:
`TOTALPROJECTCOST` is the project value and `FINALAWARDAMOUNT` the grant.

The lead is a grant with `STATUS = Awarded` and no completion date: money is
committed and the work has not been done. A `Completed` row is a reference
project, not an opportunity.

Traps observed in the live data:
  * `AWARDEDAMOUNT` is 0.0 on completed rows; the real figure is in
    `FINALAWARDAMOUNT`. Read both.
  * `APPLICANT` is a person ("Ted Boscaino"); `BUSINESSPROPERTYOWNER` is the
    business ("SanMarten LLC / Wine Stream"). The business is the entity.
  * `STATUS` carries a trailing space ("Awarded ").
  * MapServer, not FeatureServer, and there is no per-record link field.
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arcgis  # noqa: E402
import geo  # noqa: E402

SOURCE = "cra_grant"
NAME = "CRA commercial grants"
SERVICE = "Planning/CRACommercialInitiative"
LAYER = 0
KIND = "MapServer"

# GRANTTYPE -> what the money buys.
INTERIOR_GRANTS = {"Commercial Interior Grant", "Commercial Interior",
                   "Vanilla Shell Grant", "Commercial Special Projects Grant",
                   "Commercial Design Grant"}
EXTERIOR_GRANTS = {"Commercial Exterior Grant", "Façade Improvement Grant",
                   "Business Enhancement Micro Grant"}

_TRADE_WORDS = [
    ("medical", r"pharmac|clinic|health|wellness|dental|medical"),
    ("restaurant", r"restaurant|caf|bar\b|brewery|kitchen|bakery|food"),
    ("retail", r"retail|store|shop|salon|barber|boutique|strip center"),
    ("office", r"office"),
]


def _trade(description: str | None, occupancy: str | None) -> tuple[str, float]:
    import re
    blob = f"{description or ''} {occupancy or ''}"
    for trade, pattern in _TRADE_WORDS:
        if re.search(pattern, blob, re.I):
            return trade, 0.6
    return "other", 0.2


def collect(days_back: int = 365) -> list[dict]:
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    feats = arcgis.fetch(SERVICE, LAYER, kind=KIND)

    out = []
    for a, lon, lat in arcgis.iter_attrs(feats):
        objectid = a.get("OBJECTID")
        status = (arcgis.clean(a.get("STATUS")) or "").strip()
        completed = arcgis.epoch_to_date(a.get("COMPLETIONDATE"))
        grant_type = arcgis.clean(a.get("GRANTTYPE")) or ""
        description = arcgis.clean(a.get("DESCRIPTION"))
        trade, confidence = _trade(description, arcgis.clean(a.get("OCCUPANCY")))

        # Awarded and not finished = committed money, work outstanding.
        live = status.lower() == "awarded" and not completed

        out.append({
            "id": "cra-" + hashlib.sha1(
                f"{SOURCE}:{objectid}".encode()).hexdigest()[:16],
            "source": SOURCE,
            "source_id": f"CRA-{objectid}",
            "source_url": arcgis.record_url(SERVICE, LAYER, objectid, kind=KIND),
            "retrieved_at": retrieved,

            "hood": geo.hood_of(lon, lat),
            "address": arcgis.clean(a.get("ADDRESS")) or "",
            "zip": None,
            "lat": lat, "lon": lon,
            "city_neighborhood": arcgis.clean(a.get("NEIGHBORHOOD")),
            "cra": arcgis.clean(a.get("CRA")),
            "council_district": arcgis.clean(a.get("DISTRICT")),

            "entity": (arcgis.clean(a.get("BUSINESSPROPERTYOWNER"))
                       or arcgis.clean(a.get("APPLICANT"))),
            "applicant": arcgis.clean(a.get("APPLICANT")),
            "brand": None,
            "trade": trade,
            "confidence": confidence,
            "stage_hint": "cra_awarded" if live else "issued",
            "record_type": grant_type,
            "occupancy_category": None,
            "occupancy_type": arcgis.clean(a.get("OCCUPANCY")),
            # Every one of these is commercial construction money — interior
            # buildout, façade, full rehabilitation. The Awarded/Completed
            # stage decides whether it is a lead, not the grant type.
            "is_fitout": True,
            "work_type": ("interior" if grant_type in INTERIOR_GRANTS
                          else "exterior" if grant_type in EXTERIOR_GRANTS else None),
            "is_dwelling": False,

            # TOTALPROJECTCOST is the job; the grant is a slice of it.
            "value_est": arcgis.number(a.get("TOTALPROJECTCOST")),
            "grant_amount": (arcgis.number(a.get("FINALAWARDAMOUNT"))
                             or arcgis.number(a.get("AWARDEDAMOUNT"))),
            "private_investment": arcgis.number(a.get("PRIVATEINVESTMENT")),
            "sqft": None,
            "seats": None,
            "filed_at": arcgis.epoch_to_date(a.get("AWARDEDDATE")),
            "issued_at": completed,
            "fiscal_year": a.get("FISCALYEAR"),
            "grant_status": status,
            "project_name": grant_type or None,
            "scope": grant_type or None,
            "description": description,
            "contacts": [],
        })
    return out
