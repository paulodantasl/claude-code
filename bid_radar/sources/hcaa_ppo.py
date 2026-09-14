"""
HCAA Planned Procurement Opportunities — PLAN.md §2 step 6, §3 #6d.

The Hillsborough County Aviation Authority publishes, every month, a PDF
listing the contracts it intends to advertise and when. The 2026-09-03
prequalified-contractors RFP that Ideal missed was in it months ahead of the
close date. Reading this file monthly is how that stops happening.

What round-1 discovery established, from a GitHub runner on 2026-09-14:

  * The URL is predictable and stable:
      https://www.tampaairport.com/sites/default/files/{YYYY-MM}/
      Planned%20Procurement%20Opportunities%20Report%20-%20{Month}%20{Year}.pdf
    Seven consecutive months answered 200, ~180 KB each.
  * The folder segment is usually the report's own month, but not always —
    the April 2026 report was found under 2026-04 alongside another, so the
    collector tries the report month and the month before it.
  * HCAA also runs an OpenGov portal. It is NOT usable: the portal page
    returns 403 to a runner, and both `/api/public/...` endpoints return
    50,872 bytes of `text/html` — identical size, i.e. the single-page-app
    shell, not JSON. The PDF is the route.

These are `relationship` signals, not fitout leads. Nobody bids a line in a
planning report; the point is to be on the prequalified list before the
solicitation opens, so each row carries the advertise date as its bid window
and the procurement contact as its contact.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SOURCE = "hcaa_ppo"
NAME = "HCAA planned procurement"
BASE = "https://www.tampaairport.com/sites/default/files"
REPORT = "Planned%20Procurement%20Opportunities%20Report%20-%20{month}%20{year}.pdf"
TIMEOUT = 60
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# The airport is inside the Airport / Westshore polygon, and every one of these
# contracts is let there. There is no per-row address in the report, so the
# submarket is the airport itself rather than a geocode we cannot do.
HOOD = "airport"
AIRPORT_LON, AIRPORT_LAT = -82.5332, 27.9755

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
# "4/20/2026", "04-20-26", "April 2026", "Q3 2026"
DATE_US = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")

# What Ideal can actually do. A janitorial or IT contract is noise.
BUILD_WORDS = re.compile(
    r"construct|constructi|building|renovat|remodel|refurbish|fit.?out|"
    r"tenant\s+improve|prequalif|pre.?qualif|contractor|general\s+trades|"
    r"site\s*work|paving|roof|hvac|mechanical|electrical|plumbing|"
    r"concourse|terminal|hangar|facilit", re.I)
# Careful with this list: every row in the report carries an "Advertise
# <date>" label, so a bare `advertis` here silently drops the entire file.
# Each entry must match the *subject* of a contract, not a column heading.
SKIP_WORDS = re.compile(
    r"janitorial|custodial|staffing|temporary\s+labor|insurance\s+broker|"
    r"advertising\s+(?:services|agency|program)|concession|food\s+and\s+beverage\s+lease|"
    r"software|license\s+renewal|legal\s+services|financial\s+audit", re.I)


def _month_candidates(months_back: int) -> list[tuple[str, str, str]]:
    """(folder, Month, Year) newest first, trying the report month and the one
    before it — discovery saw both used."""
    out, seen = [], set()
    first = date.today().replace(day=1)
    for i in range(months_back + 1):
        m = first
        for _ in range(i):
            m = (m - timedelta(days=1)).replace(day=1)
        month, year = m.strftime("%B"), m.strftime("%Y")
        prev = (m - timedelta(days=1)).replace(day=1)
        for folder in (m.strftime("%Y-%m"), prev.strftime("%Y-%m")):
            key = (folder, month, year)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def fetch_report(months_back: int = 2) -> list[tuple[str, str, bytes]]:
    """Returns [(report_label, url, pdf_bytes)] for the months that answered."""
    got, have = [], set()
    for folder, month, year in _month_candidates(months_back):
        label = f"{month} {year}"
        if label in have:
            continue
        url = f"{BASE}/{folder}/" + REPORT.format(month=month, year=year)
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            print(f"    {label}: {type(exc).__name__}", flush=True)
            continue
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            have.add(label)
            got.append((label, url, r.content))
            print(f"    {label}: {len(r.content):,} bytes", flush=True)
    return got


def pdf_text(body: bytes) -> str:
    """pypdf if it is installed, otherwise nothing — never a guess."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            print("    !! no pypdf installed; cannot read the report", flush=True)
            return ""
    import io
    try:
        reader = PdfReader(io.BytesIO(body))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        print(f"    !! pdf parse failed: {type(exc).__name__}: {exc}", flush=True)
        return ""


