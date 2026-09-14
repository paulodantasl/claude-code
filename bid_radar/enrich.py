"""
Enrich permit signals from their own Accela record pages.

Every permit signal already carries a per-record Accela URL. That page holds
the GC of record, the applicant with a phone and an email, the owner, the job
valuation and the real square footage — none of which exist in the ArcGIS
layer. Fetching it turns a permit row from "something happened at this address"
into a lead with a name and a number, and gives us the contractor-of-record
data the Hillsborough Clerk would have provided if its public-records hosts
answered cloud traffic at all (they do not — PLAN.md §3 #6c).

Cost control, because these are 370 KB pages:
  * only signals inside a tracked submarket are enriched
  * results are cached by record id in data/accela_cache.json, committed to the
    data branch, so a second run fetches only what is new
  * MAX_FETCH caps a single run
  * a failed fetch is skipped, never fatal, and never cached as a negative
  * the cache is written every SAVE_EVERY fetches, so a run cancelled mid-flight
    (a new push cancels the workflow) keeps the pages it already paid for
  * BUDGET_S caps the wall clock. Accela is not always fast: the same 223 pages
    that took ten minutes on 2026-09-14 02:22Z were still going at thirty-seven
    on the 02:42Z run. Enrichment is one step of a pipeline, and it must not be
    allowed to hold the rest of it hostage — it stops fetching at the budget and
    the run continues with what is cached.
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone

import requests

import accela

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "accela_cache.json")
MAX_FETCH = int(os.environ.get("ACCELA_MAX_FETCH", "160"))
PAUSE = float(os.environ.get("ACCELA_PAUSE", "0.7"))
SAVE_EVERY = int(os.environ.get("ACCELA_SAVE_EVERY", "20"))
BUDGET_S = float(os.environ.get("ACCELA_BUDGET_S", "600"))
TIMEOUT = 45
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def load_cache() -> dict:
    try:
        with open(CACHE_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as fh:
        json.dump(cache, fh, separators=(",", ":"), default=str)


def fetch_one(url: str) -> dict | None:
    resp = requests.get(url, headers=UA, timeout=TIMEOUT)
    if resp.status_code != 200 or len(resp.content) < 20_000:
        return None
    return accela.parse(resp.text)


def enrich(signals: list[dict], *, only_tracked: bool = True) -> dict:
    """Merges Accela detail into permit signals in place. Returns a report."""
    cache = load_cache()
    stats = {"eligible": 0, "cached": 0, "fetched": 0, "failed": 0, "enriched": 0}

    todo = [s for s in signals
            if s.get("source") == "permit" and s.get("source_url")
            and (s.get("hood") or not only_tracked)]
    stats["eligible"] = len(todo)
    budget = MAX_FETCH
    deadline = time.monotonic() + BUDGET_S

    for sig in todo:
        key = sig["source_id"]
        parsed = cache.get(key)
        if parsed is not None:
            stats["cached"] += 1
        elif budget <= 0 or time.monotonic() > deadline:
            stats["skipped"] = stats.get("skipped", 0) + 1
            continue
        else:
            budget -= 1
            try:
                parsed = fetch_one(sig["source_url"])
            except Exception as exc:  # noqa: BLE001
                print(f"    {key}: {type(exc).__name__}", flush=True)
                parsed = None
            if parsed is None:
                stats["failed"] += 1
                continue
            cache[key] = parsed
            stats["fetched"] += 1
            if stats["fetched"] % SAVE_EVERY == 0:
                save_cache(cache)
            time.sleep(PAUSE + random.random() * 0.4)

        _merge(sig, parsed)
        stats["enriched"] += 1

    if stats.get("skipped"):
        print(f"    {stats['skipped']} left for the next run "
              f"(fetch cap {MAX_FETCH}, budget {BUDGET_S:.0f}s)", flush=True)
    cache["_meta"] = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "records": len([k for k in cache if not k.startswith("_")])}
    save_cache(cache)
    return stats


def _merge(sig: dict, parsed: dict) -> None:
    """Accela is more authoritative than the ArcGIS layer on every field it has,
    because the ArcGIS layer simply does not carry them."""
    if parsed.get("job_value"):
        sig["value_est"] = parsed["job_value"]
        # Kept, but flagged: a fitout permit valued at $280,000,000 or $500 is
        # a data-entry error on the record, and it must not move an average.
        if parsed.get("value_suspect"):
            sig["value_suspect"] = True
    if parsed.get("sqft"):
        sig["sqft"] = parsed["sqft"]

    contacts = accela.contacts_from(parsed)
    if contacts:
        have = {c["value"].lower() for c in sig.get("contacts") or []}
        sig["contacts"] = (sig.get("contacts") or []) + [
            c for c in contacts if c["value"].lower() not in have]

    gc = parsed.get("contractor") or {}
    if gc.get("company") or gc.get("name"):
        sig["contractor_name"] = gc.get("company") or gc.get("name")
        sig["contractor_licence"] = gc.get("licence")
    applicant = parsed.get("applicant") or {}
    if applicant.get("name"):
        sig["applicant_name"] = applicant["name"]
    if parsed.get("owner"):
        sig["owner_name"] = parsed["owner"]
    if parsed.get("tenant_contact"):
        sig["tenant_contact"] = parsed["tenant_contact"]
    if parsed.get("subs"):
        sig["subs"] = parsed["subs"]

    # The entity is the tenant. Accela's applicant is often the permit
    # expediter, so it only fills a gap — it never overwrites a name the
    # project description already gave us.
    if not sig.get("entity") and applicant.get("name"):
        sig["entity"] = applicant["name"]
    sig["enriched"] = "accela"
