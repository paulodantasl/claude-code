"""
Offline mapping tests for the three Phase 2 sources.

Fixtures are ArcGIS features copied verbatim from the live Tampa layers
(`fixtures/leading_features.json`, retrieved 2026-09-14). No network.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import arcgis  # noqa: E402
import score  # noqa: E402
from sources import abt, cra_grants, entitlements  # noqa: E402

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "leading_features.json")) as _fh:
    FIX = json.load(_fh)

NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------- arcgis utils

@pytest.mark.parametrize("value,expected", [
    (None, None), (0, None), ("nope", None),
    (1769403600000, "2026-01-26"),
])
def test_epoch_to_date(value, expected):
    assert arcgis.epoch_to_date(value) == expected


def test_out_of_range_dates_are_dropped_not_carried():
    """The alcoholic-beverage layer holds a 2997 and an 0201. A lease signed in
    2997 would sort to the top of every list."""
    year_2997 = int(datetime(2997, 1, 29, tzinfo=timezone.utc).timestamp() * 1000)
    assert arcgis.epoch_to_date(year_2997) is None
    assert arcgis.epoch_to_date(-55_000_000_000_000) is None


@pytest.mark.parametrize("value,expected", [
    ("08/20/2026", "2026-08-20"), ("2026-08-20", "2026-08-20"),
    ("", None), (None, None), ("not a date", None), ("08/20/2997", None),
])
def test_us_date_to_iso(value, expected):
    assert arcgis.us_date_to_iso(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("4445", 4445.0), (4445, 4445.0), ("See Ordinance", None),
    ("", None), (None, None), ("0", None), (0.0, None), ("25,680.50", 25680.5),
])
def test_number_survives_a_string_typed_numeric_field(value, expected):
    assert arcgis.number(value) == expected


def test_clean_trims_the_trailing_space_on_bus_name():
    assert arcgis.clean("BOSC ") == "BOSC"
    assert arcgis.clean("  ") is None
    assert arcgis.clean(None) is None


def test_record_url_resolves_to_the_single_row():
    url = arcgis.record_url("Planning/AlcoholBeverage", 0, 15591)
    assert url.startswith("https://arcgis.tampagov.net/")
    assert "OBJECTID%3D15591" in url or "OBJECTID=15591" in url
    assert "outFields=%2A" in url or "outFields=*" in url


# ------------------------------------------------------------------- ABT

ABT_ROWS = [abt._to_signal(f["attributes"], f["geometry"]["x"], f["geometry"]["y"], NOW)
            for f in FIX["abt"]]


def test_abt_extracts_real_contacts():
    with_contacts = [r for r in ABT_ROWS if r["contacts"]]
    assert with_contacts, "no contacts parsed from the sample"
    for row in with_contacts:
        for c in row["contacts"]:
            assert c["kind"] in {"phone", "email"}
            assert c["value"] and c["from"].startswith("AlcoholBeverage.")


def test_abt_bosc_row_maps_completely():
    row = next(r for r in ABT_ROWS if r["entity"] == "BOSC")
    assert row["source"] == "abt"
    assert row["address"].startswith("201 W Platt St")
    assert row["zip"] == "33606"
    assert row["trade"] == "restaurant"
    assert row["sqft"] == 4445.0
    # 201 W Platt St is on the river at Platt, five blocks up the mainland from
    # the Davis Islands bridge. It resolved to `davis` until the island's buffer
    # was clipped at the shoreline.
    assert row["hood"] == "riverwalk"
    assert row["source_url"].startswith("https://arcgis.tampagov.net/")
    assert any(c["value"] == "813-486-8128" for c in row["contacts"])
    assert any(c["value"] == "dawn@mainstreeteg.com" for c in row["contacts"])


def test_abt_does_not_invent_square_footage_from_see_ordinance():
    row = next(r for r in ABT_ROWS if r["entity"] == "Pepper's Island Restaurant")
    assert row["sqft"] is None
    assert row["hood"] == "ybor"


def test_abt_collapses_a_duplicate_phone():
    """LARA files the same number as both business and owner phone."""
    row = next(r for r in ABT_ROWS if r["entity"] == "LARA")
    phones = [c["value"] for c in row["contacts"] if c["kind"] == "phone"]
    assert phones == ["813-410-3730"]


@pytest.mark.parametrize("condition,prefix,trade", [
    ("Consumption On Premises-Restaurant", "4", "restaurant"),
    ("Consumption On Premises", "2", "restaurant"),
    ("Package Sales", "1", "retail"),
    ("Consumption On Premises & Package Sales", "4", "restaurant"),
    ("Consumption On Premises-Large Venue", "4", "restaurant"),
    (None, None, "other"),
])
def test_abt_trade_from_sale_condition(condition, prefix, trade):
    assert abt._trade(condition, prefix)[0] == trade


def test_abt_signals_score_with_a_contact_bonus():
    row = next(r for r in ABT_ROWS if r["contacts"] and r["hood"])
    result = score.score(row)
    assert result["score_components"]["access"] >= 10
    assert "needs_contact" not in result["warnings"]


# ---------------------------------------------------------------- entitlement

def test_entitlement_maps_the_hearing_date():
    a = FIX["entitlement"][0]["attributes"]
    assert arcgis.us_date_to_iso(a["TENTATIVEHEARING"]) == "2026-08-20"
    assert a["APPSTATUS"] == "In Process"
    assert a["URL"].startswith("https://aca-prod.accela.com/TAMPA/")


def test_entitlement_bid_window_opens_at_the_hearing():
    from datetime import date
    opens, closes = score.bid_window("pre_permit", "2026-01-26", date(2026, 3, 1),
                                     hearing_at="2026-08-20")
    assert opens == "2026-08-20"
    assert closes > opens


def test_entitlement_bid_window_never_opens_in_the_past():
    from datetime import date
    opens, _ = score.bid_window("pre_permit", "2026-01-26", date(2026, 9, 14),
                                hearing_at="2026-08-20")
    assert opens == "2026-09-14"


def test_alcoholic_beverage_special_use_is_an_fnb_tell():
    assert "AB Special Use 2" in entitlements.AB_CASES


def test_row_vacating_is_not_a_fitout():
    assert "ROW Vacating" in entitlements.LOW_VALUE_CASES


def test_an_entitlement_with_no_trade_still_qualifies_as_a_precursor():
    result = score.score({"source": "entitlement", "hood": "ybor", "trade": "other",
                          "stage_hint": "pre_permit", "filed_at": "2026-08-01",
                          "hearing_at": "2026-10-01", "entity": None, "contacts": [],
                          "confidence": 0.2})
    assert "trade_other" not in result["blockers"]
    assert "trade_undeclared" in result["warnings"]


# ------------------------------------------------------------------ CRA grants

def test_cra_reads_the_project_cost_not_the_zeroed_award():
    a = FIX["cra_grant"][0]["attributes"]
    assert arcgis.number(a["AWARDEDAMOUNT"]) is None        # 0.0 on completed rows
    assert arcgis.number(a["FINALAWARDAMOUNT"]) == 10000.0
    assert arcgis.number(a["TOTALPROJECTCOST"]) == 25680.0


def test_cra_status_trailing_space_is_handled():
    assert (arcgis.clean("Awarded ") or "").strip().lower() == "awarded"


@pytest.mark.parametrize("description,trade", [
    ("a full building and site rehabilitation of a former nightclub to create a "
     "health care and wellness facility, including pharmacy services.", "medical"),
    ("exterior improvements to modernize the building for an existing retail "
     "strip center", "retail"),
    ("interior renovation of a vacant building into an office.", "office"),
    ("nothing identifiable here", "other"),
])
def test_cra_trade_from_the_description(description, trade):
    assert cra_grants._trade(description, None)[0] == trade


def test_only_interior_grants_are_fitouts():
    assert "Commercial Interior Grant" in cra_grants.INTERIOR_GRANTS
    assert "Vanilla Shell Grant" in cra_grants.INTERIOR_GRANTS
    assert "Façade Improvement Grant" in cra_grants.EXTERIOR_GRANTS
    assert "Façade Improvement Grant" not in cra_grants.INTERIOR_GRANTS


def test_cra_grant_with_a_real_value_scores_on_it():
    result = score.score({"source": "cra_grant", "hood": "ybor", "trade": "medical",
                          "stage_hint": "cra_awarded", "filed_at": "2026-08-01",
                          "entity": "Health Matters Pharmacy West", "contacts": [],
                          "value_est": 822641.7, "confidence": 0.6})
    assert result["score_components"]["value"] == score.value_points(822641.7)
    assert result["qualified"] is True


def test_the_value_curve_is_flat_across_ordinary_fitout_sizes():
    """PLAN §2.4's 4·log10(value/10,000) puts a $75k job at 4 and an $800k job
    at 8 — the same as the unknown-value prior. Worth knowing before anyone
    reads a score difference of one or two points as meaningful."""
    assert score.value_points(75_000) == 4
    assert score.value_points(822_641) == score.value_points(None) == 8
    assert score.value_points(5_000_000) == 11
    assert score.value_points(None) == 8


# ------------------------------------------------------------------- contract

@pytest.mark.parametrize("module", [abt, cra_grants, entitlements])
def test_every_source_declares_the_module_contract(module):
    assert isinstance(module.SOURCE, str) and module.SOURCE
    assert isinstance(module.NAME, str) and module.NAME
    assert callable(module.collect)


REQUIRED_KEYS = {"id", "source", "source_id", "source_url", "retrieved_at", "hood",
                 "address", "lat", "lon", "entity", "trade", "confidence",
                 "stage_hint", "value_est", "filed_at", "contacts"}


@pytest.mark.parametrize("row", ABT_ROWS, ids=lambda r: str(r["source_id"]))
def test_abt_signals_carry_the_required_schema(row):
    assert REQUIRED_KEYS <= set(row)
    assert row["source_url"] and row["retrieved_at"]
    assert json.dumps(row, default=str)


# --------------------------------------------------------- qualification gate

def _sig(**kw):
    base = {"source": "entitlement", "hood": "ybor", "trade": "other",
            "stage_hint": "pre_permit", "filed_at": "2026-08-01",
            "entity": None, "contacts": [], "confidence": 0.2, "is_fitout": True}
    base.update(kw)
    return base


def test_a_record_no_gc_bids_is_a_hard_blocker():
    """Sized against the first real multi-source run: 62 of 160 live
    entitlement cases were residential variances and design exceptions, and
    letting them qualify buried nine real rezonings under 25 rows that all
    scored an identical 58."""
    assert "not_fitout" in score.score(_sig(is_fitout=False))["blockers"]
    assert score.score(_sig(is_fitout=False))["qualified"] is False
    assert score.score(_sig(is_fitout=True))["qualified"] is True


@pytest.mark.parametrize("case,is_fitout", [
    ("Rezoning", True),
    ("General Land Use", True),
    ("Special Use 1 - General", True),
    ("AB Special Use 2", True),
    ("Variance Review Board", False),     # a setback on somebody's house
    ("Design Exception 1", False),
    ("Formal Decision", False),
    ("ROW Vacating", False),
    ("Temp Special Event", False),
])
def test_only_commercial_case_types_are_fitouts(case, is_fitout):
    assert (case in entitlements.FITOUT_CASES) is is_fitout


def test_an_entitlement_never_presents_a_case_type_as_a_business_name():
    """`Variance Review Board` in an Entity column reads like a company."""
    for case in entitlements.FITOUT_CASES | entitlements.LOW_VALUE_CASES:
        assert case not in ("", None)
    # the mapper sets project_name to None; the case type lives in scope
    assert "case_type" not in entitlements.AB_CASES


def test_an_awarded_cra_grant_is_a_precursor_not_a_dead_row():
    """Centro Asturiano's $987k Special Projects grant is Awarded and not
    complete: committed money, outstanding work, broad scope."""
    result = score.score({"source": "cra_grant", "hood": "ybor", "trade": "other",
                          "stage_hint": "cra_awarded", "filed_at": "2026-08-01",
                          "entity": "Centro Asturiano de Tampa", "contacts": [],
                          "value_est": 987850.99, "is_fitout": True,
                          "confidence": 0.2})
    assert "trade_other" not in result["blockers"]
    assert result["qualified"] is True


def test_a_completed_cra_grant_is_not_a_lead():
    result = score.score({"source": "cra_grant", "hood": "ybor", "trade": "retail",
                          "stage_hint": "issued", "filed_at": "2025-01-01",
                          "entity": "J.C. Newman Cigar Company", "contacts": [],
                          "value_est": 316405.5, "is_fitout": True})
    assert "already_awarded" in result["blockers"]
    assert result["qualified"] is False


def test_one_ordinance_over_several_addresses_does_not_collapse():
    """Ordinance 2026-74 covers three storefronts on E 2nd and E 4th Ave."""
    base = dict(FIX["abt"][0]["attributes"])
    base["ORD_PERMIT"] = "2026-74"
    ids = set()
    for addr in ("1302 E 2nd Ave", "1302 E 4th Ave", "1306 E 4th Ave"):
        a = dict(base, PERMIT_ADDR=addr, PERMIT_ADDR_2=None)
        ids.add(abt._to_signal(a, -82.44, 27.96, NOW)["id"])
    assert len(ids) == 3


# ------------------------------------------------ ABT: which date means a job

def _abt_feature(**over):
    a = dict(FIX["abt"][0]["attributes"])
    a.update(over)
    return a


def _epoch(iso):
    from datetime import date
    y, m, d = (int(x) for x in iso.split("-"))
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


def test_a_status_change_alone_is_not_a_lead(monkeypatch):
    """Mise en Place has been licensed since 1991. Its record being touched is
    a directory update, not a restaurant opening — including HISTORY_ACT_DT
    put it, Grand Central Cafe and Mitas Cocina Moderna on the call list at 83."""
    from datetime import timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
    old = "1991-05-12"
    feat = {"attributes": _abt_feature(CREATEDATE=_epoch(old), PLACARD_DT=None,
                                       HISTORY_ACT_DT=_epoch(recent),
                                       HISTORY_ACTION="Active"),
            "geometry": {"x": -82.44, "y": 27.96}}
    monkeypatch.setattr(abt, "_all_features", lambda: [feat])
    assert abt.collect(365) == []


@pytest.mark.parametrize("field,event", [
    ("CREATEDATE", "new_record"),
    ("PLACARD_DT", "placard_posted"),
])
def test_a_new_record_or_a_posted_placard_is_a_lead(monkeypatch, field, event):
    from datetime import timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
    attrs = _abt_feature(CREATEDATE=None, PLACARD_DT=None, HISTORY_ACT_DT=None,
                         HISTORY_ACTION="Active")
    attrs[field] = _epoch(recent)
    monkeypatch.setattr(abt, "_all_features",
                        lambda: [{"attributes": attrs, "geometry": {"x": -82.44, "y": 27.96}}])
    rows = abt.collect(365)
    assert len(rows) == 1
    assert rows[0]["abt_event"] == event
    # the date on the card is the event, not an ordinance letter from 2014
    assert rows[0]["filed_at"] == recent


def test_a_surrendered_licence_is_never_a_lead(monkeypatch):
    from datetime import timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
    attrs = _abt_feature(CREATEDATE=_epoch(recent), HISTORY_ACTION="Dry")
    monkeypatch.setattr(abt, "_all_features",
                        lambda: [{"attributes": attrs, "geometry": {"x": -82.44, "y": 27.96}}])
    assert abt.collect(365) == []
