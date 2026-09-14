"""
End-to-end mapping test for collect.to_signal, against ArcGIS features copied
verbatim from the live layer. No network.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import collect  # noqa: E402

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "arcgis_features.json")) as _fh:
    FEATURES = json.load(_fh)["features"]

BY_ID = {f["attributes"].get("RECORD_ID"): f for f in FEATURES}


def test_record_without_an_id_is_dropped():
    assert collect.to_signal(BY_ID[""]) is None


def test_wagamama_maps_completely():
    s = collect.to_signal(BY_ID["BLD-26-0526061"])
    assert s["source"] == "permit"
    assert s["source_id"] == "BLD-26-0526061"
    assert s["id"].startswith("permit-")
    assert s["hood"] == "waterst"
    assert s["trade"] == "restaurant"
    assert s["stage_hint"] == "early_start"
    assert s["entity"] == "Wagamama Pan Asian"
    assert s["address"] == "1050 Water St"
    assert s["is_fitout"] is True
    assert s["is_dwelling"] is False
    assert s["source_url"].startswith("https://aca-prod.accela.com/TAMPA/")
    assert s["filed_at"] and s["issued_at"]
    assert s["filed_at"] < s["issued_at"]
    # The layer has no valuation, seats or contact field — assert the absence
    # so a future schema change that adds one does not go unnoticed.
    assert s["value_est"] is None
    assert s["seats"] is None
    assert s["contacts"] == []


def test_condo_unit_remodel_is_not_a_fitout():
    s = collect.to_signal(BY_ID["BLD-26-0526036"])
    assert s["hood"] == "waterst"
    assert s["is_dwelling"] is True
    assert s["is_fitout"] is False
    assert s["address"] == "1209 E Cumberland Ave #903"


def test_record_outside_every_submarket_has_no_hood():
    s = collect.to_signal(BY_ID["BLD-26-0526641"])
    assert s["hood"] is None
    assert s["entity"] == "Coca-Cola"
    assert s["stage_hint"] == "early_start"


@pytest.mark.parametrize("feat", [f for f in FEATURES if f["attributes"].get("RECORD_ID")],
                         ids=[f["attributes"]["RECORD_ID"]
                              for f in FEATURES if f["attributes"].get("RECORD_ID")])
def test_every_signal_carries_provenance(feat):
    """PLAN.md §0.2: no row without source_url and retrieved_at."""
    s = collect.to_signal(feat)
    assert s["source_url"]
    assert s["retrieved_at"]
    assert json.dumps(s)  # must be serialisable for signals.jsonl


def test_summary_renders_without_a_network_call():
    signals = [collect.scored(s) for s in (collect.to_signal(f) for f in FEATURES) if s]
    md = collect.summary(signals, {"permit": {"name": "Building permits",
                                              "fetched": len(signals)}})
    assert "# Tampa Bid Radar" in md
    assert "Wagamama Pan Asian" in md
    assert "early_start" in md


def test_summary_reports_a_failed_source_rather_than_hiding_it():
    md = collect.summary([], {"abt": {"name": "Alcoholic-beverage permits",
                                      "error": "ArcGISError: boom"}})
    assert "ArcGISError: boom" in md
    assert "⚠️" in md


def test_one_record_arriving_as_two_features_is_collected_once(monkeypatch):
    """The permit layer carries a feature per address unit, so BLD-26-0522346
    arrived as both `5041 W Cypress St` and `5041 W Cypress St #FS`."""
    import sources

    dup = {"id": "permit-same", "source": "permit", "source_id": "BLD-26-0522346",
           "source_url": "https://x", "retrieved_at": "now", "hood": "airport",
           "address": "5041 W Cypress St", "trade": "medical",
           "stage_hint": "revision", "entity": "Inlumia Imaging", "contacts": [],
           "is_fitout": True, "filed_at": "2026-02-04"}

    class _Fake:
        SOURCE = "permit"
        NAME = "Building permits"

        @staticmethod
        def collect(days_back):
            return [dict(dup), dict(dup, address="5041 W Cypress St #FS")]

    monkeypatch.setattr(sources, "ALL", [_Fake])
    signals, report = collect.run_sources(365)
    assert len(signals) == 1
    assert report["permit"]["duplicates"] == 1


def test_a_source_that_raises_does_not_take_the_others_down(monkeypatch):
    import sources

    class _Boom:
        SOURCE = "abt"
        NAME = "Alcoholic-beverage permits"

        @staticmethod
        def collect(days_back):
            raise RuntimeError("upstream 503")

    class _Fine:
        SOURCE = "permit"
        NAME = "Building permits"

        @staticmethod
        def collect(days_back):
            return [{"id": "a", "source": "permit", "hood": "ybor", "trade": "restaurant",
                     "stage_hint": "early_start", "entity": "X", "contacts": [],
                     "is_fitout": True, "filed_at": "2026-08-01"}]

    monkeypatch.setattr(sources, "ALL", [_Boom, _Fine])
    signals, report = collect.run_sources(365)
    assert len(signals) == 1
    assert "upstream 503" in report["abt"]["error"]
    assert report["permit"]["fetched"] == 1


def test_the_calibration_seed_measures_avgti_and_only_avgti():
    """Win rate is a fact about us and comes from Won/Lost rows a person
    logged. Market share is a different quantity. The seed must never carry
    anything a reader could mistake for our win rate."""
    sigs = [
        {"hood": "waterst", "qualified": True, "value_est": 300_000,
         "contractor_name": "TWT RESTAURANT DESIGN", "contractor_licence": "CBC1"},
        {"hood": "waterst", "qualified": True, "value_est": 500_000,
         "contractor_name": "TWT RESTAURANT DESIGN", "contractor_licence": "CBC1"},
        {"hood": "riverwalk", "qualified": True, "value_est": 700_000,
         "contractor_name": "BUILDIFY", "contractor_licence": "CGC2"},
    ]
    seed = collect.calibration_seed(sigs, collect.market_share(sigs))
    assert seed["measures"] == "avgTI"
    assert "winRate" not in json.dumps(seed)
    assert seed["n"] == 3
    assert seed["avg_value"] == 500_000.0
    assert seed["by_hood"]["waterst"]["avg_value"] == 400_000.0


def test_the_seed_excludes_suspect_values_and_unqualified_rows():
    sigs = [
        {"hood": "riverwalk", "qualified": True, "value_est": 280_000_000,
         "value_suspect": True, "contractor_name": "SOME BUILDERS", "contractor_licence": "C1"},
        {"hood": "riverwalk", "qualified": False, "value_est": 9_000_000,
         "contractor_name": "NOT A FITOUT LLC", "contractor_licence": "C2"},
        {"hood": "riverwalk", "qualified": True, "value_est": 400_000,
         "contractor_name": "REAL GC", "contractor_licence": "C3"},
    ]
    seed = collect.calibration_seed(sigs, collect.market_share(sigs))
    assert seed["n"] == 1
    assert seed["avg_value"] == 400_000.0


def test_no_valued_permits_means_no_seed_rather_than_a_zero():
    sigs = [{"hood": "waterst", "qualified": True,
             "contractor_name": "GC WITH NO VALUE", "contractor_licence": "C1"}]
    assert collect.calibration_seed(sigs, collect.market_share(sigs)) is None
