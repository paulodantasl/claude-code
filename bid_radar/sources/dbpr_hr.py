"""
DBPR Hotels & Restaurants — new licences and changes of ownership.
PLAN.md §2 step 4.

A new food-service licence at an address means a restaurant is opening there.
A change of ownership means one is being taken over, which in this trade almost
always means a remodel. Both are fitout signals, and both are public.

The files, confirmed from a GitHub runner on 2026-09-14:

  newfood.csv       1,274 rows   new food-service licences, current FY
  chgownr_food.csv  1,141 rows   food-service change of ownership
  newlodg.csv       2,356 rows   new lodging licences
  chgownr_lodg.csv    290 rows   lodging change of ownership

all under https://www2.myfloridalicense.com/sto/file_download/extracts/

TRAPS, every one of them seen in the real files rather than imagined:

1. **The column order is NOT the same across files.** Every file ships the same
   38-name header, but in `newfood.csv` the phone is at index 15 and the county
   code at 16, while in `chgownr_food.csv` they are the other way round — a row
   there reads `Primary Phone Number = "39"` and `Mailing County Code =
   "8134886294"`. Mapping by header name alone gets the phone wrong in one file
   out of two, so `_row` validates what it reads and repairs the swap.

2. **`newlodg.csv` has a different header entirely** — 34 columns, with no
   `Location County` at all. There is no single schema; each file is read
   against its own header.

3. **A Tampa MAILING address is not a Tampa location.** The first row of
   newfood.csv is `BLUSH SOCIAL`, mailing address Tampa 33647, location
   `101 PHILIPPE PKWY, SAFETY HARBOR` — Pinellas county. Filtering on a
   blanket text match for "Tampa" would have imported it as a Tampa lead.
   Only `Location …` fields decide where the work is.

4. **No coordinates.** These files carry a street address and nothing else, so
   the submarket comes from the geocoder when one is configured. Without it
   `hood` is None and the row is honest about not knowing, rather than being
   dropped into a submarket by ZIP — 33602 alone spans Downtown, the
   Riverwalk, Water Street and the Channel District.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geo  # noqa: E402

SOURCE = "dbpr_hr"
NAME = "DBPR food service and lodging"
EXTRACTS = "https://www2.myfloridalicense.com/sto/file_download/extracts/"
TIMEOUT = 90
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

#: file -> (what it means, the trade it implies, the stage it implies)
FILES = {
    "newfood.csv":      ("New food-service licence", "restaurant", "dbpr_hr"),
    "chgownr_food.csv": ("Food-service change of ownership", "restaurant", "dbpr_hr"),
    "newlodg.csv":      ("New lodging licence", "hospitality", "dbpr_hr"),
    "chgownr_lodg.csv": ("Lodging change of ownership", "hospitality", "dbpr_hr"),
}

COUNTY = "hillsborough"
CITIES = {"tampa"}

_PHONE = re.compile(r"^\D*(\d{3})\D*(\d{3})\D*(\d{4})\D*$")
_ZIP = re.compile(r"^\d{5}(-\d{4})?$")
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

#: A single-family dwelling rented out is not a commercial fitout. The lodging
#: files are full of them — `Rank Code` DWEL with modifier SNGL.
_DWELLING_RANKS = {"DWEL"}

#: Licence classes that are not a buildout at all, and which the first live run
#: put straight onto the call list — 9 of 23 qualified rows:
#:   MFDV  mobile food dispensing vehicle — a food truck
#:   VEND  vending machine operator
#: Five of the MFDV rows shared one address, 4601 N Lois Ave, which is a
#: commissary where trucks register. That is one kitchen, not five fitouts.
_NOT_A_BUILDOUT = {"MFDV", "VEND", "THEA", "CATE"}


def _clean(v) -> str:
    return " ".join(str(v or "").split()).strip()


def _is_phone(v: str) -> bool:
    return bool(_PHONE.match(_clean(v)))


def _fmt_phone(v: str) -> str | None:
    m = _PHONE.match(_clean(v))
    return f"({m.group(1)}) {m.group(2)}-{m.group(3)}" if m else None


def _iso(v: str) -> str | None:
    m = _DATE.match(_clean(v))
    if not m:
        return None
    mm, dd, yy = (int(g) for g in m.groups())
    try:
        return date(yy, mm, dd).isoformat()
    except ValueError:
        return None


def _row(header: list[str], values: list[str]) -> dict:
    """Map one row by header NAME, then repair the phone/county-code swap.

    Trap 1: the same header ships with two different column orders. Rather
    than trust either, the two suspect fields are checked against what they
    should look like and exchanged when they are clearly the wrong way round.
    """
    rec = {h.strip(): _clean(v) for h, v in zip(header, values)}
    phone_key = "Primary Phone Number"
    county_key = "Mailing County Code"
    phone, county = rec.get(phone_key, ""), rec.get(county_key, "")
    # A county code is 1-2 digits; a phone is 10. If they are swapped, the
    # "phone" is short and the "county code" is long.
    if phone and county and not _is_phone(phone) and _is_phone(county):
        rec[phone_key], rec[county_key] = county, phone
        rec["_swapped_phone_county"] = True
    return rec


def _in_tampa(rec: dict) -> bool:
    """Trap 3: only the Location fields decide. A Tampa mailing address on a
    Safety Harbor restaurant is not our lead."""
    county = (rec.get("Location County") or "").lower()
    city = (rec.get("Location City") or "").lower()
    if county:
        return county == COUNTY
    # newlodg.csv has no Location County (trap 2); fall back to the city.
    return city in CITIES


def fetch(name: str) -> list[dict]:
    url = EXTRACTS + name
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        print(f"    {name}: {type(exc).__name__}: {exc}", flush=True)
        return []
    if r.status_code != 200 or len(r.content) < 500:
        print(f"    {name}: HTTP {r.status_code}", flush=True)
        return []
    rows = list(csv.reader(io.StringIO(r.content.decode("latin-1", "replace"))))
    if len(rows) < 2:
        return []
    header = rows[0]
    return [_row(header, v) for v in rows[1:] if any(v)]


def collect(days_back: int = 365, *, geocode=None) -> list[dict]:
    """`geocode` is an optional callable (street, city, state, zip) ->
    (lon, lat) | None. Without it every row is emitted with hood=None."""
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    out, swapped = [], 0

    for name, (label, trade, stage) in FILES.items():
        rows = fetch(name)
        kept = 0
        for rec in rows:
            if rec.get("_swapped_phone_county"):
                swapped += 1
            if not _in_tampa(rec):
                continue
            approved = _iso(rec.get("Application Approval Date") or
                            rec.get("Application Approval Date ") or "")
            if approved and approved < cutoff:
                continue
            kept += 1
            out.append(_signal(rec, name, label, trade, stage, approved,
                               retrieved, geocode))
        print(f"    {name:<18} {len(rows):>6,} rows -> {kept:>4} in Hillsborough",
              flush=True)
    if swapped:
        print(f"    repaired {swapped} rows whose phone and county code were "
              f"swapped against the header", flush=True)
    return out


def _signal(rec: dict, fname: str, label: str, trade: str, stage: str,
            approved: str | None, retrieved: str, geocode) -> dict:
    street = rec.get("Location Street Address") or ""
    city = rec.get("Location City") or ""
    state = rec.get("Location State Code") or "FL"
    zipc = (rec.get("Location Zip Code") or "")[:5]
    licence = rec.get("License Number") or ""

    lon = lat = None
    if geocode and street:
        try:
            got = geocode(street, city, state, zipc)
            if got:
                lon, lat = got
        except Exception:  # noqa: BLE001
            lon = lat = None

    contacts = []
    for key in ("Primary Phone Number", "Secondary Phone Number"):
        p = _fmt_phone(rec.get(key) or "")
        if p and not any(c["value"] == p for c in contacts):
            contacts.append({"kind": "phone", "value": p})

    seats = rec.get("Number of Seats") or ""
    units = rec.get("Number of Rental Units") or ""
    rank = (rec.get("Rank Code") or "").upper()

    return {
        "id": "dbpr-" + hashlib.sha1(
            f"{SOURCE}:{licence or rec.get('Application Number')}".encode()
        ).hexdigest()[:16],
        "source": SOURCE,
        "source_id": licence or rec.get("Application Number") or "",
        # DBPR has no per-record permalink; the extract itself is the source.
        "source_url": EXTRACTS + fname,
        "retrieved_at": retrieved,

        "hood": geo.hood_of(lon, lat) if (lon and lat) else None,
        "address": ", ".join(p for p in (street, city) if p),
        "zip": zipc or None,
        "lat": lat, "lon": lon,
        "city_neighborhood": None, "cra": None,
        "council_district": rec.get("District") or None,

        # Business Name is the trading name ("HAVELI INDIAN KITCHEN");
        # Licensee Name is the holding company ("JAI BUA RANI LLC").
        "entity": rec.get("Business Name") or rec.get("Licensee Name") or None,
        "applicant": rec.get("Licensee Name") or None,
        "brand": rec.get("Business Name") or None,
        "trade": trade,
        "confidence": 0.75,
        "stage_hint": stage,
        "record_type": label,
        "occupancy_category": None,
        "occupancy_type": rec.get("Rank Code") or None,
        "is_fitout": rank not in _DWELLING_RANKS | _NOT_A_BUILDOUT,
        "work_type": "interior",
        "is_dwelling": rank in _DWELLING_RANKS,

        "value_est": None,
        "sqft": None,
        # Seats is the build-size proxy PLAN wanted and the ABT layer could
        # not give — it is filled on these rows, not on 23 of 4,096.
        "seats": int(seats) if seats.isdigit() else None,
        "rental_units": int(units) if units.isdigit() else None,
        "filed_at": approved,
        "issued_at": approved,
        "licence_number": licence or None,
        "licence_expiry": _iso(rec.get("License Expiry Date") or ""),
        "project_name": rec.get("Business Name") or None,
        "scope": label,
        "description": f"{label}: {rec.get('Business Name') or ''} "
                       f"({rec.get('Licensee Name') or ''}) at {street}, {city}"
                       .strip(),
        "contacts": contacts,
        "needs_geocode": lon is None,
    }
