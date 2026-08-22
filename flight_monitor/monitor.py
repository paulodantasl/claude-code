#!/usr/bin/env python3
"""Monitor Tampa/Orlando → Natal flight prices for 4 passengers (2A+2C)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from amadeus_client import search_flights
from date_combos import iter_date_pairs, rotate_pairs
from storage import (
    FlightOffer,
    get_all_time_best,
    init_db,
    log_run,
    save_offer,
    summary_json,
)


CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _resolve_notify_emails(alerts: dict) -> list[str]:
    env_override = os.environ.get("FLIGHT_ALERT_EMAILS", "").strip()
    if env_override:
        return [e.strip() for e in env_override.split(",") if e.strip()]
    emails = alerts.get("notify_emails")
    if emails:
        return list(emails)
    legacy = alerts.get("notify_email")
    if legacy:
        return [legacy]
    return []


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run_index_from_clock(runs_per_day: int = 3) -> int:
    """Map time-of-day to run slot 0..runs_per_day-1 (ET hours 8, 14, 20)."""
    # Use UTC hour buckets aligned with GitHub Actions cron (0, 12, 18 UTC ≈ 8pm, 8am, 2pm ET)
    hour = datetime.now(timezone.utc).hour
    if hour < 6:
        return 0
    if hour < 15:
        return 1
    return 2


def build_queries(config: dict) -> list[dict]:
    season = config["season"]
    pairs = list(
        iter_date_pairs(
            config["departure_anchors"],
            min_stay_days=season["min_stay_days"],
            preferred_stays=season.get("preferred_stays"),
            departure_start=season["departure_start"],
            departure_end=season["departure_end"],
        )
    )
    # One stay length per anchor per rotation (use min stay for batching)
    unique_pairs: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for dep, ret, stay in pairs:
        key = (dep, ret)
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append((dep, ret, stay))

    batch_size = max(1, config["search"]["max_queries_per_run"] // len(config["route"]["origins"]))
    rotated = rotate_pairs(unique_pairs, run_index_from_clock(), batch_size)

    queries = []
    for origin in config["route"]["origins"]:
        for dep, ret, stay in rotated:
            queries.append(
                {
                    "origin": origin["code"],
                    "origin_name": origin["name"],
                    "destination": config["route"]["destination"]["code"],
                    "departure": dep,
                    "return": ret,
                    "stay_days": stay,
                }
            )
    max_q = config["search"]["max_queries_per_run"]
    return queries[:max_q]


def run_monitor(dry_run: bool = False) -> dict:
    config = load_config()
    init_db()
    queries = build_queries(config)
    pax = config["passengers"]
    search_cfg = config["search"]

    all_offers: list[FlightOffer] = []
    errors: list[str] = []

    if dry_run:
        return {
            "dry_run": True,
            "queries": queries,
            "passengers": pax,
        }

    has_amadeus = bool(os.environ.get("AMADEUS_API_KEY") and os.environ.get("AMADEUS_API_SECRET"))
    if not has_amadeus:
        errors.append("AMADEUS_API_KEY/SECRET not set — no live search performed.")
        log_run(0, 0, None, notes="; ".join(errors))
        return {
            "error": "missing_credentials",
            "message": errors[0],
            "queries_planned": queries,
        }

    for q in queries:
        try:
            offers = search_flights(
                origin=q["origin"],
                destination=q["destination"],
                departure=q["departure"],
                return_date=q["return"],
                adults=pax["adults"],
                children=pax["children"],
                currency=search_cfg["currency"],
                max_offers=search_cfg["max_offers_per_query"],
                travel_class=search_cfg.get("travel_class", "ECONOMY"),
                stay_days=q["stay_days"],
            )
            for offer in offers:
                save_offer(offer)
                all_offers.append(offer)
        except Exception as exc:  # noqa: BLE001 — log and continue other queries
            errors.append(f"{q['origin']} {q['departure']}→{q['return']}: {exc}")

    best_this_run = min(all_offers, key=lambda o: o.total_price_usd) if all_offers else None
    log_run(len(queries), len(all_offers), best_this_run, notes="; ".join(errors) if errors else "ok")

    prev_best = get_all_time_best()
    alerts = config.get("alerts", {})
    notify_emails = _resolve_notify_emails(alerts)
    alert_triggered = False
    alert_reason = ""

    if best_this_run:
        target = alerts.get("target_price_usd")
        threshold = alerts.get("drop_threshold_usd", 100)
        if target and best_this_run.total_price_usd <= target:
            alert_triggered = True
            alert_reason = f"Below target ${target}"
        elif prev_best and prev_best.total_price_usd - best_this_run.total_price_usd >= threshold:
            alert_triggered = True
            alert_reason = f"Dropped ${prev_best.total_price_usd - best_this_run.total_price_usd:.0f} vs prior best"

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "queries_run": len(queries),
        "offers_found": len(all_offers),
        "best_this_run": best_this_run.__dict__ if best_this_run else None,
        "all_time_best": get_all_time_best().__dict__ if get_all_time_best() else None,
        "alert_triggered": alert_triggered,
        "alert_reason": alert_reason,
        "notify_emails": notify_emails,
        "errors": errors,
        "summary": json.loads(summary_json()),
    }


def format_report(result: dict) -> str:
    lines = [
        "✈️ Flight Monitor — Tampa/Orlando → Natal (2 adults + 2 children)",
        f"Checked: {result.get('checked_at', 'dry-run')}",
        "",
    ]
    if result.get("dry_run"):
        lines.append(f"DRY RUN — {len(result['queries'])} queries planned:")
        for q in result["queries"]:
            lines.append(
                f"  • {q['origin']} {q['departure']} → {q['return']} ({q['stay_days']} nights)"
            )
        return "\n".join(lines)

    if result.get("error"):
        lines.append(f"⚠️ {result['message']}")
        lines.append(f"Queries planned: {len(result.get('queries_planned', []))}")
        return "\n".join(lines)

    best = result.get("best_this_run")
    all_best = result.get("all_time_best")
    if best:
        lines.extend(
            [
                f"Best this run: ${best['total_price_usd']:,.2f} {best['currency']}",
                f"  {best['origin']} → {best['destination']}",
                f"  {best['departure_date']} – {best['return_date']} ({best['stay_days']} nights)",
                f"  {best['airline']} | {best['stops']} stops",
                f"  {best['booking_link']}",
                "",
            ]
        )
    else:
        lines.append("No offers found this run.")

    if all_best:
        lines.extend(
            [
                f"All-time best: ${all_best['total_price_usd']:,.2f}",
                f"  {all_best['origin']} {all_best['departure_date']} – {all_best['return_date']}",
                "",
            ]
        )

    if result.get("alert_triggered"):
        lines.append(f"🔔 ALERT: {result['alert_reason']}")

    if result.get("errors"):
        lines.append("Errors:")
        for e in result["errors"]:
            lines.append(f"  • {e}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor TPA/MCO → NAT flight prices")
    parser.add_argument("--dry-run", action="store_true", help="Show planned queries only")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = run_monitor(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))
    return 0 if not result.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
