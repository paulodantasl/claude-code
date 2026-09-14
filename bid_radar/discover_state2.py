"""
DISCOVER round 2 for the state sources — the columns, not the URLs.

Round 1 (discover_state.py) established what is reachable. It found the files
that matter, which were not the ones PLAN.md guessed at:

  * newfood.csv       — NEW food-service licences, current fiscal year
  * chgownr_food.csv  — food-service CHANGE OF OWNERSHIP, which is a remodel
                        signal as reliably as a new licence is
  * newlodg.csv       — new lodging licences
  * hrfood{1..7}.csv  — the full licence list, one file per inspection district

This round answers the only remaining questions: what are the columns, which
district covers Hillsborough, and does a row carry a street address we can put
a point on. It downloads, prints headers and real Tampa rows, and records
everything in bid_radar/data/vocab_state2.json.

It also takes a second run at AHCA, whose facility data is behind a search
endpoint rather than a static file.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone

import requests

TIMEOUT = 60
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
EXTRACTS = "https://www2.myfloridalicense.com/sto/file_download/extracts/"
OUT: dict = {"retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def hr(t: str) -> None:
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72, flush=True)


def grab(url: str) -> tuple[int, bytes]:
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        return r.status_code, r.content
    except Exception as exc:  # noqa: BLE001
        print(f"  !! {type(exc).__name__}: {exc}", flush=True)
        return 0, b""


def sniff_csv(name: str, body: bytes, *, want: str = "TAMPA") -> dict:
    """Header, row count, and the first rows mentioning `want`."""
    text = body.decode("latin-1", "replace")
    # DBPR extracts have been seen both comma- and tab-delimited.
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not rows:
        return {"error": "no rows"}
    header = rows[0]
    rec = {"delimiter": delim, "columns": header, "n_columns": len(header),
           "n_rows": len(rows) - 1}
    print(f"  {name}: {len(rows)-1:,} rows x {len(header)} cols  (delim {delim!r})",
          flush=True)
    print(f"    columns: {header}", flush=True)

    hits = [r for r in rows[1:] if want.lower() in " ".join(r).lower()]
    rec["n_matching"] = len(hits)
    rec["sample"] = hits[:3]
    print(f"    rows mentioning {want}: {len(hits):,}", flush=True)
    for r in hits[:2]:
        print(f"      {r}", flush=True)

    # Which column looks like a county, and which like a street address?
    for i, col in enumerate(header):
        if re.search(r"count(y|ry)|district|dist", col, re.I):
            vals = Counter(r[i] for r in rows[1:] if len(r) > i and r[i])
            rec.setdefault("county_like", {})[col] = vals.most_common(6)
            print(f"    {col}: {vals.most_common(5)}", flush=True)
    return rec


def dbpr_columns() -> None:
    hr("DBPR — the files that actually carry new licences")
    OUT["dbpr"] = {}
    for name in ("newfood.csv", "chgownr_food.csv", "newlodg.csv",
                 "chgownr_lodg.csv"):
        status, body = grab(EXTRACTS + name)
        print(f"\n{name}  HTTP {status}  {len(body):,} bytes", flush=True)
        rec = {"url": EXTRACTS + name, "status": status, "bytes": len(body)}
        if status == 200 and body:
            rec.update(sniff_csv(name, body))
        OUT["dbpr"][name] = rec

    # Which inspection district is Hillsborough? Ask the district files.
    hr("DBPR — which district file covers Hillsborough")
    OUT["dbpr"]["districts"] = {}
    for n in range(1, 8):
        name = f"hrfood{n}.csv"
        status, body = grab(EXTRACTS + name)
        if status != 200 or not body:
            OUT["dbpr"]["districts"][name] = {"status": status}
            continue
        text = body.decode("latin-1", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        hillsborough = sum(1 for r in rows[1:] if "hillsborough" in " ".join(r).lower())
        tampa = sum(1 for r in rows[1:] if "tampa" in " ".join(r).lower())
        OUT["dbpr"]["districts"][name] = {"status": status, "rows": len(rows) - 1,
                                          "hillsborough_rows": hillsborough,
                                          "tampa_rows": tampa}
        print(f"  {name}: {len(rows)-1:>7,} rows · Hillsborough {hillsborough:>6,}"
              f" · Tampa {tampa:>6,}", flush=True)
        if tampa and "columns" not in OUT["dbpr"]:
            OUT["dbpr"]["district_columns"] = rows[0]


def ahca() -> None:
    hr("AHCA — is the facility search reachable without a browser?")
    OUT["ahca"] = {}
    base = "https://quality.healthfinder.fl.gov"
    for label, url, method, payload in (
        ("locate GET", f"{base}/Facility-Search/FacilityLocateSearch", "GET", None),
        ("locate POST county", f"{base}/Facility-Search/FacilityLocateSearch",
         "POST", {"County": "Hillsborough", "FacilityType": "0"}),
        ("proximity GET", f"{base}/Facility-Search/FacilityProximitySearch", "GET", None),
    ):
        try:
            if method == "POST":
                r = requests.post(url, data=payload, headers=UA, timeout=TIMEOUT)
            else:
                r = requests.get(url, headers=UA, timeout=TIMEOUT)
            rec = {"url": url, "method": method, "status": r.status_code,
                   "content_type": r.headers.get("Content-Type", ""),
                   "bytes": len(r.content)}
            print(f"  {label:<24} {r.status_code}  {rec['content_type'][:30]:<30} "
                  f"{rec['bytes']:>9,}", flush=True)
            # Any link to a downloadable dataset on the rendered page?
            if "html" in rec["content_type"]:
                dl = re.findall(r'href=["\']([^"\']+\.(?:xlsx|csv|zip))["\']', r.text, re.I)
                rec["download_links"] = sorted(set(dl))[:25]
                for f in rec["download_links"][:10]:
                    print(f"      {f}", flush=True)
                hills = r.text.lower().count("hillsborough")
                rec["hillsborough_mentions"] = hills
                print(f"      'hillsborough' appears {hills}x", flush=True)
            OUT["ahca"][label] = rec
        except Exception as exc:  # noqa: BLE001
            print(f"  {label:<24} !! {type(exc).__name__}: {exc}", flush=True)
            OUT["ahca"][label] = {"url": url, "error": f"{type(exc).__name__}: {exc}"}

    # The blob store behind the site serves the published datasets directly.
    hr("AHCA — the blob store the Order-Data page links to")
    for name in ("AllFacilityData_Hillsborough_08242026.xlsx",
                 "AllFacilityData_MiamiDade_08242026.xlsx"):
        url = f"{base}/files/{name}"
        status, body = grab(url)
        print(f"  {name}: HTTP {status}  {len(body):,} bytes", flush=True)
        OUT["ahca"][name] = {"url": url, "status": status, "bytes": len(body)}


def main() -> int:
    for fn in (dbpr_columns, ahca):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"!! {fn.__name__}: {type(exc).__name__}: {exc}", flush=True)
            OUT[fn.__name__] = {"error": f"{type(exc).__name__}: {exc}"}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "vocab_state2.json"), "w") as fh:
        json.dump(OUT, fh, indent=2, default=str)
    hr("done — bid_radar/data/vocab_state2.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
