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
    signals = [s for s in (collect.to_signal(f) for f in FEATURES) if s]
    md = collect.summary(signals, {"fetched": len(signals), "layer_total": 2577,
                                   "record_types": {"Commercial Building Alterations "
                                                    "(Renovations)"}})
    assert "# Tampa Bid Radar" in md
    assert "Wagamama Pan Asian" in md
    assert "EARLY START" in md
    # the condo remodel must not appear as a fitout row
    assert "1209 E Cumberland Ave #903" not in md.split("## Source notes")[0]
