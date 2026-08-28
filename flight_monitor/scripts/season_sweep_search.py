#!/usr/bin/env python3
"""Season sweep: TPA/MCO → NAT, Sep 2026 – Feb 2027."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ignav_client import search_flights  # noqa: E402

DEPARTURE_START = date(2026, 9, 1)
DEPARTURE_END = date(2027, 2, 15)
DEPARTURE_STEP_DAYS = 6
STAY_NIGHTS = [14, 17, 20, 21]
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
        day += timedelta(days=DEPARTURE_STEP_DAYS)


def main() -> int:
    results: list[dict] = []
    errors: list[str] = []
    queries = list(iter_queries())
    print(
        f"Season sweep: {len(queries)} combos "
        f"({DEPARTURE_START} – {DEPARTURE_END}, every {DEPARTURE_STEP_DAYS}d, "
        f"stays {STAY_NIGHTS})",
        flush=True,
    )

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
                max_offers=2,
            )
            best = min(offers, key=lambda o: o.total_price_usd) if offers else None
            if best:
                row = {
                    "origin": best.origin,
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

    by_month: dict[str, dict] = {}
    for r in results:
        month = r["departure"][:7]
        if month not in by_month or r["price_usd"] < by_month[month]["price_usd"]:
            by_month[month] = r

    by_origin: dict[str, dict] = {}
    for r in results:
        o = r["origin"]
        if o not in by_origin or r["price_usd"] < by_origin[o]["price_usd"]:
            by_origin[o] = r

    report = {
        "search": {
            "departure_window": f"{DEPARTURE_START} – {DEPARTURE_END}",
            "departure_step_days": DEPARTURE_STEP_DAYS,
            "stay_nights": STAY_NIGHTS,
            "passengers": f"{ADULTS} adults + {CHILDREN} children",
            "queries_run": len(queries),
            "offers_found": len(results),
            "errors": len(errors),
        },
        "best_overall": results[0] if results else None,
        "best_by_origin": by_origin,
        "best_by_departure_month": by_month,
        "top_20": results[:20],
        "errors": errors[:15],
    }

    print("\n" + "=" * 60)
    if report["best_overall"]:
        b = report["best_overall"]
        print(f"BEST OVERALL: ${b['price_usd']:,.0f} — {b['origin']} → NAT")
        print(f"  {b['departure']} – {b['return']} ({b['stay_days']} nights)")
        print(f"  {b['airline']} | {b['stops']} stops")
        print(f"  {b['booking_link']}")
        print()
        print("Best by origin:")
        for origin, r in sorted(by_origin.items()):
            print(
                f"  {origin}: ${r['price_usd']:,.0f}  "
                f"{r['departure']}–{r['return']} ({r['stay_days']}n)"
            )
        print()
        print("Best by departure month:")
        for month in sorted(by_month):
            r = by_month[month]
            print(
                f"  {month}: ${r['price_usd']:,.0f}  {r['origin']}  "
                f"{r['departure']}–{r['return']} ({r['stay_days']}n)"
            )
        print()
        print("Top 15:")
        for r in results[:15]:
            print(
                f"  ${r['price_usd']:,.0f}  {r['origin']}  "
                f"{r['departure']}–{r['return']} ({r['stay_days']}n)  "
                f"{r['stops']}st  {r['airline']}"
            )
    else:
        print("No offers found.")

    if errors:
        print(f"\n{len(errors)} query errors")

    out = Path(__file__).resolve().parent.parent.parent / "season_sweep_results.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nJSON saved to {out.name}")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
