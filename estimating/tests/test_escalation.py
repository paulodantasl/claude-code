"""Tests for the validator's escalation check.

`escalation_rows` is pure, so the judgement it encodes — when a carried
contingency stops being a cushion — is tested without FRED, a key, or network.

Run: python3 -m pytest estimating/tests/
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "validate_estimate", Path(__file__).resolve().parents[1] / "scripts" / "validate_estimate.py"
)
validate_estimate = importlib.util.module_from_spec(_SPEC)
sys.modules["validate_estimate"] = validate_estimate
_SPEC.loader.exec_module(validate_estimate)

escalation_rows = validate_estimate.escalation_rows


def esc(annualized=8.0, pct=8.0, months=12, series="WPUSI012011"):
    """A FRED escalation read shaped like MarketService.escalation() returns."""
    return {
        "series": series,
        "months": months,
        "observations": 12,
        "start": {"date": "2025-08-01", "value": 100.0},
        "end": {"date": "2026-08-01", "value": 100.0 + pct},
        "pct_change": pct,
        "annualized_pct": annualized,
    }


def levels(rows):
    return {level for level, _check, _msg in rows}


def messages(rows):
    return " ".join(msg for _level, _check, msg in rows)


# --------------------------- the exposure model ---------------------------

def test_ample_contingency_passes():
    # 8%/yr over 30 days = 0.66% drift; 40% material share ⇒ ~0.26% of bid.
    # A 5% contingency swallows that with room to spare.
    rows = escalation_rows(esc(annualized=8.0), mat_share=0.4,
                           contingency_pct=5.0, validity_days=30)
    assert "PASS" in levels(rows)
    assert "WARN" not in levels(rows)


def test_escalation_exceeding_contingency_warns():
    # 30%/yr over 180 days = 14.8% drift; 50% material share ⇒ ~7.4% of bid,
    # against a 3% contingency.
    rows = escalation_rows(esc(annualized=30.0, pct=30.0), mat_share=0.5,
                           contingency_pct=3.0, validity_days=180)
    assert "WARN" in levels(rows)
    assert "fully consumed" in messages(rows)


def test_thin_cushion_warns_before_it_is_exceeded():
    # ~2.2% required against a 3% carried line: covered, but 74% consumed.
    rows = escalation_rows(esc(annualized=18.0, pct=18.0), mat_share=0.5,
                           contingency_pct=3.0, validity_days=90)
    assert "WARN" in levels(rows)
    assert "thin cushion" in messages(rows)
    assert "fully consumed" not in messages(rows)


def test_zero_contingency_with_rising_materials_warns():
    rows = escalation_rows(esc(annualized=6.0), mat_share=0.45,
                           contingency_pct=0.0, validity_days=60)
    assert "WARN" in levels(rows)
    assert "contingency_pct=0" in messages(rows)


def test_longer_validity_raises_the_requirement():
    """The window is the exposure — the same index costs more over a longer hold."""
    short = escalation_rows(esc(annualized=12.0), 0.5, 4.0, validity_days=30)
    long = escalation_rows(esc(annualized=12.0), 0.5, 4.0, validity_days=365)
    assert "PASS" in levels(short)
    assert "WARN" in levels(long)


def test_material_share_scales_the_requirement():
    """A sub-heavy bid carries less index exposure than a self-perform one."""
    light = escalation_rows(esc(annualized=20.0, pct=20.0), 0.10, 2.0, validity_days=90)
    heavy = escalation_rows(esc(annualized=20.0, pct=20.0), 0.70, 2.0, validity_days=90)
    assert "PASS" in levels(light)
    assert "WARN" in levels(heavy)


# --------------------------- degradation and citation ---------------------------

def test_falling_materials_is_informational_not_a_warning():
    rows = escalation_rows(esc(annualized=-4.0, pct=-4.0), mat_share=0.5,
                           contingency_pct=0.0, validity_days=180)
    assert levels(rows) == {"INFO"}
    assert "flat or falling" in messages(rows)


def test_series_error_degrades_to_info():
    rows = escalation_rows(
        {"series": "WPU081", "error": "not enough observations in window to measure a move"},
        mat_share=0.5, contingency_pct=2.0, validity_days=90,
    )
    assert levels(rows) == {"INFO"}
    assert "not checked" in messages(rows)


def test_missing_annualized_rate_degrades_to_info():
    read = esc()
    read["annualized_pct"] = None
    rows = escalation_rows(read, mat_share=0.5, contingency_pct=2.0, validity_days=90)
    assert levels(rows) == {"INFO"}


def test_output_cites_the_series_and_both_endpoints():
    """A WARN a reviewer cannot trace back to a published series is not evidence."""
    rows = escalation_rows(esc(annualized=30.0, pct=30.0), 0.5, 3.0, 180)
    text = messages(rows)
    assert "WPUSI012011" in text
    assert "2025-08-01" in text and "2026-08-01" in text
    assert "+30.0%/yr" in text


def test_never_emits_a_fail():
    """The check rests on a published index, not this bid's buyout — advisory only."""
    for annualized, share, carried, days in [
        (200.0, 1.0, 0.0, 365), (-50.0, 1.0, 0.0, 365), (0.0, 0.0, 0.0, 1),
    ]:
        rows = escalation_rows(esc(annualized=annualized, pct=annualized), share, carried, days)
        assert "FAIL" not in levels(rows)


