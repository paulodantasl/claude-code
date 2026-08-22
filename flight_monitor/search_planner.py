"""Adaptive query planner — explore the date window for the cheapest combo."""

from __future__ import annotations

from date_combos import coarse_pairs, refine_pairs, rotate_pairs


def plan_queries(
    config: dict,
    searched: set[tuple[str, str, str, str]],
    best_offer: dict | None,
    run_index: int,
    explore: bool = False,
) -> tuple[list[dict], dict]:
    """
    Build prioritized API queries for this run.

    searched keys: (origin, destination, departure, return)
    """
    season = config["season"]
    search = config["search"]
    origins = config["route"]["origins"]
    destinations = config["route"]["destinations"]

    dep_start = season["departure_start"]
    latest_return = season["latest_return"]
    min_stay = season.get("min_stay_days", 7)
    dep_step = search.get("departure_step_days", 4)
    stay_lengths = search.get("stay_lengths")
    refine_window = search.get("refine_window_days", 3)
    max_queries = search.get("max_queries_per_run", 12)
    if explore:
        max_queries = search.get("max_queries_explore", 24)

    slots = max(1, len(origins) * len(destinations))
    pairs_budget = max(1, max_queries // slots)

    coarse = coarse_pairs(
        dep_start,
        latest_return,
        min_stay_days=min_stay,
        departure_step_days=dep_step,
        stay_lengths=stay_lengths,
    )

    # Rotate which destinations get priority this run
    dest_order = list(destinations)
    if dest_order:
        shift = run_index % len(dest_order)
        dest_order = dest_order[shift:] + dest_order[:shift]

    candidates: list[tuple[str, str, str, str, int, int]] = []
    # origin, dest_code, dest_name, dep, ret, stay, priority

    def add(
        origin_code: str,
        origin_name: str,
        dest_code: str,
        dest_name: str,
        dep: str,
        ret: str,
        stay: int,
        priority: int,
    ) -> None:
        key = (origin_code, dest_code, dep, ret)
        if key in searched and not explore:
            return
        candidates.append((origin_code, origin_name, dest_code, dest_name, dep, ret, stay, priority))

    # 1) Refine around best known offer (same destination if possible)
    if best_offer and best_offer.get("departure_date"):
        refine = refine_pairs(
            best_offer["departure_date"],
            best_offer["return_date"],
            dep_start,
            latest_return,
            min_stay_days=min_stay,
            window_days=refine_window,
            stay_lengths=stay_lengths,
        )
        best_dest = best_offer.get("destination")
        for origin in origins:
            for dest in dest_order:
                if best_dest and dest["code"] != best_dest:
                    continue
                for dep, ret, stay in refine:
                    add(
                        origin["code"],
                        origin["name"],
                        dest["code"],
                        dest["name"],
                        dep,
                        ret,
                        stay,
                        0,
                    )

    # 2) Unsearched coarse combos
    for dep, ret, stay in coarse:
        for origin in origins:
            for dest in dest_order:
                key = (origin["code"], dest["code"], dep, ret)
                if key not in searched:
                    add(
                        origin["code"],
                        origin["name"],
                        dest["code"],
                        dest["name"],
                        dep,
                        ret,
                        stay,
                        1,
                    )

    # 3) Rotating coarse coverage — cycle destinations
    rotated_pairs = rotate_pairs(coarse, run_index, pairs_budget)
    for i, (dep, ret, stay) in enumerate(rotated_pairs):
        dest = dest_order[i % len(dest_order)]
        for origin in origins:
            add(
                origin["code"],
                origin["name"],
                dest["code"],
                dest["name"],
                dep,
                ret,
                stay,
                2,
            )

    candidates.sort(key=lambda x: x[7])

    queries: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for oc, on, dc, dn, dep, ret, stay, _prio in candidates:
        key = (oc, dc, dep, ret)
        if key in seen:
            continue
        seen.add(key)
        queries.append(
            {
                "origin": oc,
                "origin_name": on,
                "destination": dc,
                "destination_name": dn,
                "departure": dep,
                "return": ret,
                "stay_days": stay,
            }
        )
        if len(queries) >= max_queries:
            break

    unsearched = sum(
        1
        for dep, ret, _stay in coarse
        for origin in origins
        for dest in destinations
        if (origin["code"], dest["code"], dep, ret) not in searched
    )

    meta = {
        "monitor_id": config.get("id"),
        "window": f"{dep_start} → return by {latest_return}",
        "destinations": [d["code"] for d in destinations],
        "min_stay_days": min_stay,
        "coarse_combos_total": len(coarse) * len(origins) * len(destinations),
        "coarse_unsearched": unsearched,
        "queries_this_run": len(queries),
        "mode": "explore" if explore else "adaptive",
    }
    return queries, meta
