"""
Unit tests for the first-pass permit classifier.

Every string below is verbatim from the live City of Tampa PermitsAll layer
(retrieved 2026-09-14) — no invented examples.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import classify  # noqa: E402

# (occupancy_category, project_name2, project_description,
#  expected_trade, expected_stage, expected_entity)
REAL = [
    ("B-9 Business-Professional Office",
     "FEMA: PP: Int. Remodel: Ste 100: AIC Architecture",
     "Interior renovation of Suite 100 for new tenant AIC Architecture. partial expansion",
     "office", "issued", "AIC Architecture"),
    ("A-2 Assembly-Food & Drink. Restaurant. Night Club. Bar",
     "EARLY START: PP:Interior remodel - The Violet Stone Pizzeria",
     "Remodel existing restaurant into the Violet Stone restaurant",
     "restaurant", "early_start", "The Violet Stone Pizzeria"),
    ("A-2 Assembly-Food & Drink. Restaurant. Night Club. Bar",
     "Early Start: THRESH: PP: Interior Remodel: Restaurant - "
     "Wagamama Pan Asian Block F2 Ground Floor", "",
     "restaurant", "early_start", "Wagamama Pan Asian"),
    ("B-10 Business-High Rise Office",
     "THRESHOLD BUILDING Interior Build-Out - Suite 855 - CFS Staffing",
     "CFS Staffing: BUILD-OUT OF SUITE 855 FOR NEW TENANT: CFS STAFFING. "
     "ALTERATIONS INCLUDE MINOR DEMOLITION",
     "office", "issued", "CFS Staffing"),
    ("M-4 Mercantile-Retail or wholesale store",
     "EARLY START: SEC: PP: Int. Remodel: Edikted STE :125",
     "Interior tenant improvement within the mall: Suite 125.",
     "retail", "early_start", "Edikted"),
    ("B-10 Business-High Rise Office",
     "SEC: FEMA: Interior ALT (Suite 2200)",
     "Interior alterations to an existing vacant office Suite 2200, for a tenant "
     "(Altieri Ins. Consultants) relocating into this Suite.",
     "office", "revision", "Altieri Ins. Consultants"),
    ("B-10 Business-High Rise Office",
     "EARLY START: BLD-26-526641 Interior Renovation - Coca-Cola Suite 300",
     "THRESHOLD BUILDING Early start for interior, non-structural work ONLY",
     "office", "early_start", "Coca-Cola"),
    ("B-10 Business-High Rise Office",
     "Interior Alteration - 2nd Floor Common Areas",
     "THRESHOLD BUILDING 2nd Floor Common Areas (Meridian Two) - Interior Renovation",
     "office", "issued", None),
    ("B-9 Business-Professional Office",
     "EARLY START: Interior Alteration - Suite 300 - Pike Engineering",
     "Interior Renovation of Suite 300.",
     "office", "early_start", "Pike Engineering"),
    ("B-10 Business-High Rise Office",
     "PP: Int. Remodel: Ste 800: Norlee Group",
     "Renovation of existing full-floor suite for new tenant (Norlee Group)",
     "office", "issued", "Norlee Group"),
    ("R-3 Residential Townhouses",
     "Fema: PP: Int. Kitchen & Bath Remodel: Unit 804",
     "SUNDHOLM - KITCHEN & BATH REMODEL Unit 804",
     "other", "issued", None),
    ("R-2 Residential-Permanent. 3+ Dwellings Apartment. Dormitory. Timeshare",
     "FEMA: Bathroom Remodel: Unit 903",
     "Remodel of shower, toilet and vanity in 2nd bath.",
     "other", "issued", None),
    ("B-9 Business-Professional Office",
     "TIA PROJECT:  Interior/Exterior Alterations - Tampa Police Aviation Office",
     "Interior Office Renovation at the Tampa Police Aviation Facility.",
     "office", "issued", "Tampa Police Aviation Office"),
    ("A-3 Assembly-Worship. Amusement. Arcade. Church. Community Hall",
     "SEC: FEMA: PP: THRESHOLD: Sea Lion and Penguin Exhibits",
     "New outdoor exhibits housing Sea Lions and Penguins.",
     "other", "issued", "Sea Lion and Penguin Exhibits"),
    ("", "Demo 2-Story Buildings",
     "Demolition of (2) two story wood framed office buildings.",
     "other", "issued", None),
    ("B-9 Business-Professional Office",
     "FEMA: PP: SEC: Interior Reno suite 103",
     "THE PROPOSED SCOPE OF WORK CONSISTS OF THE INTERIOR RENOVATION OF AN "
     "EXISTING COMMERCIAL SHOWER ROOM INTO APPROXIMATELY 400 SQUARE FEET",
     "office", "issued", None),
    ("M-4 Mercantile-Retail or wholesale store",
     "PP:Interior Alterations - Designers Closet",
     "ALTERATION OF AN EXISTING RETAIL TENANT SPACE WITHIN SHOPPING CENTER",
     "retail", "issued", "Designers Closet"),
    ("B-9 Business-Professional Office",
     "SEC: TIA PROJECT: Interior Remodel: Fly USA Hangar 4300",
     "INTERIOR IMPROVEMENTS TO 4870 SF IN A 59,470 SF BUILDING",
     "office", "issued", "Fly USA"),
]

IDS = [f"{i}-{row[1][:28] or 'blank'}" for i, row in enumerate(REAL)]


def _record_type(name2: str, desc: str) -> str:
    return ("Commercial Demolition Permit" if name2.lower().startswith("demo")
            else "Commercial Building Alterations (Renovations)")


@pytest.mark.parametrize("occ,name2,desc,trade,stage,entity", REAL, ids=IDS)
def test_trade(occ, name2, desc, trade, stage, entity):
    got, conf = classify.trade_of(occ, name2, desc,
                                  record_type=_record_type(name2, desc))
    assert got == trade
    assert 0.0 <= conf <= 1.0


@pytest.mark.parametrize("occ,name2,desc,trade,stage,entity", REAL, ids=IDS)
def test_stage(occ, name2, desc, trade, stage, entity):
    status = "Revision" if stage == "revision" else "Issued"
    assert classify.stage_of(status, name2, desc) == stage


@pytest.mark.parametrize("occ,name2,desc,trade,stage,entity", REAL, ids=IDS)
def test_entity(occ, name2, desc, trade, stage, entity):
    assert classify.entity_of(name2, desc) == entity


def test_trade_precision_on_the_real_sample():
    """PLAN.md Phase 1 gate: precision >= 0.8 for `trade`."""
    hits = sum(classify.trade_of(o, n, d, record_type=_record_type(n, d))[0] == t
               for o, n, d, t, _, _ in REAL)
    assert hits / len(REAL) >= 0.8


def test_entity_never_returns_scope_language():
    """A wrong name is worse than no name — it gets read out on a cold call."""
    for occ, name2, desc, _, _, _ in REAL:
        got = classify.entity_of(name2, desc)
        if got is not None:
            assert not classify._NOT_A_NAME.match(got), got
            assert not got[0].isdigit(), got


def test_occupancy_code_parsing():
    assert classify.occupancy_code("B-10 Business-High Rise Office") == "B-10"
    assert classify.occupancy_code("R-3A Dwellings-Custom Homes") == "R-3A"
    assert classify.occupancy_code("") is None
    assert classify.occupancy_code(None) is None
    assert classify.occupancy_code("CSTR") is None


def test_every_occupancy_code_in_the_live_vocabulary_is_mapped():
    """Guards against a new FBC category silently becoming `other`."""
    observed = [
        "R-3A", "R-2", "B-9", "R-3D", "A-2", "R-3", "B-10", "M-4", "A-3", "B-5",
        "S-2A", "M-2", "R-1", "S-1A", "R-3B", "S-2C", "F-1", "I-2", "I-1", "A-4",
        "E-1", "F-2", "S-1B", "B-4", "U-3", "A-1", "U-2", "R-3C", "B-3", "B-8",
        "B-2", "M-3", "I-4", "M-1", "E-2", "B-1", "B-7", "A-5", "S-2B", "R-4",
    ]
    missing = [c for c in observed if c not in classify.OCCUPANCY_TRADE]
    assert not missing, f"unmapped occupancy codes: {missing}"


ALT = "Commercial Building Alterations (Renovations)"


def test_record_type_gates():
    assert classify.is_fitout(ALT)
    assert classify.is_fitout("Commercial New Construction and Additions")
    assert not classify.is_fitout("Commercial Demolition Permit")
    assert not classify.is_fitout("Residential New Construction and Additions (1 and 2 Family)")
    assert classify.is_commercial("Commercial Demolition Permit")
    assert not classify.is_commercial(None)


@pytest.mark.parametrize("occ,fitout", [
    # A condo kitchen remodel files under a commercial record type because the
    # building is a threshold high-rise. It is not a job a GC bids.
    ("R-2 Residential-Permanent. 3+ Dwellings Apartment. Dormitory. Timeshare", False),
    ("R-3 Residential Townhouses", False),
    ("R-3A Dwellings-Custom Homes", False),
    ("R-1 Residential-Transient Boarding Houses. Hotels. Motels", True),   # hotel
    ("R-4 Residential-Assisted Living (6-16 persons)", True),              # care facility
    ("B-9 Business-Professional Office", True),
    ("A-2 Assembly-Food & Drink. Restaurant. Night Club. Bar", True),
    ("", True),
    (None, True),
])
def test_dwelling_occupancies_are_not_fitouts(occ, fitout):
    assert classify.is_fitout(ALT, occ) is fitout


@pytest.mark.parametrize("name2,expected", [
    ("INT. Remodel STE 250 (Nationwide)", "Nationwide"),
    ("Interior Alteration (Suite 2200)", None),
])
def test_trailing_parenthetical_brand(name2, expected):
    assert classify.entity_of(name2, "") == expected


@pytest.mark.parametrize("name2,expected", [
    ("EARLY START: THRESHOLD FEMA: PP: Renovation-Interior/Exterior",
     "Renovation-Interior/Exterior"),
    ("Fema: PP: Int. Kitchen & Bath Remodel: Unit 804",
     "Int. Kitchen & Bath Remodel: Unit 804"),
    ("", None),
])
def test_scope_label_strips_administrative_prefixes(name2, expected):
    assert classify.scope_label(name2, None) == expected


# --- strip-outs ------------------------------------------------------------

STRIP_OUT_REAL = (
    "Suite 100: Interior Demolition",
    "Interior demolition of existing lease space, to include demolition of "
    "partitions, ceilings, and fixtures. Remodel permit for build back to be "
    "pulled under separate permit.",
)

NOT_STRIP_OUT = [
    # An ordinary fitout that happens to include selective demolition.
    ("SEC: FEMA: Interior ALT (Suite 2200)",
     "Interior alterations to an existing vacant office Suite 2200, for a tenant "
     "relocating into this Suite. work will include selective demolition of "
     "partitions, millwork and ceiling elements. And the construction of new "
     "partitions"),
    ("INT. Remodel STE 250 (Nationwide)",
     "THRESHOLD BUILDING Ste 250: Demolition of existing partitions and "
     "installation of new millwork"),
    ("THRESHOLD BUILDING Interior Build-Out - Suite 855 - CFS Staffing",
     "BUILD-OUT OF SUITE 855. ALTERATIONS INCLUDE MINOR DEMOLITION, CONSTRUCTION "
     "OF NEW INTERIOR PARTITIONS"),
    ("Demo 2-Story Buildings", "Demolition of (2) two story wood framed office buildings."),
]


def test_strip_out_is_detected_when_the_record_says_build_back_is_separate():
    assert classify.is_strip_out(*STRIP_OUT_REAL)
    assert classify.stage_of("Issued", *STRIP_OUT_REAL) == "strip_out"


def test_strip_out_declares_no_trade():
    """Saying `office` because the word appears in a strip-out scope is a guess."""
    trade, conf = classify.trade_of(
        "A-3 Assembly-Worship. Amusement. Arcade. Church. Community Hall",
        *STRIP_OUT_REAL, record_type=ALT)
    assert trade == "other"
    assert conf < 0.5


@pytest.mark.parametrize("name2,desc", NOT_STRIP_OUT,
                         ids=[n[:30] for n, _ in NOT_STRIP_OUT])
def test_ordinary_fitouts_are_not_mistaken_for_strip_outs(name2, desc):
    """A false positive here demotes a real fitout's trade to `other` and
    loses the lead — costlier than missing a strip-out."""
    assert not classify.is_strip_out(name2, desc)


def test_early_start_wins_over_strip_out():
    name2, desc = "EARLY START: " + STRIP_OUT_REAL[0], STRIP_OUT_REAL[1]
    assert classify.stage_of("Issued", name2, desc) == "early_start"