# --------------------------- the live fallback ---------------------------
#
# These cover --escalation-live. The default path reads the committed snapshot and
# is covered in test_snapshot.py.

def _stub_ideal_apis(monkeypatch, client):
    """Install a minimal fake ideal_apis, matching what check_escalation imports."""
    pkg = type(sys)("ideal_apis")
    pkg.IdealAPIs = client
    exceptions = type(sys)("ideal_apis.exceptions")

    class MissingAPIKeyError(Exception):
        pass

    exceptions.MissingAPIKeyError = MissingAPIKeyError
    monkeypatch.setitem(sys.modules, "ideal_apis", pkg)
    monkeypatch.setitem(sys.modules, "ideal_apis.exceptions", exceptions)
    return MissingAPIKeyError


def test_check_escalation_survives_a_broken_client(monkeypatch):
    """A FRED outage must not take the validator down with it."""
    rep = validate_estimate.Report()

    class Boom:
        def __init__(self, *a, **kw):
            raise RuntimeError("network unreachable")

    _stub_ideal_apis(monkeypatch, Boom)
    validate_estimate.check_escalation(rep, 0.5, 3.0, 90, "construction_materials", 12, live=True)
    assert [r[0] for r in rep.rows] == ["INFO"]
    assert "FRED unreachable" in rep.rows[0][2]


def test_check_escalation_names_the_missing_key(monkeypatch):
    """A missing key is a config fix, not an outage — say which one."""
    rep = validate_estimate.Report()
    holder = {}

    class NoKey:
        def __init__(self, *a, **kw):
            pass

        @property
        def market(self):
            raise holder["exc"]("FRED requires IDEAL_FRED_KEY")

    holder["exc"] = _stub_ideal_apis(monkeypatch, NoKey)
    validate_estimate.check_escalation(rep, 0.5, 3.0, 90, "construction_materials", 12, live=True)
    assert rep.rows[0][0] == "INFO"
    assert "IDEAL_FRED_KEY not set" in rep.rows[0][2]


def test_check_escalation_reports_a_real_read(monkeypatch):
    """The happy path: a FRED read reaches the report as a cited row."""
    rep = validate_estimate.Report()
    read = esc(annualized=30.0, pct=30.0)

    class Client:
        def __init__(self, *a, **kw):
            pass

        market = type("M", (), {"escalation": staticmethod(lambda *a, **kw: read)})()

    _stub_ideal_apis(monkeypatch, Client)
    validate_estimate.check_escalation(rep, 0.5, 3.0, 180, "construction_materials", 12, live=True)
    assert "WARN" in {r[0] for r in rep.rows}
    assert "WPUSI012011" in " ".join(r[2] for r in rep.rows)


def test_check_escalation_reports_when_ideal_apis_is_absent(monkeypatch):
    """No ideal_apis at all: say how to get the check, do not fail the run."""
    rep = validate_estimate.Report()
    monkeypatch.setitem(sys.modules, "ideal_apis", None)  # forces ImportError
    validate_estimate.check_escalation(rep, 0.5, 3.0, 90, "construction_materials", 12, live=True)
    assert rep.rows[0][0] == "INFO"
    assert "ideal_apis not installed" in rep.rows[0][2]


@pytest.mark.parametrize("flag_days,csv_days,expected", [
    (None, None, 30),      # neither set → default
    (None, 45.0, 45),      # markups.csv supplies it
    (90, 45.0, 90),        # explicit flag wins over markups.csv
])
def test_bid_validity_precedence(flag_days, csv_days, expected):
    """Mirrors the resolution order in main(): flag, then markups.csv, then 30."""
    mk = {"bid_validity_days": csv_days} if csv_days is not None else {}
    resolved = flag_days or int(mk.get("bid_validity_days") or 0) or 30
    assert resolved == expected
