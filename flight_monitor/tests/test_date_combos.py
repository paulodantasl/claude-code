"""Tests for flexible date search and multi-monitor planner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import load_monitor, resolve_season
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


def test_rolling_season():
    season = resolve_season({"mode": "rolling", "days_ahead_min": 30, "days_ahead_max": 180, "min_stay_days": 7})
    assert season["departure_start"] < season["latest_return"]


def test_europe_config_loads():
    config = load_monitor("europe")
    assert config["id"] == "europe"
    assert len(config["route"]["destinations"]) >= 5


def test_planner_multi_destination():
    config = load_monitor("natal")
    queries, meta = plan_queries(config, searched=set(), best_offer=None, run_index=0)
    assert len(queries) <= config["search"]["max_queries_per_run"]
    assert meta["monitor_id"] == "natal"


def test_europe_planner():
    config = load_monitor("europe")
    queries, meta = plan_queries(config, searched=set(), best_offer=None, run_index=0)
    assert len(queries) <= config["search"]["max_queries_per_run"]
    destinations = {q["destination"] for q in queries}
    assert len(destinations) >= 1
