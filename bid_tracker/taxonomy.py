"""Controlled vocabularies. schema.sql CHECK constraints and the validator both use these lists."""

from __future__ import annotations

# code, work_class, label, phase1_core
PROJECT_TYPES = [
    ("V-TI", "vertical", "Interior buildout / tenant improvement", 1),
    ("V-REN", "vertical", "Renovation / remodel of existing building", 1),
    ("V-ADA", "vertical", "ADA / restroom renovation", 1),
    ("V-NEW-S", "vertical", "New building <= 20,000 GSF", 1),
    ("V-NEW-L", "vertical", "New building > 20,000 GSF", 0),
    ("V-ENV", "vertical", "Roof / windows / envelope hardening", 0),
    ("V-MEP", "vertical", "MEP-led renovation (HVAC, electrical, plumbing)", 0),
    ("R-WATER", "restoration", "Water mitigation / structural drying", 1),
    ("R-MOLD", "restoration", "Mold remediation", 1),
    ("R-FIRE", "restoration", "Fire and smoke restoration", 1),
    ("R-MULTI", "restoration", "Disaster remediation term contract (multi-service)", 1),
    ("R-ABATE", "restoration", "Asbestos / lead abatement", 0),
    ("H-ROAD", "horizontal", "Roadway / paving", 0),
    ("H-UTIL", "horizontal", "Water, sewer, storm utilities", 0),
    ("H-SITE", "horizontal", "Site work / parks / sidewalks", 0),
]
PROJECT_TYPE_CODES = {p[0] for p in PROJECT_TYPES}
WORK_CLASSES = ("vertical", "restoration", "horizontal")

AGENCY_TYPES = (
    "city", "county", "school_district", "airport", "port", "university",
    "state", "special_district", "federal", "other",
)
PROCUREMENT_METHODS = ("ITB", "RFP", "RFQ", "JOC", "CMAR", "DB", "term_contract", "emergency", "other")
AWARD_BASIS = ("low_bid", "best_value", "qualifications", "rate_card")
EE_SOURCES = ("ee", "budget", "not_published")
GSF_BASIS = ("stated", "measured", "derived")
AWARD_STATUS = ("open", "opened", "recommended", "awarded", "rejected_all", "cancelled", "unknown")
TOTAL_BASIS = ("base", "base+all_alts", "base+accepted_alts", "as_tabulated", "rate_card")
RATE_SERVICES = (
    "water", "mold", "fire", "smoke", "sewage", "dryout", "demo", "contents",
    "board_up", "labor_hourly", "equipment_daily", "other",
)
PURSUIT_DECISIONS = ("go", "no_go", "pending")
PURSUIT_RESULTS = ("won", "lost", "no_bid", "rejected", "pending", "cancelled")
FEEDS = ("weekday", "weekly", "manual")

# Higher number wins when two sources describe the same solicitation.
EVIDENCE_RANK = {
    "official_tab": 6,
    "board_award_item": 5,
    "portal_award_notice": 4,
    "news": 3,
    "search_snippet": 2,   # number quoted from a search-result snippet of the source; page not fetched
    "internal": 1,
}
EVIDENCE_CLASSES = tuple(EVIDENCE_RANK)
# Which event bid_open_date actually records when the opening date itself isn't published.
DATE_BASIS = ("bid_open", "award", "board", "posted")

# GSF bands for vertical work; dollar bands when GSF is unknown.
GSF_BANDS = [(0, 2500, "<2.5k sf"), (2500, 10000, "2.5-10k sf"), (10000, 25000, "10-25k sf"), (25000, None, ">=25k sf")]
DOLLAR_BANDS = [(0, 300_000, "<$300k"), (300_000, 1_000_000, "$300k-1M"), (1_000_000, 5_000_000, "$1-5M"), (5_000_000, None, ">=$5M")]


GSF_BAND_LABELS = {b[2] for b in GSF_BANDS}
DOLLAR_BAND_LABELS = {b[2] for b in DOLLAR_BANDS}


def band_kind(label: str | None) -> str | None:
    """'gsf_band' or 'dollar_band' for a size-band label."""
    if label in GSF_BAND_LABELS:
        return "gsf_band"
    if label in DOLLAR_BAND_LABELS:
        return "dollar_band"
    return None


def size_band(gsf: float | None, low_bid: float | None) -> str | None:
    """GSF band when floor area is known, otherwise a dollar band on the low bid."""
    if gsf:
        bands, value = GSF_BANDS, gsf
    elif low_bid:
        bands, value = DOLLAR_BANDS, low_bid
    else:
        return None
    for lo, hi, label in bands:
        if value >= lo and (hi is None or value < hi):
            return label
    return None


# All 67 Florida counties, grouped into the regions the benchmarks roll up to.
REGION_COUNTIES = {
    "tampa_bay": ["Hillsborough", "Pinellas", "Pasco", "Polk", "Manatee", "Sarasota", "Hernando", "Citrus"],
    "central": ["Orange", "Osceola", "Seminole", "Lake", "Volusia", "Brevard", "Sumter", "Marion"],
    "southwest": ["Lee", "Collier", "Charlotte", "Hendry", "Glades", "DeSoto", "Hardee", "Highlands"],
    "southeast": ["Miami-Dade", "Broward", "Palm Beach", "Monroe", "Martin", "St. Lucie", "Indian River", "Okeechobee"],
    "northeast": ["Duval", "St. Johns", "Clay", "Nassau", "Baker", "Putnam", "Flagler"],
    "north_central": [
        "Alachua", "Columbia", "Suwannee", "Hamilton", "Lafayette", "Madison",
        "Taylor", "Dixie", "Gilchrist", "Levy", "Union", "Bradford",
    ],
    "panhandle": [
        "Escambia", "Santa Rosa", "Okaloosa", "Walton", "Holmes", "Washington", "Bay", "Jackson",
        "Calhoun", "Gulf", "Liberty", "Franklin", "Gadsden", "Leon", "Wakulla", "Jefferson",
    ],
}
REGIONS = tuple(REGION_COUNTIES) + ("statewide", "other")
COUNTY_REGION = {c.lower(): r for r, cs in REGION_COUNTIES.items() for c in cs}


def region_for(county: str | None) -> str | None:
    if not county:
        return None
    return COUNTY_REGION.get(county.strip().lower().replace(" county", ""))
