"""
End-to-end demo / self-test for issued-permit lead generation.

Runs the full lead pipeline against canned portal responses (no browser, no
network, no database):

    python -m permit_scraper.leads.demo

Proves:
  1. Only ISSUED commercial/residential *projects* become leads — trade noise
     (re-roofs, water heaters), non-issued permits, and sub-floor values are
     filtered out.
  2. Each lead carries the GC-of-record and owner as contacts, pulled from the
     permit fields OR (fallback) the raw detail data.
  3. The CSV call-list is written with the right columns.
  4. Re-running is idempotent — no duplicate leads.

Exit code 0 = all assertions passed.
"""
from __future__ import annotations

import csv
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from permit_scraper.scrapers.base import RawPermit  # noqa: E402
from permit_scraper.leads import (  # noqa: E402
    LeadClassifier,
    LeadConfig,
    LeadPipeline,
    LeadStore,
)
from permit_scraper.leads.models import DEFAULT_EXCLUDE_KEYWORDS  # noqa: E402
from permit_scraper.leads.enrichment import (  # noqa: E402
    DBPRDataFileEnricher,
    EnrichmentCache,
    EnrichmentManager,
    PropertyAppraiserEnricher,
)

COUNTY = {"id": "pasco_county", "name": "Pasco County, FL", "type": "accela"}
d = datetime


def _p(num, ptype, status, desc, value, **kw) -> RawPermit:
    return RawPermit(
        source_id=num, county_id="pasco_county", county_name="Pasco County, FL",
        permit_number=num, permit_type=ptype, status=status, description=desc,
        estimated_value=value, city="Wesley Chapel", state="FL", zip_code="33544",
        source_url=f"https://aca-prod.accela.com/PASCO/permit/{num}",
        **kw,
    )


CANNED = [
    # 1) Issued commercial new construction — QUALIFIES (GC + owner on fields)
    _p("BD-2026-011001", "Commercial New Construction", "Permit Issued",
       "New 52,600 SF supermarket — Epperson Ranch", 7_400_000,
       contractor_name="Welbro Building Corporation", contractor_license="CGC012345",
       owner_name="Publix Realty LLC", owner_mailing_address="PO Box 407, Lakeland, FL 33802",
       address="7800 Epperson Blvd", issued_date=d(2026, 7, 10)),

    # 2) Issued residential new home — QUALIFIES (GC license + owner mailing via raw_data)
    _p("BD-2026-011002", "Residential New Construction", "Issued",
       "New single-family residence 3,150 SF custom home", 460_000,
       contractor_name="Lennar Homes LLC",
       address="4100 Tour Trace",
       raw_data={"state license": "CBC059752",
                 "owner mailing address": "700 NW 107th Ave, Miami, FL 33172",
                 "owner": "John & Mary Homeowner"},
       owner_name="John & Mary Homeowner", issued_date=d(2026, 7, 12)),

    # 3) Issued residential RE-ROOF — excluded (trade noise)
    _p("BD-2026-011003", "Residential Reroof", "Permit Issued",
       "Re-roof existing SFR, architectural shingle", 18_500,
       contractor_name="Bob's Roofing Inc", address="123 Palm St"),

    # 4) Issued water heater — excluded (trade noise)
    _p("BD-2026-011004", "Plumbing", "Issued",
       "Water heater replacement 50 gal", 1_800,
       contractor_name="QuickPlumb LLC", address="55 Oak Ave"),

    # 5) Commercial in plan review — excluded (not issued)
    _p("BD-2026-011005", "Commercial New Construction", "Plan Review",
       "New 24,000 SF retail strip center", 5_600_000,
       contractor_name="ABC Constructors", address="900 SR-56"),

    # 6) Commercial finaled — excluded (phase past 'issued')
    _p("BD-2026-011006", "Commercial New Construction", "Certificate of Occupancy Issued",
       "New 12,000 SF medical office", 3_100_000,
       contractor_name="MedBuild Inc", address="200 Wellness Way"),

    # 7) Issued commercial but below the $100k commercial floor — excluded (value)
    _p("BD-2026-011007", "Commercial Alteration", "Issued",
       "Interior commercial alteration, paint & partitions", 55_000,
       contractor_name="Small Jobs Co", address="12 Plaza Ct"),

    # 8) Issued residential new home below the $150k residential floor — excluded (value)
    _p("BD-2026-011008", "Residential New Construction", "Issued",
       "New single-family residence, modest", 120_000,
       contractor_name="Budget Homes LLC", address="8 Cottage Ln"),
]


