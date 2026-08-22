#!/usr/bin/env python3
"""One batch: TPA/MCO → Europe (9 cities), rolling 45–270 days out."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ignav_client import search_flights  # noqa: E402

TODAY = date.today()
DAYS_AHEAD = [45, 90, 135, 180, 225]
STAY_NIGHTS = [7, 14]
ORIGINS = ["TPA", "MCO"]
DESTINATIONS = {
    "LIS": "Lisbon",
    "MAD": "Madrid",
    "CDG": "Paris",
    "FCO": "Rome",
    "LHR": "London",
    "AMS": "Amsterdam",
    "DUB": "Dublin",
    "BCN": "Barcelona",
    "FRA": "Frankfurt",
}
ADULTS = 2
CHILDREN = 2
ALERT_TARGET = 2400


def iter_queries():
    for offset in DAYS_AHEAD:
        dep = TODAY + timedelta(days=offset)
        for stay in STAY_NIGHTS:
            ret = dep + timedelta(days=stay)
            for origin in ORIGINS:
                for code, name in DESTINATIONS.items():
                    yield {
                        "origin": origin,
                        "destination": code,
                        "destination_name": name,
                        "departure": dep.isoformat(),
                        "return": ret.isoformat(),
                        "stay_days": stay,
                    }


def main() -> int:
    results: list[dict] = []
    errors: list[str] = []
    queries = list(iter_queries())
    print(
        f"Europe batch: {len(queries)} combos "
        f"({len(DESTINATIONS)} cities, {len(DAYS_AHEAD)} depart offsets, "
        f"stays {STAY_NIGHTS}, 2A+2C)",
        flush=True,
    )

    for i, q in enumerate(queries, 1):
        label = (
            f"{q['origin']}→{q['destination']} "
            f"{q['departure']}→{q['return']} ({q['stay_days']}n)"
        )
        try:
            offers = search_flights(
                origin=q["origin"],
                destination=q["destination"],
                departure=q["departure"],
                return_date=q["return"],
                adults=ADULTS,
                children=CHILDREN,
                stay_days=q["stay_days"],
                max_offers=2,
            )
            best = min(offers, key=lambda o: o.total_price_usd) if offers else None
            if best:
                row = {
                    "origin": best.origin,
                    "destination": best.destination,
                    "destination_name": q["destination_name"],
                    "departure": best.departure_date,
                    "return": best.return_date,
                    "stay_days": best.stay_days,
                    "price_usd": best.total_price_usd,
                    "airline": best.airline,
                    "stops": best.stops,
                    "booking_link": best.booking_link,
                }
                results.append(row)
            status = f"${best.total_price_usd:,.0f}" if best else "no offers"
            print(f"  [{i}/{len(queries)}] {label}: {status}", flush=True)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}: {exc}")
            print(f"  [{i}/{len(queries)}] {label}: ERROR {exc}", flush=True)

    results.sort(key=lambda r: r["price_usd"])

    by_dest: dict[str, dict] = {}
    for r in results:
        d = r["destination"]
        if d not in by_dest or r["price_usd"] < by_dest[d]["price_usd"]:
            by_dest[d] = r

    deals = [r for r in results if r["price_usd"] <= ALERT_TARGET]

    report = {
        "search": {
            "days_ahead_offsets": DAYS_AHEAD,
            "stay_nights": STAY_NIGHTS,
            "passengers": f"{ADULTS} adults + {CHILDREN} children",
            "queries_run": len(queries),
            "offers_found": len(results),
            "deals_at_or_below_target": len(deals),
            "alert_target_usd": ALERT_TARGET,
            "errors": len(errors),
        },
        "best_overall": results[0] if results else None,
        "best_by_destination": by_dest,
        "deals": deals[:20],
        "top_20": results[:20],
        "errors": errors[:15],
    }

    print("\n" + "=" * 60)
    if report["best_overall"]:
        b = report["best_overall"]
        print(f"BEST OVERALL: ${b['price_usd']:,.0f} — {b['origin']} → {b['destination_name']}")
        print(f"  {b['departure']} – {b['return']} ({b['stay_days']} nights)")
        print(f"  {b['airline']} | {b['stops']} stops")
        print(f"  {b['booking_link']}")
        if deals:
            print(f"\n🔔 {len(deals)} combos at/below ${ALERT_TARGET:,} target")
        print()
        print("Best per city:")
        for code in DESTINATIONS:
            if code in by_dest:
                r = by_dest[code]
                flag = " 🔔" if r["price_usd"] <= ALERT_TARGET else ""
                print(
                    f"  {r['destination_name']:12} ${r['price_usd']:,.0f}  "
                    f"{r['origin']}  {r['departure']}–{r['return']} ({r['stay_days']}n){flag}"
                )
        print()
        print("Top 15:")
        for r in results[:15]:
            flag = " 🔔" if r["price_usd"] <= ALERT_TARGET else ""
            print(
                f"  ${r['price_usd']:,.0f}  {r['origin']}→{r['destination_name']:10} "
                f"{r['departure']}–{r['return']} ({r['stay_days']}n)  "
                f"{r['stops']}st{flag}"
            )
    else:
        print("No offers found.")

    out = Path(__file__).resolve().parent.parent.parent / "europe_batch_results.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nJSON saved to {out.name}")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
