#!/usr/bin/env python3
"""One-off search: TPA/MCO → NAT, 2nd week of Jan ±3 days, ~20-night stay ±3."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Allow imports from flight_monitor package root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ignav_client import search_flights  # noqa: E402

# Second week of January 2027 (Jan 8–14) ±3 days → Jan 5–17 departures
DEPARTURE_START = date(2027, 1, 5)
DEPARTURE_END = date(2027, 1, 17)
# ~20 nights ±3 (search endpoints + target)
STAY_NIGHTS = [17, 20, 23]
ORIGINS = ["TPA", "MCO"]
DESTINATION = "NAT"
ADULTS = 2
CHILDREN = 2


def iter_queries():
    day = DEPARTURE_START
    while day <= DEPARTURE_END:
        for stay in STAY_NIGHTS:
            ret = day + timedelta(days=stay)
            for origin in ORIGINS:
                yield {
                    "origin": origin,
                    "destination": DESTINATION,
                    "departure": day.isoformat(),
                    "return": ret.isoformat(),
                    "stay_days": stay,
                }
        day += timedelta(days=1)


def main() -> int:
    results: list[dict] = []
    errors: list[str] = []
    queries = list(iter_queries())
    print(f"Searching {len(queries)} date combos (Jan 5–17 depart, 17–23 night stays)...", flush=True)

    for i, q in enumerate(queries, 1):
        label = f"{q['origin']} {q['departure']}→{q['return']} ({q['stay_days']}n)"
        try:
            offers = search_flights(
                origin=q["origin"],
                destination=q["destination"],
                departure=q["departure"],
                return_date=q["return"],
                adults=ADULTS,
                children=CHILDREN,
                stay_days=q["stay_days"],
                max_offers=3,
            )
            for offer in offers:
                results.append(
                    {
                        "origin": offer.origin,
                        "departure": offer.departure_date,
                        "return": offer.return_date,
                        "stay_days": offer.stay_days,
                        "price_usd": offer.total_price_usd,
                        "airline": offer.airline,
                        "stops": offer.stops,
                        "booking_link": offer.booking_link,
                    }
                )
            best = min(offers, key=lambda o: o.total_price_usd) if offers else None
            status = f"${best.total_price_usd:,.0f}" if best else "no offers"
            print(f"  [{i}/{len(queries)}] {label}: {status}", flush=True)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}: {exc}")
            print(f"  [{i}/{len(queries)}] {label}: ERROR {exc}", flush=True)

    results.sort(key=lambda r: r["price_usd"])
    top = results[:15]

    report = {
        "search": {
            "departure_window": f"{DEPARTURE_START} – {DEPARTURE_END}",
            "stay_nights": STAY_NIGHTS,
            "passengers": f"{ADULTS} adults + {CHILDREN} children",
            "queries_run": len(queries),
            "offers_found": len(results),
            "errors": len(errors),
        },
        "best": results[0] if results else None,
        "top_15": top,
        "errors": errors[:10],
    }

    print("\n" + "=" * 60)
    if report["best"]:
        b = report["best"]
        print(f"BEST: ${b['price_usd']:,.0f} — {b['origin']} → NAT")
        print(f"  {b['departure']} – {b['return']} ({b['stay_days']} nights)")
        print(f"  {b['airline']} | {b['stops']} stops")
        print(f"  {b['booking_link']}")
        print()
        print("Top 10:")
        for r in top[:10]:
            print(
                f"  ${r['price_usd']:,.0f}  {r['origin']}  "
                f"{r['departure']}–{r['return']} ({r['stay_days']}n)  "
                f"{r['stops']}st  {r['airline']}"
            )
    else:
        print("No offers found.")
    if errors:
        print(f"\n{len(errors)} query errors (showing first 5):")
        for e in errors[:5]:
            print(f"  • {e}")

    out = Path(__file__).resolve().parent.parent.parent / "jan_week2_results.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nJSON saved to {out.name}")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
