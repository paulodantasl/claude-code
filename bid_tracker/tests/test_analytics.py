import math

import pytest

from bid_tracker.benchmark import benchmark
from bid_tracker.competitors import head_to_head, profiles
from bid_tracker.escalation import escalate, factor, series_for
from bid_tracker.gonogo import gonogo
from bid_tracker.importer import import_package
from bid_tracker.position import best_value, p_win, position, price_points
from bid_tracker.rates import cliffs, effective_psf, rate_bands
from bid_tracker.stats import quartiles, tab_stats
from bid_tracker.taxonomy import size_band
from conftest import FAKE_VALID, synth_package


@pytest.fixture
def loaded(conn, tmp_path):
    assert import_package(conn, FAKE_VALID, fixtures=True).status == "ok"
    assert import_package(conn, synth_package(tmp_path / "synth"), fixtures=True).status == "ok"
    return conn


def test_tab_stats_formulas():
    s = tab_stats([150, 100, 120, 110], ee=125, gsf=2)
    assert s.n == 4 and s.low == 100 and s.second == 110 and s.median == 115
    assert s.gap == pytest.approx(0.10)
    assert s.low_median == pytest.approx(100 / 115)
    assert s.low_ee == pytest.approx(0.80)
    mean = 120
    sd = math.sqrt(sum((x - mean) ** 2 for x in [100, 110, 120, 150]) / 3)
    assert s.cv == pytest.approx(sd / mean)
    assert s.range_pct == pytest.approx(0.5)
    assert s.low_psf == 50
    assert tab_stats([100]).gap is None


def test_quartiles_small_samples():
    assert quartiles([1, 2]) == {"n": 2, "values": [1, 2]}
    q = quartiles([1, 2, 3, 4, 5])
    assert (q["p25"], q["p50"], q["p75"]) == (2, 3, 4)


def test_size_bands():
    assert size_band(1800, None) == "<2.5k sf"
    assert size_band(None, 812_400) == "$300k-1M"
    assert size_band(30000, 10) == ">=25k sf"
    assert size_band(None, None) is None


def test_escalation(conn):
    import_package(conn, FAKE_VALID, fixtures=True)
    value, esc = escalate(conn, 100_000, "2024-03-12", series_id="WPUIP2300001")
    assert value == pytest.approx(110_000)
    assert "uses preliminary index values" in esc.flags
    # Nearest earlier period: 2024-07 uses the 2024-03 value.
    assert factor(conn, "WPUIP2300001", "2024-07").factor == pytest.approx(110 / 100)
    late = factor(conn, "WPUIP2300001", "2024-03", "2027-01")
    assert any("held flat" in f for f in late.flags)
    assert factor(conn, "WPUIP2300001", "2020-01").factor is None
    assert series_for("V-REN", "vertical", "school_district") == "PCU236222236222"
    assert series_for("R-MOLD", "restoration", "county") == "WPUIP2300001"
    assert series_for("V-TI", "vertical", "city") == "PCU236223236223"
    assert series_for(None, None, None) == "WPUIP2300001"
    assert series_for("V-REN") == "PCU236223236223"         # work class inferred from project type
    assert series_for("R-WATER") == "WPUIP2300001"


def test_benchmark_segment_and_fallback(loaded):
    b = benchmark(loaded, project_type="V-REN", agency_type="county", gsf=3000)
    assert b["n"] >= 5 and not b["dropped"]
    assert b["low_ee"]["p25"] <= b["low_ee"]["p50"] <= b["low_ee"]["p75"]
    thin = benchmark(loaded, project_type="V-ADA", agency_type="city", gsf=1800)
    assert thin["n"] == 1 and any("SMALL SAMPLE" in w for w in thin["warnings"])
    assert thin["dropped"]                       # widened before giving up
    assert benchmark(loaded, project_type="H-ROAD")["n"] == 0


def test_position_monotone_and_sane(loaded):
    r = position(loaded, cost=230_000, ee=250_000, project_type="V-REN")
    assert r["mode"] == "ee" and r["n_ratios"] >= 30
    wins = [row["p_win"] for row in r["table"]]
    assert all(a > b for a, b in zip(wins, wins[1:])), "P(win) must fall as markup rises"
    assert 0 <= r["m_star"] <= 0.20
    assert r["caveats"]


def test_position_refuses_thin_history(loaded):
    r = position(loaded, cost=100_000, ee=120_000, project_type="V-ADA", agency_type="city")
    assert "refused" in r


def test_position_needs_a_reference(loaded):
    with pytest.raises(ValueError):
        position(loaded, cost=100_000, project_type="V-REN", mode="ee")


def test_p_win_limits():
    assert p_win(0.4, {0: 1.0}) == 1.0
    assert p_win(0.5, {3: 1.0}) < p_win(0.5, {1: 1.0})


def test_best_value_price_cannot_close_gap():
    r = best_value(cost=100_000, competitor_price=110_000, weight=20, nonprice_gap=5)
    assert r["breakeven_bid"] == pytest.approx(82_500)
    assert r["flags"] and "cannot close" in r["flags"][0]
    ok = best_value(cost=100_000, competitor_price=130_000, weight=30, nonprice_gap=3)
    assert not ok["flags"] and ok["max_markup_to_close_gap"] > 0
    assert price_points(100, 100, 20) == 20
    assert price_points(110, 100, 20, "linear") == pytest.approx(18)


def test_rate_bands_and_cliffs(loaded):
    assert effective_psf("lump", 1500, 0, 500) == (6.0, True)
    assert effective_psf("sf", 5.25, 10001, None) == (5.25, False)
    bands = {(b["service"], b["bucket"]): b for b in rate_bands(loaded)}
    assert bands[("mold", "10,001+ sf")]["all_bidders"]["values"] == [9.0, 14.0]
    jumps = {(c["bidder"], round(c["jump"], 2)) for c in cliffs(loaded)}
    assert ("FAKE Zeta Restoration LLC", 2.62) in jumps       # bucket cliff
    assert all(c["to_bucket"] != "10,001+ sf" for c in cliffs(loaded))  # non-adjacent buckets skipped


def test_competitor_profiles(loaded):
    p = {x["name"]: x for x in profiles(loaded, top=0)}
    alpha = p["FAKE Builder Alpha LLC"]
    assert (alpha["bids"], alpha["wins"], alpha["win_rate"]) == (1, 1, 1.0)
    beta = p["FAKE Builder Beta, Inc."]
    assert (beta["bids"], beta["wins"], beta["low_bids"]) == (2, 0, 1)
    assert "Ideal Remodeling LLC" not in p
    h2h = {x["name"]: x for x in head_to_head(loaded)}
    assert h2h["FAKE Epsilon Construction LLC"]["ideal_lower"] == 1


def test_gonogo_flags(loaded):
    r = gonogo(loaded, project_type="V-REN", agency_id="fake-synth", cost=230_000,
               profile={"bond_limit_single": 200_000, "largest_win": 50_000, "ohp_floor_pct": 0.05})
    levels = {f["level"] for f in r["flags"]}
    assert r["verdict"] == "STOP" and "CAUTION" in levels
    clean = gonogo(loaded, project_type="V-REN", agency_id="fake-synth", cost=230_000,
                   profile={"bond_limit_single": 5_000_000})
    assert clean["verdict"] == "GO"
