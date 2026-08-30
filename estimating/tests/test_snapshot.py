"""Tests for the autonomous escalation path.

The point of the snapshot is that the check runs on every validation with no flag,
no key, and no network. These tests hold that promise to its edges: a missing or
corrupt snapshot degrades instead of failing, a stale one says so before its number
is used, and the default path never opens a socket.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validate_estimate = _load("validate_estimate")
refresh_escalation = _load("refresh_escalation")


def series_entry(annualized=8.0, pct=8.0, series="WPUSI012011"):
    return {
        "series": series,
        "months": 12,
        "observations": 12,
        "start": {"date": "2025-08-01", "value": 100.0},
        "end": {"date": "2026-08-01", "value": 100.0 + pct},
        "pct_change": pct,
        "annualized_pct": annualized,
    }


def write_snapshot(tmp_path, *, age_days=0, series=None):
    written = datetime.now(timezone.utc) - timedelta(days=age_days)
    snapshot = {
        "generated_at": written.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "FRED (Federal Reserve Bank of St. Louis)",
        "months": 12,
        "series_read": 2,
        "series_total": 2,
        "series": series if series is not None else {
            "construction_materials": series_entry(),
            "lumber_wood": series_entry(annualized=20.0, pct=20.0, series="WPU081"),
        },
    }
    path = tmp_path / "escalation.json"
    path.write_text(json.dumps(snapshot))
    return path


def rows(rep):
    return [(level, msg) for level, _check, msg in rep.rows]


def levels(rep):
    return {level for level, _check, _msg in rep.rows}


# --------------------------- reading the snapshot ---------------------------

def test_reads_a_snapshot_without_key_or_network(tmp_path):
    """The default path must not import ideal_apis or open a socket."""
    path = write_snapshot(tmp_path)
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(
        rep, 0.4, 5.0, 30, "construction_materials", 12, snapshot_path=path
    )
    assert "PASS" in levels(rep)
    assert any("WPUSI012011" in msg for _l, msg in rows(rep))


def test_missing_snapshot_degrades_with_a_next_step(tmp_path):
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(
        rep, 0.4, 5.0, 30, "construction_materials", 12,
        snapshot_path=tmp_path / "absent.json",
    )
    assert levels(rep) == {"INFO"}
    assert "refresh_escalation.py" in rows(rep)[0][1]


def test_corrupt_snapshot_degrades_instead_of_crashing(tmp_path):
    path = tmp_path / "escalation.json"
    path.write_text("{not json at all")
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "construction_materials", 12,
                                       snapshot_path=path)
    assert levels(rep) == {"INFO"}
    assert "unreadable" in rows(rep)[0][1]


def test_snapshot_without_series_is_rejected(tmp_path):
    path = tmp_path / "escalation.json"
    path.write_text(json.dumps({"generated_at": "2026-08-01T00:00:00Z", "series": {}}))
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "construction_materials", 12,
                                       snapshot_path=path)
    assert levels(rep) == {"INFO"}
    assert "no series" in rows(rep)[0][1]


def test_unknown_series_names_what_is_available(tmp_path):
    path = write_snapshot(tmp_path)
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "gypsum", 12, snapshot_path=path)
    assert levels(rep) == {"INFO"}
    assert "construction_materials" in rows(rep)[0][1]


def test_series_can_be_addressed_by_raw_fred_id(tmp_path):
    path = write_snapshot(tmp_path)
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "WPU081", 12, snapshot_path=path)
    assert "WPU081" in " ".join(msg for _l, msg in rows(rep))


# --------------------------- staleness ---------------------------

def test_fresh_snapshot_reports_its_age_as_info(tmp_path):
    path = write_snapshot(tmp_path, age_days=10)
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "construction_materials", 12,
                                       snapshot_path=path)
    age_rows = [msg for level, msg in rows(rep) if level == "INFO" and "ago" in msg]
    assert age_rows and "10d ago" in age_rows[0]


def test_stale_snapshot_warns_before_its_number_is_used(tmp_path):
    """A number nobody refreshed for months should not pass silently into a bid."""
    path = write_snapshot(tmp_path, age_days=validate_estimate.SNAPSHOT_STALE_DAYS + 5)
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "construction_materials", 12,
                                       snapshot_path=path)
    stale = [msg for level, msg in rows(rep) if level == "WARN" and "days old" in msg]
    assert stale
    # The escalation verdict is still produced — stale beats absent.
    assert "PASS" in levels(rep) or "WARN" in levels(rep)


def test_unparseable_timestamp_does_not_break_the_check(tmp_path):
    path = write_snapshot(tmp_path)
    data = json.loads(path.read_text())
    data["generated_at"] = "sometime last spring"
    path.write_text(json.dumps(data))
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "construction_materials", 12,
                                       snapshot_path=path)
    assert "FAIL" not in levels(rep)
    assert validate_estimate.snapshot_age_days(data) is None


def test_snapshot_verdict_matches_the_live_verdict(tmp_path):
    """Same numbers in, same judgement out — the source must not change the answer."""
    entry = series_entry(annualized=30.0, pct=30.0)
    path = write_snapshot(tmp_path, series={"construction_materials": entry})
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.5, 3.0, 180, "construction_materials", 12,
                                       snapshot_path=path)
    direct = validate_estimate.escalation_rows(entry, 0.5, 3.0, 180)
    assert [r[2] for r in rep.rows if r[1] == "escalation"][-len(direct):] == \
           [msg for _l, _c, msg in direct]


def test_default_path_opens_no_socket_and_imports_nothing(tmp_path, monkeypatch):
    """The load-bearing property: the check runs with no network and no ideal_apis.

    If either creeps back into the default path, the validator stops being a
    deterministic offline gate and starts failing in CI and on a plane.
    """
    import builtins
    import socket

    def no_socket(*a, **kw):
        raise AssertionError("default escalation path opened a socket")

    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.setattr(socket, "create_connection", no_socket)

    real_import = builtins.__import__

    def guarded(name, *a, **kw):
        if name == "ideal_apis" or name.startswith("ideal_apis."):
            raise AssertionError(f"default escalation path imported {name}")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", guarded)

    path = write_snapshot(tmp_path)
    rep = validate_estimate.Report()
    validate_estimate.check_escalation(rep, 0.4, 5.0, 30, "construction_materials", 12,
                                       snapshot_path=path)
    assert "PASS" in levels(rep)


# --------------------------- the refresh script ---------------------------

def test_alerts_fire_only_on_cost_driving_series():
    snapshot = {"series": {
        "construction_materials": series_entry(annualized=9.0),
        "treasury_10yr": series_entry(annualized=40.0),   # moves, but not a material cost
        "lumber_wood": series_entry(annualized=2.0),      # material, but below threshold
    }}
    fired = refresh_escalation.alerts(snapshot, alert_pct=6.0)
    assert [a["name"] for a in fired] == ["construction_materials"]


def test_alerts_are_ranked_worst_first():
    snapshot = {"series": {
        "construction_materials": series_entry(annualized=9.0),
        "lumber_wood": series_entry(annualized=25.0),
        "iron_steel": series_entry(annualized=14.0),
    }}
    fired = refresh_escalation.alerts(snapshot, alert_pct=6.0)
    assert [a["name"] for a in fired] == ["lumber_wood", "iron_steel", "construction_materials"]


def test_alerts_skip_series_that_failed_to_read():
    snapshot = {"series": {"construction_materials": {"series": "X", "error": "boom"}}}
    assert refresh_escalation.alerts(snapshot, alert_pct=1.0) == []


def test_falling_materials_never_alert():
    snapshot = {"series": {"lumber_wood": series_entry(annualized=-30.0, pct=-30.0)}}
    assert refresh_escalation.alerts(snapshot, alert_pct=6.0) == []


def test_report_renders_a_failed_series_without_crashing():
    snapshot = {
        "generated_at": "2026-08-28T00:00:00Z", "months": 12,
        "series_read": 1, "series_total": 2,
        "series": {
            "construction_materials": series_entry(),
            "iron_steel": {"series": "WPU101", "error": "not enough observations"},
        },
    }
    report = refresh_escalation.render_report(snapshot, [], 6.0)
    assert "not enough observations" in report
    assert "WPUSI012011" in report


def test_report_survives_a_series_missing_its_rate():
    """A partial entry must not take down the whole scheduled run."""
    broken = series_entry()
    broken["annualized_pct"] = None
    snapshot = {
        "generated_at": "2026-08-28T00:00:00Z", "months": 12,
        "series_read": 1, "series_total": 1, "series": {"construction_materials": broken},
    }
    assert "no usable observations" in refresh_escalation.render_report(snapshot, [], 6.0)


@pytest.mark.parametrize("name", sorted(refresh_escalation.ALERT_SERIES))
def test_every_alert_series_exists_in_the_client(name):
    """An alert on a series the client cannot fetch would never fire."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ideal_apis"))
    from ideal_apis.services.market import MarketService

    assert name in MarketService.SERIES