class _FakeScraper:
    def __init__(self, permits):
        self._permits = permits

    def scrape(self, days_back=30, permit_types=None):
        return self._permits


def _factory(county_cfg):
    return _FakeScraper(CANNED)


def _check(msg, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    if not ok:
        raise AssertionError(msg)


def _config() -> LeadConfig:
    return LeadConfig(
        include_categories=["commercial", "residential", "industrial"],
        qualifying_phases=["issued"],
        exclude_keywords=list(DEFAULT_EXCLUDE_KEYWORDS),
        min_value={"commercial": 100_000, "residential": 150_000, "industrial": 250_000},
        issued_within_days=None,
    )


def scenario_pipeline():
    print("\n=== Scenario 1: scan issued permits → CSV call-list ===")
    tmp = Path(tempfile.mkdtemp())
    csv_path = tmp / "leads.csv"
    store = LeadStore(tmp / "state.json")
    pipe = LeadPipeline(config=_config(), store=store, counties=[COUNTY], scraper_factory=_factory)

    s = pipe.run(days_back=30, csv_path=csv_path)
    _check("scanned all 8 canned permits", s["permits_scanned"] == 8)
    _check("exactly 2 qualified (issued commercial NC + residential home)", s["qualified"] == 2)
    _check("2 new leads emitted", s["new_leads"] == 2)
    _check("CSV written", csv_path.exists())

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    _check("CSV has 2 data rows", len(rows) == 2)
    by_permit = {r["permit_number"]: r for r in rows}

    r1 = by_permit["BD-2026-011001"]
    _check("commercial lead categorised commercial", r1["category"] == "commercial")
    _check("commercial lead has GC name", r1["gc_name"] == "Welbro Building Corporation")
    _check("commercial lead has GC license", r1["gc_license"] == "CGC012345")
    _check("commercial lead has owner mailing", "Lakeland" in r1["owner_mailing_address"])

    r2 = by_permit["BD-2026-011002"]
    _check("residential lead categorised residential", r2["category"] == "residential")
    _check("GC license recovered from raw_data (fallback)", r2["gc_license"] == "CBC059752")
    _check("owner mailing recovered from raw_data (fallback)",
           "107th Ave" in r2["owner_mailing_address"])
    _check("portal URL carried through", r2["portal_url"].endswith("BD-2026-011002"))

    print("\n=== Scenario 2: re-run is idempotent (dedupe) ===")
    s2 = pipe.run(days_back=30, csv_path=csv_path)
    _check("second run finds the same 2 as duplicates", s2["duplicates"] == 2)
    _check("second run emits 0 new leads", s2["new_leads"] == 0)
    rows2 = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    _check("CSV still has only 2 rows (no dup append)", len(rows2) == 2)


def scenario_classifier():
    print("\n=== Scenario 3: categorisation & noise filtering ===")
    clf = LeadClassifier(_config())
    warehouse = _p("W1", "Industrial", "Issued", "New 320,000 SF distribution warehouse", 28_000_000)
    _check("warehouse → industrial", clf.categorize(warehouse) == "industrial")
    _check("warehouse qualifies", clf.qualifies(warehouse)[0] is True)

    reroof = _p("R1", "Reroof", "Issued", "Re-roof shingle", 20_000)
    _check("re-roof flagged as noise", clf.is_noise(reroof) is True)

    nc_with_roof = _p("N1", "Commercial New Construction", "Issued",
                      "New construction incl. roofing and mechanical", 2_000_000)
    _check("new construction w/ trade words is NOT noise", clf.is_noise(nc_with_roof) is False)

    not_issued = _p("P1", "Commercial New Construction", "Application Received",
                    "New retail", 2_000_000)
    _check("application-received does not qualify", clf.qualifies(not_issued)[0] is False)


_DBPR_EXTRACT = """\
License Number,Name (Last First),DBA Name,License Type,Primary Status,Secondary Status,Address 1,City,State,Zip,Expiration Date
CGC012345,WELBRO BUILDING CORPORATION,,Certified General Contractor,Current,Active,1000 Legion Pl,Orlando,FL,32801,08/31/2026
CBC059752,LENNAR HOMES LLC,,Certified Building Contractor,Current,Active,730 NW 107th Ave,Miami,FL,33172,08/31/2027
"""

# County configs for the enrichment scenario.
_H = {"id": "hillsborough_county", "name": "Hillsborough County, FL", "type": "accela"}
_P = {"id": "pasco_county", "name": "Pasco County, FL", "type": "accela"}


def _ep(num, county, contractor, license_, owner, value, parcel, owner_mailing=None):
    cfg = {"hillsborough_county": _H, "pasco_county": _P}[county]
    return RawPermit(
        source_id=num, county_id=county, county_name=cfg["name"],
        permit_number=num, permit_type="Commercial New Construction", status="Permit Issued",
        description="New commercial building", estimated_value=value,
        contractor_name=contractor, contractor_license=license_,
        owner_name=owner, owner_mailing_address=owner_mailing, parcel_number=parcel,
        address="100 Job Site Rd", city="Tampa", state="FL", zip_code="33601",
        source_url=f"https://portal.example.gov/{num}",
    )


def scenario_enrichment():
    print("\n=== Scenario 4: DBPR + property-appraiser contact enrichment ===")
    tmp = Path(tempfile.mkdtemp())
    extract = tmp / "dbpr.csv"
    extract.write_text(_DBPR_EXTRACT, encoding="utf-8")

    # Injected appraiser lookup (no network) — records how often it's called.
    calls = {"n": 0}
    mailing = {"U-1234": "PO BOX 111, TAMPA, FL 33601", "U-5678": "PO BOX 222, TAMPA, FL 33602"}

    def fake_lookup(county_id, parcel, owner_name):
        calls["n"] += 1
        addr = mailing.get(parcel)
        return type("P", (), {"mailing_address": addr})() if addr else None

    dbpr = DBPRDataFileEnricher(extract)
    appraiser = PropertyAppraiserEnricher(
        counties=["hillsborough_county", "pasco_county"], lookup_fn=fake_lookup
    )
    manager = EnrichmentManager(
        enrichers=[dbpr, appraiser], cache=EnrichmentCache(tmp / "cache.json")
    )

    permits = [
        # GC on DBPR, owner mailing missing → both enrichers fire
        _ep("EP-1", "hillsborough_county", "Welbro Building Corporation", "CGC012345",
            "Publix Realty LLC", 7_400_000, "U-1234"),
        # SAME GC (cache hit) + different parcel
        _ep("EP-2", "hillsborough_county", "Welbro Building Corporation", "CGC012345",
            "Another Owner LLC", 3_000_000, "U-5678"),
        # Owner mailing already present → appraiser must NOT be called for it
        _ep("EP-3", "pasco_county", "Lennar Homes LLC", "CBC059752",
            "John Homeowner", 460_000, "P-9", owner_mailing="999 Existing St, Land O Lakes FL"),
    ]

    def factory(county_cfg):
        matching = [p for p in permits if p.county_id == county_cfg["id"]]
        return _FakeScraper(matching)

    store = LeadStore(tmp / "state.json")
    csv_path = tmp / "leads.csv"
    pipe = LeadPipeline(config=_config(), store=store, counties=[_H, _P],
                        scraper_factory=factory, enricher=manager)
    s = pipe.run(days_back=30, csv_path=csv_path)

    _check("3 new leads emitted", s["new_leads"] == 3)
    _check("all 3 were enriched", s["enriched"] == 3)

    rows = {r["permit_number"]: r for r in csv.DictReader(open(csv_path, encoding="utf-8"))}
    r1 = rows["EP-1"]
    _check("EP-1 GC business address from DBPR", "Orlando" in r1["gc_address"] and "Legion" in r1["gc_address"])
    _check("EP-1 GC license type from DBPR", r1["gc_license_type"] == "Certified General Contractor")
    _check("EP-1 GC license status from DBPR", "Current" in r1["gc_license_status"])
    _check("EP-1 owner mailing from appraiser", "PO BOX 111" in r1["owner_mailing_address"])
    _check("EP-1 records both enrichment sources",
           "dbpr_datafile" in r1["enriched_from"] and "property_appraiser" in r1["enriched_from"])

    r3 = rows["EP-3"]
    _check("EP-3 keeps permit-provided owner mailing (fields win)",
           r3["owner_mailing_address"].startswith("999 Existing St"))
    _check("EP-3 GC (Lennar) still enriched from DBPR", "Miami" in r3["gc_address"])

    _check("appraiser lookup called only for the 2 missing-owner leads", calls["n"] == 2)
    _check("DBPR result cached for repeated GC (>=1 cache hit)", manager.cache_hits >= 1)


def main() -> int:
    print("Issued-permit lead-generation demo (no browser / network / DB)")
    try:
        scenario_pipeline()
        scenario_classifier()
        scenario_enrichment()
    except AssertionError as exc:
        print(f"\n✗ DEMO FAILED: {exc}")
        return 1
    print("\n✓ All lead-generation scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
