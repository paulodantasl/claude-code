"""
DISCOVER — how to measure our real win rate per submarket (PLAN.md Phase 4).

The plan's route was the Hillsborough Clerk's official records: a Notice of
Commencement names the GC who won. The Clerk has no API, and the first attempt
at driving its search UI from GitHub Actions timed out after 45s with no
response at all — no page, no gate, no captcha.

So this round asks two questions instead of one:

  A. Is the Clerk reachable from a cloud runner at all, or only slow? Plain
     HTTP probes against several of its hosts, with generous timeouts.
  B. Can the SAME measurement come from a source we already have? Every permit
     the collector returns carries a per-record Accela URL, and an Accela
     record page lists the contractor of record. If it does, we can measure who
     is building fitouts in our eight submarkets without the Clerk at all.

Never fails the build. A dead end is a finding.
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback

import requests

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

CLERK_HOSTS = [
    "https://pubrec6.hillsclerk.com/ORIPublicAccess/",
    "https://pubrec.hillsclerk.com/",
    "https://www.hillsclerk.com/",
    "https://publicrec.hillsclerk.com/",
]

# A real commercial-alteration record from the live permit layer.
ACCELA_SAMPLE = ("https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx"
                 "?Module=Building&TabName=Building&capID1=26CAP&capID2=00000"
                 "&capID3=01TOI&agencyCode=TAMPA")
ACCELA_ROOT = "https://aca-prod.accela.com/TAMPA/Default.aspx"

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def hr(t: str) -> None:
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70, flush=True)


def probe(url: str, timeout: int = 90) -> dict:
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
        body = r.text or ""
        return {"url": url, "status": r.status_code, "final": r.url,
                "bytes": len(r.content), "title": _title(body),
                "captcha": any(w in body.lower() for w in
                               ("recaptcha", "hcaptcha", "cf-challenge")),
                "terms": any(w in body.lower() for w in
                             ("i accept", "i agree", "terms of use", "disclaimer"))}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


def _title(body: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    return " ".join(m.group(1).split())[:120] if m else None


def main() -> int:
    report: dict = {}
    os.makedirs(OUT, exist_ok=True)

    hr("A. Is the Hillsborough Clerk reachable from a cloud runner?")
    report["clerk"] = []
    for url in CLERK_HOSTS:
        res = probe(url)
        report["clerk"].append(res)
        if "error" in res:
            print(f"  {url}\n      !! {res['error']}", flush=True)
        else:
            print(f"  {url}\n      status={res['status']} bytes={res['bytes']} "
                  f"title={res['title']!r} captcha={res['captcha']} terms={res['terms']}",
                  flush=True)
            print(f"      final={res['final']}", flush=True)

    hr("B. Does an Accela record page name the contractor?")
    report["accela"] = {}
    for name, url in (("root", ACCELA_ROOT), ("record", ACCELA_SAMPLE)):
        res = probe(url, timeout=60)
        report["accela"][name] = res
        print(f"\n  {name}: {url[:110]}", flush=True)
        if "error" in res:
            print(f"      !! {res['error']}", flush=True)
            continue
        print(f"      status={res['status']} bytes={res['bytes']} title={res['title']!r}",
              flush=True)

    # If the record page came back, look for the contractor block.
    rec = report["accela"].get("record", {})
    if rec.get("status") == 200:
        try:
            body = requests.get(ACCELA_SAMPLE, headers=UA, timeout=60).text
            report["accela"]["has_viewstate"] = "__VIEWSTATE" in body
            markers = {}
            for label in ("Contractor", "Licensed Professional", "Applicant",
                          "Owner", "Valuation", "Job Value", "Square Feet",
                          "Contact", "License"):
                markers[label] = body.count(label)
            report["accela"]["labels"] = markers
            print("\n  labels present on the record page:", flush=True)
            for k, v in markers.items():
                print(f"      {k:<24} {v}", flush=True)
            print(f"      __VIEWSTATE present: {report['accela']['has_viewstate']}", flush=True)
            with open(os.path.join(OUT, "accela_record.html"), "w") as fh:
                fh.write(body)
            print("      saved accela_record.html", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {type(exc).__name__}: {exc}", flush=True)

    hr("VERDICT")
    clerk_ok = any(c.get("status") == 200 for c in report["clerk"])
    accela_ok = rec.get("status") == 200
    report["verdict"] = {"clerk_reachable": clerk_ok, "accela_reachable": accela_ok}
    print(f"  Clerk reachable from Actions : {clerk_ok}", flush=True)
    print(f"  Accela record page reachable : {accela_ok}", flush=True)

    path = os.path.join(OUT, "vocab_noc.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    hr(f"WROTE {path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("\nDISCOVERY FAILED — recording as a finding, not an error", flush=True)
        sys.exit(0)
