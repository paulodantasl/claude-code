"""
Sunbiz daily corporate filings — PLAN.md §2 step 4.

A new LLC registered to a commercial address in one of our submarkets is the
earliest public signal that exists: six to twelve months ahead of a permit,
and often before a lease is signed. Nothing else in this system sees a tenant
that early.

STATUS: BUILT, DORMANT — waiting on credentials, not on code.

Discovery, from a GitHub runner on 2026-09-14:
  * The Division of Corporations serves the daily files from
    `https://sftp.floridados.gov`, which answers **401** to an anonymous
    request. It is a credentialed SFTP account, not an open download.
  * `dos.myflorida.com/sunbiz/data/cor/...` 404s and `search.sunbiz.org` 403s.
    There is no anonymous mirror.
  * The public pages at dos.fl.gov describe the format and link only to that
    same SFTP host.

So this collector reads `SUNBIZ_USER` and `SUNBIZ_PASS` from the environment
and returns an empty list, loudly, when they are absent. When somebody
registers for an account and adds the two secrets, it starts producing without
any further code change.

The record layout below is the published fixed-width corporate format
(dos.sunbiz.org/data-definitions/cor.html). It is documented rather than
observed — the file could not be downloaded to check it — so `LAYOUT_VERIFIED`
is False, and the first real run must confirm the offsets before the output is
trusted. `parse_line` is written so that a wrong offset produces obvious
rubbish rather than a plausible lie.
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geo  # noqa: E402

SOURCE = "sunbiz"
NAME = "Sunbiz new entities"
HOST = "https://sftp.floridados.gov"
PATH = "/doc/cor/{name}.txt"
TIMEOUT = 90

#: The published corporate fixed-width layout: (field, start, length), 0-based.
#: NOT yet confirmed against a downloaded file — see the module docstring.
LAYOUT: list[tuple[str, int, int]] = [
    ("doc_number",       0,  12),
    ("name",            12, 192),
    ("status",         204,   1),
    ("filing_type",    205,  15),
    ("addr1",          220,  42),
    ("addr2",          262,  42),
    ("city",           304,  28),
    ("state",          332,   2),
    ("zip",            334,  10),
    ("country",        344,  20),
    ("mail_addr1",     364,  42),
    ("mail_addr2",     406,  42),
    ("mail_city",      448,  28),
    ("mail_state",     476,   2),
    ("mail_zip",       478,  10),
    ("mail_country",   488,  20),
    ("file_date",      508,   8),
    ("fei_number",     516,  14),
]
LAYOUT_VERIFIED = False

#: Only the submarket ZIPs. Sunbiz is statewide; nearly all of it is noise.
TAMPA_ZIPS = {
    "33602", "33603", "33605", "33606", "33607", "33609", "33611", "33619",
    "33629",
}

#: A residential registration is not a tenant. These strings in an address are
#: the giveaway, and so is a registered-agent service address.
_AGENT_WORDS = ("registered agent", "corporate creations", "cogency",
                "incorp services", "northwest registered", "legalzoom",
                "harvard business services", "c t corporation")


def _clean(v: str) -> str:
    return " ".join(v.split()).strip()


def parse_line(line: str) -> dict | None:
    """One fixed-width record. Returns None when the line is too short to be
    one, rather than silently slicing past the end."""
    if len(line) < LAYOUT[-1][1] + LAYOUT[-1][2]:
        return None
    rec = {}
    for field, start, length in LAYOUT:
        rec[field] = _clean(line[start:start + length])
    if not rec["doc_number"] or not rec["name"]:
        return None
    return rec


def is_interesting(rec: dict) -> bool:
    """A commercial registration inside a submarket ZIP, not an agent address."""
    if (rec.get("zip") or "")[:5] not in TAMPA_ZIPS:
        return False
    blob = f"{rec.get('addr1','')} {rec.get('addr2','')} {rec.get('name','')}".lower()
    return not any(w in blob for w in _AGENT_WORDS)


def _file_names(days_back: int) -> list[str]:
    """CCYYMMDD + a one-letter suffix. Weekdays only — the Division does not
    generate a file on a day with no filings."""
    out, day = [], date.today()
    for _ in range(min(days_back, 30)):
        day -= timedelta(days=1)
        if day.weekday() < 5:
            out.append(day.strftime("%Y%m%d"))
    return out


def collect(days_back: int = 14) -> list[dict]:
    user = os.environ.get("SUNBIZ_USER")
    password = os.environ.get("SUNBIZ_PASS")
    if not (user and password):
        print("  sunbiz      SKIPPED — no SUNBIZ_USER / SUNBIZ_PASS. The daily "
              "files are behind a credentialed account at sftp.floridados.gov "
              "(401 to anonymous). Register, add the two secrets, and this "
              "starts producing with no code change.", flush=True)
        return []

    import requests
    from requests.auth import HTTPBasicAuth

    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    auth = HTTPBasicAuth(user, password)
    out: list[dict] = []

    for name in _file_names(days_back):
        for suffix in ("c", "a", ""):
            url = HOST + PATH.format(name=name + suffix)
            try:
                r = requests.get(url, auth=auth, timeout=TIMEOUT)
            except Exception as exc:  # noqa: BLE001
                print(f"    {name}{suffix}: {type(exc).__name__}", flush=True)
                continue
            if r.status_code != 200 or len(r.content) < 200:
                continue
            body = r.content.decode("latin-1", "replace")
            kept = 0
            for line in body.splitlines():
                rec = parse_line(line)
                if not rec or not is_interesting(rec):
                    continue
                kept += 1
                out.append(_signal(rec, url, retrieved))
            print(f"    {name}{suffix}: {kept} in-submarket registrations",
                  flush=True)
            break
    return out


def _signal(rec: dict, url: str, retrieved: str) -> dict:
    addr = ", ".join(p for p in (rec.get("addr1"), rec.get("addr2")) if p)
    filed = rec.get("file_date") or ""
    filed_iso = (f"{filed[:4]}-{filed[4:6]}-{filed[6:8]}"
                 if len(filed) == 8 and filed.isdigit() else None)
    return {
        "id": "sunbiz-" + hashlib.sha1(
            f"{SOURCE}:{rec['doc_number']}".encode()).hexdigest()[:16],
        "source": SOURCE,
        "source_id": rec["doc_number"],
        # Sunbiz has a stable per-entity public page.
        "source_url": ("https://search.sunbiz.org/Inquiry/CorporationSearch/"
                       f"SearchResultDetail?inquirytype=DocumentNumber"
                       f"&directionType=Initial&searchNameOrder={rec['doc_number']}"),
        "retrieved_at": retrieved,

        # No geometry in the file. Until a geocoder exists the ZIP is the only
        # locator, so the submarket is left unset rather than guessed.
        "hood": None,
        "address": addr,
        "zip": (rec.get("zip") or "")[:5],
        "lat": None, "lon": None,
        "city_neighborhood": None, "cra": None, "council_district": None,

        "entity": rec.get("name"),
        "applicant": None, "brand": None,
        "trade": "other",
        "confidence": 0.2,
        "stage_hint": "sunbiz",
        "record_type": rec.get("filing_type"),
        "occupancy_category": None, "occupancy_type": None,
        "is_fitout": False,
        "work_type": None, "is_dwelling": False,
        "value_est": None, "sqft": None, "seats": None,
        "filed_at": filed_iso,
        "issued_at": None,
        "project_name": rec.get("name"),
        "scope": f"New {rec.get('filing_type') or 'entity'} registration",
        "description": f"{rec.get('name')} — {addr} {rec.get('city','')} "
                       f"{rec.get('zip','')}".strip(),
        "contacts": [],
        "layout_verified": LAYOUT_VERIFIED,
    }
