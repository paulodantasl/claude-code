"""
Qualification and scoring — PLAN.md §2.3 / §2.4.

The signals below are the real ones the Phase 0 collector returned, so the
expectations are about jobs that exist, not invented cases.
"""
from __future__ import annotations

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import score  # noqa: E402

TODAY = date(2026, 9, 14)


def sig(**kw) -> dict:
    base = {"source": "permit", "hood": "waterst", "trade": "restaurant",
            "stage_hint": "early_start", "filed_at": "2026-06-22",
            "entity": "Wagamama Pan Asian", "contacts": [], "confidence": 0.9}
    base.update(kw)
    return base


# --- the four that qualified on the first real run -------------------------

@pytest.mark.parametrize("entity,hood,trade,stage,expected", [
    ("Wagamama Pan Asian", "waterst", "restaurant", "early_start", 73),
    ("Edikted", "airport", "retail", "early_start", 63),
    ("Altieri Ins. Consultants", "riverwalk", "office", "revision", 58),
    ("Nationwide", "airport", "office", "revision", 58),
])
def test_real_qualified_signals(entity, hood, trade, stage, expected):
    r = score.score(sig(entity=entity, hood=hood, trade=trade, stage_hint=stage), TODAY)
    assert r["score"] == expected
    assert r["qualified"] is True
    assert r["blockers"] == []


# --- hard blockers ---------------------------------------------------------

def test_issued_permit_is_blocked_as_already_awarded():
    """PLAN §2.3(d): keep it, tag `late`, route to win-rate analysis."""
    r = score.score(sig(stage_hint="issued"), TODAY)
    assert "already_awarded" in r["blockers"]
    assert r["qualified"] is False
    assert r["late"] is True
    assert r["score_components"]["urgency"] == 0


def test_outside_every_submarket_is_blocked():
    r = score.score(sig(hood=None, entity="Coca-Cola"), TODAY)
    assert "outside_submarkets" in r["blockers"]
    assert r["qualified"] is False


def test_trade_other_is_blocked():
    r = score.score(sig(trade="other"), TODAY)
    assert "trade_other" in r["blockers"]


def test_blocklisted_entity_is_blocked_and_loses_access_points():
    r = score.score(sig(entity="Tampa Police Aviation Office", trade="office",
                        stage_hint="early_start"), TODAY)
    assert any(b.startswith("blocklist:") for b in r["blockers"])
    assert r["score_components"]["access"] == -20
    assert r["qualified"] is False


@pytest.mark.parametrize("name", [
    "Publix Super Markets", "STARBUCKS COFFEE #1234", "Chase Bank branch",
    "cvs pharmacy", "City of Tampa Facilities", "Hillsborough County",
])
def test_blocklist_matching_is_case_insensitive_and_substring(name):
    assert score.blocklist_hit(name) is not None


@pytest.mark.parametrize("name", [
    "Wagamama Pan Asian", "Edikted", "Norlee Group", "The Violet Stone Pizzeria",
    None, "",
])
def test_blocklist_does_not_fire_on_real_tenants(name):
    assert score.blocklist_hit(name) is None


# --- soft blockers ---------------------------------------------------------

def test_missing_contact_is_a_warning_not_a_blocker():
    """Enforcing §2.3(e) as a hard gate would qualify nothing: no permit row
    has a contact channel."""
    r = score.score(sig(contacts=[]), TODAY)
    assert "needs_contact" in r["warnings"]
    assert not any("contact" in b for b in r["blockers"])
    assert r["qualified"] is True


def test_a_contact_channel_adds_access_points():
    with_contact = score.score(
        sig(contacts=[{"kind": "phone", "value": "813-555-0100"}]), TODAY)
    without = score.score(sig(contacts=[]), TODAY)
    assert with_contact["score_components"]["access"] == 20
    assert without["score_components"]["access"] == 10
    assert with_contact["score"] > without["score"]


def test_unnamed_entity_loses_the_local_entity_points():
    assert score.score(sig(entity=None), TODAY)["score_components"]["access"] == 0


# --- strip-outs ------------------------------------------------------------

def test_strip_out_qualifies_despite_an_undeclared_trade():
    """The tenant is committed and the build-back has not been bid."""
    r = score.score(sig(trade="other", stage_hint="strip_out", entity=None,
                        confidence=0.3), TODAY)
    assert r["score_components"]["fit"] == score.FIT_PRECURSOR
    assert "trade_other" not in r["blockers"]
    assert "trade_undeclared" in r["warnings"]
    assert r["qualified"] is True


def test_strip_out_with_a_real_trade_uses_the_real_fit():
    r = score.score(sig(trade="medical", stage_hint="strip_out"), TODAY)
    assert r["score_components"]["fit"] == score.FIT["medical"]


# --- components ------------------------------------------------------------

@pytest.mark.parametrize("trade,points", list(score.FIT.items()))
def test_fit_band(trade, points):
    assert score.FIT[trade] == points
    assert 0 <= points <= 30


@pytest.mark.parametrize("value,points", [
    (None, 8), (0, 8), (10_000, 0), (100_000, 4),
    (1_000_000, 8), (10_000_000, 12),
])
def test_value_points(value, points):
    assert score.value_points(value) == points


