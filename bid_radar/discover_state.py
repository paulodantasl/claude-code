"""
DISCOVER — the four sources PLAN.md §2 steps 4 and 6 left unbuilt.

The sandbox reaches none of these hosts (PLAN.md §0), so this runs in GitHub
Actions and answers, for each, the only questions that matter before writing a
collector:

  * does the host answer a cloud runner at all?
  * what is actually downloadable — a CSV, a fixed-width text file, a PDF, a
    JSON API — and at which exact URL?
  * does the payload carry a Tampa address we can put a point on?

It asserts nothing and invents nothing. Everything it prints is a response it
received, and `bid_radar/data/vocab_state.json` records them for PLAN.md §3.

Sources probed, and why:
  1. DBPR Hotels & Restaurants public records — food-service and lodging
     licensee extracts by county. A new food-service licence at an address is
     a restaurant fitout that has already been permitted or is about to be.
  2. Sunbiz daily corporate filings — fixed-length ASCII, CCYYMMDDx.txt. A new
     LLC registered to a commercial address is the earliest public signal
     there is, 6-12 months ahead of a permit.
  3. AHCA / FloridaHealthFinder facility licensure — the medical-TI niche.
  4. HCAA planned procurement — both the monthly PDF and the OpenGov portal
     that may serve the same thing as JSON.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

import requests

TIMEOUT = 45
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
OUT: dict = {"retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def hr(t: str) -> None:
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72, flush=True)


def probe(label: str, url: str, *, method: str = "GET", want: int = 200) -> dict:
    """One request, fully reported. Never raises."""
    rec: dict = {"url": url, "method": method}
    try:
        fn = requests.head if method == "HEAD" else requests.get
        r = fn(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        rec.update(status=r.status_code,
                   content_type=r.headers.get("Content-Type", ""),
                   bytes=len(r.content) if method == "GET" else
                         int(r.headers.get("Content-Length") or 0),
                   final_url=r.url)
        print(f"  {label:<34} {r.status_code}  "
              f"{rec['content_type'][:34]:<34} {rec['bytes']:>10,}", flush=True)
        rec["_resp"] = r if r.status_code == want else None
    except Exception as exc:  # noqa: BLE001
        rec.update(status=None, error=f"{type(exc).__name__}: {exc}")
        print(f"  {label:<34} !! {type(exc).__name__}: {str(exc)[:70]}", flush=True)
        rec["_resp"] = None
    return rec


def links(html: str, base: str, pattern: str) -> list[str]:
    found, rx = [], re.compile(pattern, re.I)
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        if rx.search(href):
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = re.match(r"(https?://[^/]+)", base).group(1) + href
            elif not href.startswith("http"):
                href = base.rsplit("/", 1)[0] + "/" + href
            if href not in found:
                found.append(href)
    return found


def keep(rec: dict) -> dict:
    rec.pop("_resp", None)
    return rec


# ---------------------------------------------------------------- 1. DBPR
def dbpr() -> None:
    hr("1. DBPR Hotels & Restaurants — food service and lodging extracts")
    OUT["dbpr"] = {"pages": [], "files": []}
    for label, url in (
        ("food service page", "https://www2.myfloridalicense.com/hotels-restaurants/public-records/"),
        ("lodging page", "https://www2.myfloridalicense.com/hotels-restaurants/lodging-public-records/"),
        ("instant public records", "https://www2.myfloridalicense.com/instant-public-records/"),
        ("open government", "https://www2.myfloridalicense.com/open-government/"),
    ):
        rec = probe(label, url)
        r = rec.pop("_resp", None)
        if r is not None and "html" in rec.get("content_type", ""):
            found = links(r.text, url, r"\.(csv|zip|txt|xls[xm]?|exe)(\?|$)")
            rec["download_links"] = found[:40]
            print(f"     -> {len(found)} download links", flush=True)
            for f in found[:12]:
                print(f"        {f}", flush=True)
            OUT["dbpr"]["files"] += found
        OUT["dbpr"]["pages"].append(rec)

    # Fetch the first plausible food-service extract and describe its columns.
    for f in OUT["dbpr"]["files"][:6]:
        rec = probe("sample extract", f)
        r = rec.pop("_resp", None)
        if r is not None and rec["bytes"] > 500:
            head = r.content[:4000].decode("latin-1", "replace").splitlines()
            rec["first_lines"] = head[:4]
            print("     first lines:", flush=True)
            for line in head[:3]:
                print(f"        {line[:190]}", flush=True)
            OUT["dbpr"]["sample"] = rec
            break


# -------------------------------------------------------------- 2. Sunbiz
def sunbiz() -> None:
    hr("2. Sunbiz — daily corporate filings, fixed-length ASCII")
    OUT["sunbiz"] = {"pages": [], "candidates": []}
    for label, url in (
        ("daily-data page", "https://dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/"),
        ("data-downloads page", "https://dos.fl.gov/sunbiz/other-services/data-downloads/"),
        ("cor file definitions", "https://dos.sunbiz.org/data-definitions/cor.html"),
    ):
        rec = probe(label, url)
        r = rec.pop("_resp", None)
        if r is not None and "html" in rec.get("content_type", ""):
            found = links(r.text, url, r"\.(txt|zip)(\?|$)") + \
                    links(r.text, url, r"(sftp|ftp)\.")
            rec["links"] = found[:30]
            for f in found[:10]:
                print(f"        {f}", flush=True)
        OUT["sunbiz"]["pages"].append(rec)

    # The documented naming convention is CCYYMMDDx.txt. Try the last few
    # weekdays against the hosts that have historically served them.
    day = datetime.now(timezone.utc).date()
    names = []
    while len(names) < 4:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            names.append(day.strftime("%Y%m%d"))
    for host in ("https://sftp.floridados.gov/doc/cor/",
                 "https://dos.myflorida.com/sunbiz/data/cor/",
                 "https://search.sunbiz.org/data/cor/"):
        for name in names[:2]:
            for suffix in ("c.txt", "a.txt"):
                OUT["sunbiz"]["candidates"].append(
                    keep(probe(f"{host.split('/')[2]} {name}{suffix}", host + name + suffix,
                               method="HEAD")))


# ---------------------------------------------------------------- 3. AHCA
def ahca() -> None:
    hr("3. AHCA / FloridaHealthFinder — health-care facility licensure")
    OUT["ahca"] = {"probes": []}
    for label, url in (
        ("healthfinder root", "https://quality.healthfinder.fl.gov/"),
        ("facility locate search", "https://quality.healthfinder.fl.gov/Facility-Search/FacilityLocateSearch"),
        ("order data", "https://quality.healthfinder.fl.gov/Researchers/Order-Data/"),
        ("ahca licensee resources", "https://ahca.myflorida.com/MCHQ/Licensee_Provider_Resources.shtml"),
        ("ahca data dissemination", "https://ahca.myflorida.com/schs/datad/datad.shtml"),
    ):
        rec = probe(label, url)
        r = rec.pop("_resp", None)
        if r is not None and "html" in rec.get("content_type", ""):
            found = links(r.text, url, r"\.(csv|zip|xls[xm]?|txt)(\?|$)")
            rec["download_links"] = found[:30]
            for f in found[:10]:
                print(f"        {f}", flush=True)
            # Does the page expose a JSON/OData endpoint the search UI drives?
            api = re.findall(r'["\'](/[A-Za-z0-9_\-/]*(?:api|Search|Locate)[A-Za-z0-9_\-/]*)["\']',
                             r.text)[:12]
            if api:
                rec["api_paths"] = sorted(set(api))
                print(f"     candidate api paths: {sorted(set(api))[:8]}", flush=True)
        OUT["ahca"]["probes"].append(rec)


# ---------------------------------------------------------------- 4. HCAA
def hcaa() -> None:
    hr("4. HCAA — planned procurement, monthly PDF and the OpenGov portal")
    OUT["hcaa"] = {"pdfs": [], "portal": []}

    # The monthly report URL is predictable. Walk back six months and see which
    # ones exist, so the collector knows the real pattern rather than a guess.
    now = datetime.now(timezone.utc)
    for back in range(0, 7):
        m = (now.replace(day=1) - timedelta(days=back * 28)).replace(day=1)
        month, year = m.strftime("%B"), m.strftime("%Y")
        for folder in (m.strftime("%Y-%m"),
                       (m - timedelta(days=20)).strftime("%Y-%m")):
            url = (f"https://www.tampaairport.com/sites/default/files/{folder}/"
                   f"Planned%20Procurement%20Opportunities%20Report%20-%20"
                   f"{month}%20{year}.pdf")
            rec = keep(probe(f"{month} {year} (in {folder})", url, method="HEAD"))
            if rec.get("status") == 200:
                OUT["hcaa"]["pdfs"].append(rec)
                break

    for label, url in (
        ("procurement dept", "https://www.tampaairport.com/procurement-department"),
        ("current solicitations", "https://www.tampaairport.com/business/procurement/current-solicitation-opportunities"),
        ("opengov portal", "https://procurement.opengov.com/portal/tampaairport"),
    ):
        rec = probe(label, url)
        r = rec.pop("_resp", None)
        if r is not None and "html" in rec.get("content_type", ""):
            pdfs = links(r.text, url, r"\.pdf(\?|$)")
            rec["pdf_links"] = pdfs[:20]
            for f in pdfs[:8]:
                print(f"        {f}", flush=True)
        OUT["hcaa"]["portal"].append(rec)

    # OpenGov drives its portal from a JSON API; if it answers, it beats
    # parsing a PDF every month.
    for label, url in (
        ("opengov projects api",
         "https://procurement.opengov.com/api/public/projects?entityCode=tampaairport"),
        ("opengov portal api",
         "https://procurement.opengov.com/api/public/portal/tampaairport"),
    ):
        rec = probe(label, url)
        r = rec.pop("_resp", None)
        if r is not None and "json" in rec.get("content_type", ""):
            try:
                body = r.json()
                rec["sample_keys"] = (sorted(body.keys())[:20]
                                      if isinstance(body, dict)
                                      else f"list[{len(body)}]")
                print(f"     JSON keys: {rec['sample_keys']}", flush=True)
            except ValueError:
                pass
        OUT["hcaa"]["portal"].append(rec)


def main() -> int:
    for fn in (dbpr, sunbiz, ahca, hcaa):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"!! {fn.__name__} blew up: {type(exc).__name__}: {exc}", flush=True)
            OUT[fn.__name__] = {"error": f"{type(exc).__name__}: {exc}"}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "vocab_state.json"), "w") as fh:
        json.dump(OUT, fh, indent=2, default=str)
    hr("done — bid_radar/data/vocab_state.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
