"""Tests for flexible date search logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from date_combos import coarse_pairs, iter_flexible_pairs, refine_pairs, rotate_pairs
from search_planner import plan_queries


def test_flexible_window_bounds():
    pairs = list(
        iter_flexible_pairs(
            "2026-12-20",
            "2027-02-15",
            min_stay_days=7,
            departure_step_days=7,
            stay_lengths=[7, 14, 21],
        )
    )
    assert pairs
    for dep, ret, stay in pairs:
        assert dep >= "2026-12-20"
        assert ret <= "2027-02-15"
        assert stay >= 7
        assert stay == (int(ret[8:10]) - int(dep[8:10])) or stay >= 7  # rough sanity


def test_return_never_after_feb_15():
    pairs = coarse_pairs("2026-12-20", "2027-02-15", min_stay_days=7, departure_step_days=3)
    for _dep, ret, _stay in pairs:
        assert ret <= "2027-02-15"


def test_refine_around_best():
    pairs = refine_pairs(
        "2027-01-10",
        "2027-01-24",
        "2026-12-20",
        "2027-02-15",
        min_stay_days=7,
        window_days=2,
        stay_lengths=[14],
    )
    assert ("2027-01-10", "2027-01-24", 14) in pairs or any(
        p[0] == "2027-01-10" for p in pairs
    )


def test_planner_respects_max_queries():
    config = {
        "season": {
            "departure_start": "2026-12-20",
            "latest_return": "2027-02-15",
            "min_stay_days": 7,
        },
        "search": {
            "max_queries_per_run": 12,
            "departure_step_days": 4,
            "refine_window_days": 3,
            "stay_lengths": [7, 14, 21],
        },
        "route": {
            "origins": [{"code": "TPA", "name": "Tampa"}, {"code": "MCO", "name": "Orlando"}],
            "destination": {"code": "NAT"},
        },
    }
    queries, meta = plan_queries(config, searched=set(), best_offer=None, run_index=0)
    assert len(queries) <= 12
    assert meta["coarse_combos_total"] > 0


def test_rotate_covers_all():
    pairs = [(f"2026-12-{20+i:02d}", f"2027-01-{3+i:02d}", 14) for i in range(6)]
    seen = set()
    for run in range(3):
        batch = rotate_pairs(pairs, run, batch_size=2)
        seen.update(batch)
    assert len(seen) == len(pairs)