def _iso(m: re.Match) -> str | None:
    mm, dd, yy = (int(g) for g in m.groups())
    if yy < 100:
        yy += 2000
    try:
        return date(yy, mm, dd).isoformat()
    except ValueError:
        return None


def parse_rows(text: str) -> list[dict]:
    """One row per procurement line the report names.

    The report is a table flattened by text extraction, so rows are recovered
    by blank-line blocks rather than by column position — the same reasoning
    as accela.py: the printed content is stable, the layout is not.
    """
    rows, block = [], []
    for line in text.splitlines():
        line = line.strip()
        if line:
            block.append(line)
            continue
        if block:
            rows.append(block)
            block = []
    if block:
        rows.append(block)

    out = []
    for block in rows:
        blob = " ".join(block)
        if len(blob) < 25:
            continue
        if SKIP_WORDS.search(blob) or not BUILD_WORDS.search(blob):
            continue
        dates = [d for d in (_iso(m) for m in DATE_US.finditer(blob)) if d]
        emails = EMAIL.findall(blob)
        money = MONEY.findall(blob)
        # The title is the first line long enough to be one.
        title = next((l for l in block if len(l) > 12), blob[:120])
        out.append({
            "title": title[:180],
            "blob": blob[:600],
            "dates": sorted(set(dates)),
            "emails": sorted(set(emails)),
            "value_est": _money(money),
        })
    return out


def _money(found: list[str]) -> float | None:
    vals = []
    for raw in found:
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        if 10_000 <= v <= 500_000_000:
            vals.append(v)
    return max(vals) if vals else None


def collect(days_back: int = 365) -> list[dict]:
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    months_back = max(1, min(6, round(days_back / 30)))
    out = []
    for label, url, body in fetch_report(months_back):
        text = pdf_text(body)
        if not text.strip():
            continue
        for row in parse_rows(text):
            upcoming = [d for d in row["dates"] if d >= date.today().isoformat()]
            contacts = [{"kind": "email", "value": e} for e in row["emails"]]
            out.append({
                "id": "hcaa-" + hashlib.sha1(
                    f"{SOURCE}:{row['title']}".encode()).hexdigest()[:16],
                "source": SOURCE,
                "source_id": f"HCAA-{label.replace(' ', '')}-"
                             f"{hashlib.sha1(row['title'].encode()).hexdigest()[:8]}",
                "source_url": url,
                "retrieved_at": retrieved,

                "hood": HOOD,
                "address": "Tampa International Airport",
                "zip": None,
                "lat": AIRPORT_LAT, "lon": AIRPORT_LON,
                "city_neighborhood": None, "cra": None, "council_district": None,

                "entity": "Hillsborough County Aviation Authority",
                "applicant": None,
                "brand": None,
                # Not a fitout to bid — a door to be standing inside before the
                # solicitation opens.
                "trade": "relationship",
                "confidence": 0.5,
                "stage_hint": "pre_permit",
                "record_type": "Planned procurement",
                "occupancy_category": None, "occupancy_type": None,
                "is_fitout": True,
                "work_type": None,
                "is_dwelling": False,

                "value_est": row["value_est"],
                "sqft": None, "seats": None,
                # The earliest date in the row is the advertise date; that is
                # the deadline that matters, not the award.
                "filed_at": (row["dates"][0] if row["dates"] else None),
                "issued_at": None,
                "advertise_dates": row["dates"],
                "next_date": (upcoming[0] if upcoming else None),
                "report_month": label,
                "project_name": row["title"],
                "scope": row["title"],
                "description": row["blob"],
                "contacts": contacts,
            })
    return out


def dump_text(path: str, months_back: int = 1) -> int:
    """Save the newest report's extracted text so a test fixture can be built
    from the real document rather than an imagined one. Actions only — the
    sandbox cannot reach tampaairport.com."""
    got = fetch_report(months_back)
    if not got:
        print("    no report fetched", flush=True)
        return 1
    label, url, body = got[0]
    text = pdf_text(body)
    if not text.strip():
        return 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(f"# {label}\n# {url}\n\n{text}")
    print(f"    wrote {len(text):,} chars of {label} to {path}", flush=True)
    return 0


if __name__ == "__main__":
    if os.environ.get("HCAA_DUMP"):
        raise SystemExit(dump_text(os.environ["HCAA_DUMP"]))
    rows = collect()
    print(f"\n{len(rows)} rows")
    for r in rows[:20]:
        print(f"  {r['next_date'] or '—':<12} {r['project_name'][:74]}")
        if r["contacts"]:
            print(f"               {[c['value'] for c in r['contacts']]}")
