"""Adaptive query planner — explore the date window for the cheapest combo."""

from __future__ import annotations

from date_combos import coarse_pairs, refine_pairs, rotate_pairs


def plan_queries(
    config: dict,
    searched: set[tuple[str, str, str]],
    best_offer: dict | None,
    run_index: int,
    explore: bool = False,
) -> tuple[list[dict], dict]:
    """
    Build prioritized API queries for this run.

    Strategy (in order):
    1. Refine around all-time best price (if known)
    2. Unsearched coarse-grid combos (broad coverage)
    3. Rotating coarse batch (ongoing exploration)

    Returns (queries, meta) where meta describes the search state.
    """
    season = config["season"]
    search = config["search"]
    origins = config["route"]["origins"]
    dest = config["route"]["destination"]["code"]

    dep_start = season["departure_start"]
    latest_return = season["latest_return"]
    min_stay = season.get("min_stay_days", 7)
    dep_step = search.get("departure_step_days", 4)
    stay_lengths = search.get("stay_lengths")
    refine_window = search.get("refine_window_days", 3)
    max_queries = search.get("max_queries_per_run", 12)
    if explore:
        max_queries = search.get("max_queries_explore", 24)

    pairs_per_origin = max(1, max_queries // len(origins))
    candidates: list[tuple[str, str, int, str]] = []  # dep, ret, stay, priority
    seen_pair: set[tuple[str, str, str]] = set()

    def add_pair(origin_code: str, dep: str, ret: str, stay: int, priority: int) -> None:
        key = (origin_code, dep, ret)
        if key in seen_pair:
            return
        if key in searched and not explore:
            return
        seen_pair.add(key)
        candidates.append((dep, ret, stay, priority))

    # 1) Refine around best known offer
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
        for origin in origins:
            for dep, ret, stay in refine:
                add_pair(origin["code"], dep, ret, stay, priority=0)

    # 2) Coarse grid — unsearched first
    coarse = coarse_pairs(
        dep_start,
        latest_return,
        min_stay_days=min_stay,
        departure_step_days=dep_step,
        stay_lengths=stay_lengths,
    )
    unsearched_coarse: list[tuple[str, str, int]] = []
    for dep, ret, stay in coarse:
        if all((o["code"], dep, ret) not in searched for o in origins):
            unsearched_coarse.append((dep, ret, stay))

    for dep, ret, stay in unsearched_coarse:
        for origin in origins:
            add_pair(origin["code"], dep, ret, stay, priority=1)

    # 3) Rotating coarse coverage
    rotated = rotate_pairs(coarse, run_index, pairs_per_origin)
    for dep, ret, stay in rotated:
        for origin in origins:
            add_pair(origin["code"], dep, ret, stay, priority=2)

    candidates.sort(key=lambda x: x[3])
    selected_pairs: list[tuple[str, str, int]] = []
    selected_keys: set[tuple[str, str, int]] = set()
    for dep, ret, stay, _prio in candidates:
        pair_key = (dep, ret, stay)
        if pair_key in selected_keys:
            continue
        selected_keys.add(pair_key)
        selected_pairs.append(pair_key)
        if len(selected_pairs) >= pairs_per_origin:
            break

    queries: list[dict] = []
    for origin in origins:
        for dep, ret, stay in selected_pairs:
            queries.append(
                {
                    "origin": origin["code"],
                    "origin_name": origin["name"],
                    "destination": dest,
                    "departure": dep,
                    "return": ret,
                    "stay_days": stay,
                }
            )

    meta = {
        "window": f"{dep_start} → return by {latest_return}",
        "min_stay_days": min_stay,
        "coarse_combos_total": len(coarse),
        "coarse_unsearched": len(unsearched_coarse),
        "pairs_this_run": len(selected_pairs),
        "mode": "explore" if explore else "adaptive",
    }
    return queries[:max_queries], meta
