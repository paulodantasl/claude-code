"""
City of Tampa alcoholic-beverage permits — PLAN.md §3 #3.

The only source anywhere in this system that carries a contact channel, which
is what §2.3(e) asks for and no permit row can supply. 4,096 records; business
name on 76%, owner name on 61%, a phone on 47% and an email on 22%.

Two outputs, kept apart because they answer different questions:

  * **Signals** — records that moved inside the window: a new wet-zoning
    record, a newly posted placard, or a transition to Active. About thirty a
    year citywide, so this is a slow, high-quality feed.
  * **Directory** — every Active venue inside a tracked submarket, with its
    contact details. Not a lead: a prospecting list of the bars and
    restaurants in Ybor, Water Street and downtown, which is exactly the
    relationship list a GC doing F&B fitouts wants on the desk.

Traps, all observed in the live data:
  * `AB_SLS_AREA_*_SF` is typed as a string and reads "See Ordinance" where
    the figure is not recorded.
  * `SEAT_COUNT` is populated on 23 of 4,096 rows — unusable as a gate.
  * Dates include a 2997 and a 0201; arcgis.epoch_to_date drops both.
  * `BUS_NAME` carries trailing whitespace.
  * The layer has no per-record link field, so source_url is a query that
    returns exactly the row the signal was built from.
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arcgis  # noqa: E402
import geo  # noqa: E402

SOURCE = "abt"
NAME = "Alcoholic-beverage permits"
SERVICE = "Planning/AlcoholBeverage"
LAYER = 0

# ABSALECONDITION -> trade. Consumption on premises is a buildout; package
# sales is a shelf.
def _trade(sale_condition: str | None, class_prefix: str | None) -> tuple[str, float]:
    text = f"{sale_condition or ''} {class_prefix or ''}".lower()
    if "consumption on premises" in text and "package" not in text:
        return ("restaurant", 0.8)
    if "restaurant" in text:
        return ("restaurant", 0.8)
    if "consumption on premises" in text:      # and package sales
        return ("restaurant", 0.6)
    if "package" in text:
        return ("retail", 0.7)
    if "venue" in text:
        return ("hospitality", 0.7)
    return ("other", 0.2)


def _contacts(a: dict) -> list[dict]:
    """Only what the public record states. Duplicates are collapsed."""
    seen: set[str] = set()
    out = []
    for field, kind in (("BUS_PHONE", "phone"), ("BUS_OWN_PHONE", "phone"),
                        ("BUS_OWN_EMAIL", "email")):
        value = arcgis.clean(a.get(field))
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        out.append({"kind": kind, "value": value, "from": f"AlcoholBeverage.{field}"})
    return out


def _entity(a: dict) -> str | None:
    for field in ("BUS_NAME", "BUS_OWNER_NAME2", "BUS_OWNER_NAME"):
        name = arcgis.clean(a.get(field))
        if name:
            return name
    return None


def _to_signal(a: dict, lon, lat, retrieved: str) -> dict | None:
    objectid = a.get("OBJECTID")
    key = arcgis.clean(a.get("ORD_PERMIT")) or arcgis.clean(a.get("APP_NUM")) or str(objectid)
    if not key:
        return None

    addr = arcgis.clean(a.get("PERMIT_ADDR")) or " ".join(filter(None, [
        arcgis.clean(a.get("NUM")), arcgis.clean(a.get("DIR")),
        arcgis.clean(a.get("STREET_NAME")), arcgis.clean(a.get("TYPE"))])) or ""
    addr2 = arcgis.clean(a.get("PERMIT_ADDR_2"))
    trade, confidence = _trade(arcgis.clean(a.get("ABSALECONDITION")),
                               arcgis.clean(a.get("AB_CLASS_PREFIX")))
    action = arcgis.clean(a.get("HISTORY_ACTION"))
    entity = _entity(a)

    # One ordinance can cover several addresses (2026-74 covers three storefronts
    # on E 2nd and E 4th Ave), so the dedupe key has to carry the address too.
    dedupe = f"{SOURCE}:{key}:{addr.lower()}"

    return {
        "id": "abt-" + hashlib.sha1(dedupe.encode()).hexdigest()[:16],
        "source": SOURCE,
        "source_id": key,
        "source_url": arcgis.record_url(SERVICE, LAYER, objectid),
        "retrieved_at": retrieved,

        "hood": geo.hood_of(lon, lat),
        "address": f"{addr} ({addr2})" if addr2 else addr,
        "zip": arcgis.clean(a.get("PERMIT_ZIP")),
        "lat": lat, "lon": lon,
        "city_neighborhood": None,
        "cra": None,
        "council_district": None,

        "entity": entity,
        "brand": None,
        "trade": trade,
        "confidence": confidence,
        "stage_hint": "abt",
        "record_type": " ".join(filter(None, [
            arcgis.clean(a.get("AB_CLASS_PREFIX")),
            arcgis.clean(a.get("AB_CLASS_SUFFIX"))])) or None,
        "occupancy_category": None,
        "occupancy_type": arcgis.clean(a.get("ABSALECONDITION")),
        "is_fitout": True,
        "is_dwelling": False,

        "value_est": None,
        "sqft": arcgis.number(a.get("AB_SLS_AREA_TTL_SF")),
        "sqft_indoor": arcgis.number(a.get("AB_SLS_AREA_IN_SF")),
        "seats": arcgis.number(a.get("SEAT_COUNT")),
        "occupant_load": arcgis.number(a.get("FIRE_OCC_LOAD")),
        "filed_at": (arcgis.epoch_to_date(a.get("CREATEDATE"))
                     or arcgis.epoch_to_date(a.get("ORD_LTR_DT"))),
        "issued_at": arcgis.epoch_to_date(a.get("PLACARD_DT")),
        "ab_status": action,
        "ab_status_at": arcgis.epoch_to_date(a.get("HISTORY_ACT_DT")),
        "sale_type": arcgis.clean(a.get("ABSALETYPE")),
        "owner_name": arcgis.clean(a.get("BUS_OWNER_NAME")),
        "project_name": entity,
        "scope": arcgis.clean(a.get("ABSALECONDITION")),
        "description": arcgis.clean(a.get("PMT_COMMENT")),
        "contacts": _contacts(a),
    }


def collect(days_back: int = 365) -> list[dict]:
    """Records where a NEW wet-zoning event happened inside the window.

    The distinction matters more than it looks. Three dates can move on a
    record, and only two of them mean a buildout:

      CREATEDATE   a new wet-zoning record — somebody is opening something
      PLACARD_DT   the public notice was posted — a live application
      HISTORY_ACT_DT  the status changed

    A status change alone is usually administrative. Including it put Mise en
    Place (licensed 1991), Grand Central Cafe and Mitas Cocina Moderna on the
    call list at a score of 83 — long-established restaurants whose record was
    merely touched. Those belong in the directory, not the lead list, so a
    status-only change is excluded here and picked up by `directory()`.
    """
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).date().isoformat()

    out = []
    for a, lon, lat in arcgis.iter_attrs(_all_features()):
        if arcgis.clean(a.get("HISTORY_ACTION")) == "Dry":
            continue                       # the licence was surrendered
        created = arcgis.epoch_to_date(a.get("CREATEDATE"))
        placard = arcgis.epoch_to_date(a.get("PLACARD_DT"))

        event, moved = None, None
        if created and created >= cutoff:
            event, moved = "new_record", created
        elif placard and placard >= cutoff:
            event, moved = "placard_posted", placard
        if not event:
            continue

        sig = _to_signal(a, lon, lat, retrieved)
        if sig:
            sig["abt_event"] = event
            sig["moved_at"] = moved
            # The date on the card is the event that put it here, not an
            # ordinance letter from 2014.
            sig["filed_at"] = moved
            out.append(sig)
    return out


def directory(days_back: int = 365) -> list[dict]:
    """Every Active venue inside a tracked submarket, with contact details.

    A prospecting list, not a lead list — these are open businesses, not jobs.
    """
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for a, lon, lat in arcgis.iter_attrs(_all_features()):
        if arcgis.clean(a.get("HISTORY_ACTION")) != "Active":
            continue
        if not geo.hood_of(lon, lat):
            continue
        sig = _to_signal(a, lon, lat, retrieved)
        if sig and sig["contacts"]:
            rows.append(sig)
    return rows


_CACHE: list[dict] | None = None


def _all_features() -> list[dict]:
    """One fetch serves both outputs."""
    global _CACHE
    if _CACHE is None:
        _CACHE = arcgis.fetch(SERVICE, LAYER, order_by="LASTUPDATE DESC")
    return _CACHE