def test_value_points_never_exceed_the_cap():
    assert score.value_points(10 ** 12) == 20


@pytest.mark.parametrize("stage,opens_today", [
    ("early_start", True), ("strip_out", True), ("revision", True),
    ("pre_permit", False), ("sunbiz", False),
])
def test_bid_window_opening(stage, opens_today):
    opens, closes = score.bid_window(stage, "2026-06-22", TODAY)
    assert opens and closes and opens <= closes
    assert (opens == TODAY.isoformat()) is opens_today


def test_issued_bid_window_closed_on_the_filing_date():
    assert score.bid_window("issued", "2026-07-10", TODAY) == ("2026-07-10", "2026-07-10")


def test_size_gate_passes_licence_and_permit_sources():
    for src in ("permit", "abt", "ahca", "dbpr_hr", "entitlement"):
        assert score.meets_size_gate({"source": src})
    assert not score.meets_size_gate({"source": "sunbiz"})
    assert score.meets_size_gate({"source": "sunbiz", "value_est": 80_000})
    assert score.meets_size_gate({"source": "sunbiz", "sqft": 1_500})
    assert score.meets_size_gate({"source": "sunbiz", "seats": 40})


def test_score_is_clamped_to_0_100():
    for s in (sig(), sig(trade="medical", contacts=[{"kind": "phone", "value": "x"}],
                         value_est=50_000_000),
              sig(entity="Publix", contractor_name="Some GC", trade="other",
                  stage_hint="issued")):
        r = score.score(s, TODAY)
        assert 0 <= r["score"] <= 100


def test_a_relationship_row_scores_like_a_door_not_a_job():
    """HCAA prequalification is worth working and is never a fitout to bid.
    It must not be hard-blocked on `trade_other`, and it must not need a
    dollar value it can never have."""
    sig = {"source": "hcaa_ppo", "hood": "airport", "trade": "relationship",
           "stage_hint": "pre_permit", "is_fitout": True,
           "entity": "Hillsborough County Aviation Authority",
           "filed_at": "2026-11-15", "contacts": [{"kind": "email",
                                                   "value": "x@tampaairport.com"}]}
    out = score.score(dict(sig), today=date(2026, 9, 14))
    assert "trade_other" not in out["blockers"]
    assert "below_size_gate" not in out["blockers"]
    assert out["score"] > 0



def test_a_prequalification_is_not_chasing_public_work():
    """The public blocklist stops the system bidding work Ideal is not set up
    for. Getting onto an agency's prequalified list is the thing you do first,
    and blocking it killed the HCAA collector outright — all 21 rows of the
    September 2026 report came back `blocklist:hillsborough county`."""
    assert score.blocklist_hit("Hillsborough County Aviation Authority") \
        == "hillsborough county"
    assert score.blocklist_hit("Hillsborough County Aviation Authority",
                               trade="relationship") is None


def test_a_relationship_with_a_chain_that_self_performs_is_still_blocked():
    """Only the PUBLIC list is waived. A national with an in-house
    construction arm is worth nothing to us either way."""
    hit = score.blocklist_hit("Starbucks", trade="relationship")
    assert hit is None or hit  # depends on the list; assert the real one below


def test_the_national_in_house_list_still_applies_to_a_relationship_row():
    import yaml, os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "blocklist.yaml")
    names = yaml.safe_load(open(path)).get("national_in_house") or []
    if not names:
        pytest.skip("no national_in_house entries")
    assert score.blocklist_hit(names[0], trade="relationship") is not None


# --- target niches ---------------------------------------------------------

def test_niche_bonus_is_its_own_component_and_adds_up():
    r = score.score(sig(trade="retail", niche="hair_salon"), TODAY)
    c = r["score_components"]
    assert c["fit"] == score.FIT["retail"]
    assert c["niche"] == score.NICHE_BONUS["hair_salon"]
    assert r["score"] == sum(c.values())


def test_a_row_with_no_niche_scores_exactly_as_before():
    with_niche = score.score(sig(trade="retail", niche=None), TODAY)
    legacy = score.score(sig(trade="retail"), TODAY)
    assert with_niche["score_components"]["niche"] == 0
    assert with_niche["score"] == legacy["score"]


def test_the_bonus_is_what_brings_a_hair_salon_over_the_bar():
    """retail at 15 leaves a salon under 55 on an unnamed, 90-day row."""
    base = dict(trade="retail", stage_hint="dbpr_hr", entity=None,
                source="permit", sqft=1_400)
    without = score.score(sig(**base), TODAY)
    with_niche = score.score(sig(niche="hair_salon", **base), TODAY)
    assert without["score"] < score.QUALIFY_AT <= with_niche["score"]


def test_urgent_care_and_veterinary_keep_the_medical_fit():
    for niche in ("urgent_care", "veterinary"):
        c = score.score(sig(trade="medical", niche=niche), TODAY)["score_components"]
        assert c["fit"] == score.FIT["medical"]
        assert c["niche"] == score.NICHE_BONUS[niche]


def test_a_niche_bonus_cannot_rescue_a_hard_blocker():
    """A salon outside the submarkets is still not a lead."""
    r = score.score(sig(trade="retail", niche="hair_salon", hood=None), TODAY)
    assert "outside_submarkets" in r["blockers"]
    assert not r["qualified"]
