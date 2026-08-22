#!/usr/bin/env python3
"""
Interactive Natal search: Jan 15 – Feb 15 departures.

Phases:
  1. Coarse grid — sample every 3 days × key stay lengths
  2. Refine — ±3 days / ±3 nights around top results
  3. Fine-tune — ±1 day / ±1 night around global best
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ignav_client import search_flights  # noqa: E402

DEPARTURE_START = date(2027, 1, 15)
DEPARTURE_END = date(2027, 2, 15)
COARSE_STEP_DAYS = 3
COARSE_STAYS = [10, 14, 17, 20, 21, 24]
MIN_STAY = 7
MAX_STAY = 28
ORIGINS = ["TPA", "MCO"]
DESTINATION = "NAT"
ADULTS = 2
CHILDREN = 2


@dataclass
class Combo:
    origin: str
    departure: str
    return_date: str
    stay_days: int
    price_usd: float | None = None
    airline: str = ""
    stops: int = 0
    booking_link: str = ""

    def key(self) -> tuple[str, str, str, int]:
        return (self.origin, self.departure, self.return_date, self.stay_days)


@dataclass
class SearchState:
    searched: set[tuple[str, str, str, int]] = field(default_factory=set)
    results: list[Combo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    query_count: int = 0


def _parse(d: str) -> date:
    return date.fromisoformat(d)


def _dep_in_window(dep: date) -> bool:
    return DEPARTURE_START <= dep <= DEPARTURE_END


def _make_combo(origin: str, dep: date, stay: int) -> Combo | None:
    if stay < MIN_STAY or stay > MAX_STAY or not _dep_in_window(dep):
        return None
    return Combo(
        origin=origin,
        departure=dep.isoformat(),
        return_date=(dep + timedelta(days=stay)).isoformat(),
        stay_days=stay,
    )


def coarse_combos() -> list[Combo]:
    out: list[Combo] = []
    dep = DEPARTURE_START
    while dep <= DEPARTURE_END:
        for stay in COARSE_STAYS:
            for origin in ORIGINS:
                c = _make_combo(origin, dep, stay)
                if c:
                    out.append(c)
        dep += timedelta(days=COARSE_STEP_DAYS)
    return out


def neighbors(combo: Combo, dep_window: int, stay_window: int) -> list[Combo]:
    dep = _parse(combo.departure)
    out: list[Combo] = []
    for dd in range(-dep_window, dep_window + 1):
        for ds in range(-stay_window, stay_window + 1):
            if dd == 0 and ds == 0:
                continue
            c = _make_combo(combo.origin, dep + timedelta(days=dd), combo.stay_days + ds)
            if c:
                out.append(c)
    return out


def run_query(state: SearchState, combo: Combo, label: str) -> None:
    key = combo.key()
    if key in state.searched:
        return
    state.searched.add(key)
    state.query_count += 1
    n = state.query_count
    tag = f"{combo.origin} {combo.departure}→{combo.return_date} ({combo.stay_days}n)"
    try:
        offers = search_flights(
            origin=combo.origin,
            destination=DESTINATION,
            departure=combo.departure,
            return_date=combo.return_date,
            adults=ADULTS,
            children=CHILDREN,
            stay_days=combo.stay_days,
            max_offers=2,
        )
        if not offers:
            print(f"  [{label} #{n}] {tag}: no offers", flush=True)
            return
        best = min(offers, key=lambda o: o.total_price_usd)
        combo.price_usd = best.total_price_usd
        combo.airline = best.airline
        combo.stops = best.stops
        combo.booking_link = best.booking_link
        state.results.append(combo)
        print(f"  [{label} #{n}] {tag}: ${best.total_price_usd:,.0f}", flush=True)
    except Exception as exc:  # noqa: BLE001
        state.errors.append(f"{tag}: {exc}")
        print(f"  [{label} #{n}] {tag}: ERROR {exc}", flush=True)


def top_combos(state: SearchState, n: int) -> list[Combo]:
    priced = [c for c in state.results if c.price_usd is not None]
    priced.sort(key=lambda c: c.price_usd or 0)
    return priced[:n]


def run_phase(state: SearchState, combos: list[Combo], label: str) -> None:
    print(f"\n── {label}: {len(combos)} candidates ──", flush=True)
    for combo in combos:
        run_query(state, combo, label)


def main() -> int:
    state = SearchState()

    print(
        f"Interactive Natal search: depart {DEPARTURE_START} – {DEPARTURE_END}, "
        f"stays {MIN_STAY}–{MAX_STAY} nights, {ADULTS}A+{CHILDREN}C",
        flush=True,
    )

    # Phase 1: coarse
    run_phase(state, coarse_combos(), "COARSE")

    # Phase 2: refine around top 8
    refine_queue: list[Combo] = []
    for top in top_combos(state, 8):
        refine_queue.extend(neighbors(top, dep_window=3, stay_window=3))
    run_phase(state, refine_queue, "REFINE")

    # Phase 3: fine-tune around global best
    fine_queue: list[Combo] = []
    if state.results:
        for top in top_combos(state, 1):
            fine_queue.extend(neighbors(top, dep_window=1, stay_window=1))
    run_phase(state, fine_queue, "FINE")

    priced = top_combos(state, len(state.results))
    report = {
        "window": {
            "departure_start": DEPARTURE_START.isoformat(),
            "departure_end": DEPARTURE_END.isoformat(),
            "stay_range": [MIN_STAY, MAX_STAY],
            "passengers": f"{ADULTS} adults + {CHILDREN} children",
        },
        "queries_run": state.query_count,
        "offers_found": len(priced),
        "errors": len(state.errors),
        "best": priced[0].__dict__ if priced else None,
        "top_15": [c.__dict__ for c in priced[:15]],
        "error_samples": state.errors[:10],
    }

    print("\n" + "=" * 60)
    if priced:
        b = priced[0]
        print(f"BEST: ${b.price_usd:,.0f} — {b.origin} → NAT")
        print(f"  {b.departure} – {b.return_date} ({b.stay_days} nights)")
        print(f"  {b.airline} | {b.stops} stops")
        print(f"  {b.booking_link}")
        print(f"\nQueries: {state.query_count} | Offers: {len(priced)}")
        print("\nTop 10:")
        for c in priced[:10]:
            print(
                f"  ${c.price_usd:,.0f}  {c.origin}  "
                f"{c.departure}–{c.return_date} ({c.stay_days}n)  "
                f"{c.stops}st  {c.airline}"
            )
    else:
        print("No offers found.")

    out = Path(__file__).resolve().parent.parent.parent / "natal_interactive_results.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nJSON saved to {out.name}")
    return 0 if priced else 1


if __name__ == "__main__":
    sys.exit(main())
