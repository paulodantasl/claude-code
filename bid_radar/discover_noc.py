"""
DISCOVER — Hillsborough Clerk official records (PLAN.md §3 #6c).

Notices of Commencement name the contractor who won a job. They are useless
for outreach (the work is already awarded) and they are the ONLY way to measure
our real win rate and the real average fitout contract per submarket, which is
what Phase 4 needs to replace two of the five calibration dials with facts.

The Clerk has no API — VERIFIED. This establishes whether the search UI can be
driven at all, and what it would take:

  * does the page load without a session, a terms gate or a captcha?
  * what are the form controls actually named?
  * is there a document-type list, and what is the Notice of Commencement
    option called?
  * does a date-range search return results server-side, or is it a postback /
    XHR that a scraper would have to reproduce?

Prints everything and saves the rendered HTML plus a screenshot as artifacts.
Never fails the build — a dead end here is a finding, not an error.
"""
from __future__ import annotations

import json
import os
import sys
import traceback

BASE = "https://pubrec6.hillsclerk.com/ORIPublicAccess/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def hr(t: str) -> None:
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70, flush=True)


def main() -> int:
    from playwright.sync_api import sync_playwright

    report: dict = {"base": BASE}
    os.makedirs(OUT, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.set_default_timeout(45_000)

        hr(f"1. GET {BASE}")
        try:
            resp = page.goto(BASE, wait_until="domcontentloaded")
            report["status"] = resp.status if resp else None
            report["final_url"] = page.url
            print(f"  status={report['status']}", flush=True)
            print(f"  final url={page.url}", flush=True)
            print(f"  title={page.title()!r}", flush=True)
            report["title"] = page.title()
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {type(exc).__name__}: {exc}", flush=True)
            report["error"] = f"{type(exc).__name__}: {exc}"
            _save(report)
            browser.close()
            return 0

        page.wait_for_timeout(4000)

        hr("2. Gates — terms acceptance, captcha, login")
        body = page.content()
        gates = {
            "recaptcha": "recaptcha" in body.lower() or "g-recaptcha" in body.lower(),
            "hcaptcha": "hcaptcha" in body.lower(),
            "cloudflare": "cf-challenge" in body.lower() or "cf_chl" in body.lower(),
            "accept_terms": any(w in body.lower() for w in
                                ("i accept", "i agree", "terms of use", "disclaimer")),
            "login_form": page.locator("input[type=password]").count() > 0,
        }
        report["gates"] = gates
        for k, v in gates.items():
            print(f"  {k:<16} {v}", flush=True)

        hr("3. Frames")
        report["frames"] = [{"name": f.name, "url": f.url} for f in page.frames]
        for f in report["frames"]:
            print(f"  {f['name']!r} -> {f['url']}", flush=True)

        hr("4. Form controls on every frame")
        report["controls"] = []
        for frame in page.frames:
            try:
                ctrls = frame.evaluate("""() => {
                  const out = [];
                  for (const el of document.querySelectorAll('input,select,textarea,button,a[href]')) {
                    const o = {tag: el.tagName, type: el.type||null, name: el.name||null,
                               id: el.id||null,
                               label: (el.getAttribute('aria-label')||el.value||el.textContent||'').trim().slice(0,70),
                               href: el.getAttribute&&el.getAttribute('href')||null};
                    if (el.tagName === 'SELECT')
                      o.options = [...el.options].map(x => x.textContent.trim()).slice(0,120);
                    if (o.name || o.id || o.options || (o.tag === 'A' && o.href)) out.push(o);
                  }
                  return out.slice(0, 220);
                }""")
            except Exception as exc:  # noqa: BLE001
                print(f"  frame {frame.name!r}: {type(exc).__name__}", flush=True)
                continue
            if not ctrls:
                continue
            print(f"\n  --- frame {frame.name!r} ({len(ctrls)} controls) ---", flush=True)
            for c in ctrls:
                if c.get("options"):
                    print(f"    SELECT name={c['name']} id={c['id']} "
                          f"({len(c['options'])} options)", flush=True)
                    hits = [o for o in c["options"]
                            if "commence" in o.lower() or o.strip().upper() in ("NOC", "C")]
                    for o in c["options"][:40]:
                        print(f"        {o}", flush=True)
                    if hits:
                        print(f"      >>> NOTICE OF COMMENCEMENT OPTION: {hits}", flush=True)
                elif c["tag"] in ("INPUT", "TEXTAREA", "BUTTON"):
                    print(f"    {c['tag']:<8} type={c['type']} name={c['name']} "
                          f"id={c['id']} label={c['label']!r}", flush=True)
                elif c["tag"] == "A" and c.get("href") and len(c["label"]) > 2:
                    print(f"    LINK   {c['label'][:48]!r} -> {c['href'][:90]}", flush=True)
            report["controls"].append({"frame": frame.name, "controls": ctrls})

        hr("5. Does the app do postbacks or XHR?")
        report["aspnet"] = "__VIEWSTATE" in body or "__doPostBack" in body
        report["xhr_hints"] = [k for k in ("angular", "react", "vue", "kendo", "telerik",
                                           "api/", "odata", "/search")
                               if k in body.lower()]
        print(f"  ASP.NET postback markers: {report['aspnet']}", flush=True)
        print(f"  framework/API hints: {report['xhr_hints']}", flush=True)

        hr("6. Network calls the page made")
        calls = []
        page.on("request", lambda r: calls.append((r.method, r.url[:160]))
                if r.resource_type in ("xhr", "fetch", "document") else None)
        try:
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(3000)
        except Exception as exc:  # noqa: BLE001
            print(f"  reload: {type(exc).__name__}", flush=True)
        report["network"] = calls[:40]
        for m, u in calls[:40]:
            print(f"  {m:<5} {u}", flush=True)

        try:
            page.screenshot(path=os.path.join(OUT, "noc_search.png"), full_page=True)
            with open(os.path.join(OUT, "noc_search.html"), "w") as fh:
                fh.write(page.content())
            print("\n  saved noc_search.png and noc_search.html", flush=True)
        except Exception:  # noqa: BLE001
            pass

        browser.close()

    _save(report)
    return 0


def _save(report: dict) -> None:
    path = os.path.join(OUT, "vocab_noc.json")
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    hr(f"WROTE {path}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("\nDISCOVERY FAILED — recording as a finding, not an error", flush=True)
        sys.exit(0)
