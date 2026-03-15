"""
Demo test — runs the full pipeline against a realistic Central West FL
permit dataset and exports results to CSV.

The permit records below are modelled on actual filings in Hillsborough,
Tampa, and Pasco counties: real street addresses, real company filing
names (including subsidiaries), real permit types and value ranges.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys, os

# Make sure we can import from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from permit_scraper.storage import init_db, get_session, Permit
from permit_scraper.scrapers.base import RawPermit
from permit_scraper.agents.classifier import CompanyMatcher, PermitClassifier
import yaml

# ── Realistic Central West FL permit data ───────────────────────────────────
# Filing names, addresses, and values modelled on real permit records from
# Hillsborough, City of Tampa, and Pasco County portals.

SAMPLE_PERMITS = [
    # ── Hillsborough County ──────────────────────────────────────────────
    RawPermit(
        source_id="HCFL-2024-BC-018844",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2024-018844", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Vadata Inc",
        owner_name="Vadata Inc",
        contractor_name="Whiting-Turner Contracting Co",
        description="New 1,050,000 SF fulfillment center - Class A tilt-wall construction",
        address="7850 East Adamo Dr", city="Tampa", state="FL", zip_code="33619",
        parcel_number="U-09-29-19-ZZZ-000000-00000",
        estimated_value=148_000_000, total_sqft=1_050_000,
        filed_date=datetime.now() - timedelta(days=12),
    ),
    RawPermit(
        source_id="HCFL-2024-BC-019102",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2024-019102", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Brasfield & Gorrie LLC",
        description="New 49,200 SF supermarket with pharmacy and fuel center",
        address="12301 Boyette Rd", city="Riverview", state="FL", zip_code="33569",
        parcel_number="U-27-30-20-ZZZ-000000-11100",
        estimated_value=6_800_000, total_sqft=49_200,
        filed_date=datetime.now() - timedelta(days=5),
    ),
    RawPermit(
        source_id="HCFL-2024-BC-017756",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2024-017756", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Wal-Mart Stores East LP",
        owner_name="Walmart Real Estate Business Trust",
        contractor_name="Harkins Builders Inc",
        description="New 152,000 SF Walmart Supercenter with garden center and tire/lube",
        address="10120 Gibsonton Dr", city="Gibsonton", state="FL", zip_code="33534",
        parcel_number="U-01-31-19-ZZZ-000000-99900",
        estimated_value=18_400_000, total_sqft=152_000,
        filed_date=datetime.now() - timedelta(days=21),
    ),
    RawPermit(
        source_id="HCFL-2024-BC-020011",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2024-020011", permit_type="Commercial Addition",
        status="Permit Issued",
        applicant_name="Home Depot USA Inc",
        owner_name="Home Depot USA Inc",
        contractor_name="Coreslab Structures Inc",
        description="52,000 SF garden center expansion and warehouse addition",
        address="8701 N Dale Mabry Hwy", city="Tampa", state="FL", zip_code="33614",
        parcel_number="U-10-28-18-ZZZ-000000-44400",
        estimated_value=4_200_000, total_sqft=52_000,
        filed_date=datetime.now() - timedelta(days=8),
    ),
    RawPermit(
        source_id="HCFL-2024-BC-018300",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2024-018300", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Prologis USLF III LLC",
        owner_name="Prologis LP",
        contractor_name="Sunbelt Structures Inc",
        description="New 320,000 SF Class A industrial/distribution building — spec",
        address="6400 US Hwy 301 S", city="Gibsonton", state="FL", zip_code="33534",
        parcel_number="U-15-31-19-ZZZ-000000-55500",
        estimated_value=28_500_000, total_sqft=320_000,
        filed_date=datetime.now() - timedelta(days=18),
    ),
    RawPermit(
        source_id="HCFL-2024-BC-019500",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2024-019500", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Chick-fil-A Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Axiom Construction Inc",
        description="New 4,850 SF Chick-fil-A restaurant with drive-through",
        address="2201 Bloomingdale Ave", city="Brandon", state="FL", zip_code="33596",
        parcel_number="U-22-30-20-ZZZ-000000-33300",
        estimated_value=2_100_000, total_sqft=4_850,
        filed_date=datetime.now() - timedelta(days=3),
    ),
    RawPermit(
        source_id="HCFL-2024-BC-017900",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2024-017900", permit_type="Residential New Construction",
        status="Permit Issued",
        applicant_name="D.R. Horton Inc",
        owner_name="D.R. Horton Inc",
        contractor_name="D.R. Horton Inc",
        description="New single-family residence 2,450 SF",
        address="14122 Swan Lake Dr", city="Riverview", state="FL", zip_code="33579",
        parcel_number="U-05-31-20-ZZZ-000000-11100",
        estimated_value=310_000, total_sqft=2_450,
        filed_date=datetime.now() - timedelta(days=14),
    ),

    # ── City of Tampa ────────────────────────────────────────────────────
    RawPermit(
        source_id="TAMPA-2024-BLD-044821",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2024-044821", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon.com Services LLC",
        owner_name="Amazon Logistics Inc",
        contractor_name="DPR Construction",
        description="New 95,000 SF last-mile delivery station (DST7)",
        address="4215 E Hillsborough Ave", city="Tampa", state="FL", zip_code="33610",
        parcel_number="A-16-29-19-ZZZ-000000-00220",
        estimated_value=11_200_000, total_sqft=95_000,
        filed_date=datetime.now() - timedelta(days=9),
    ),
    RawPermit(
        source_id="TAMPA-2024-BLD-043100",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2024-043100", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Hensel Phelps Construction Co",
        description="New 160,000 SF Costco warehouse with tire center and fuel station",
        address="4811 W Gandy Blvd", city="Tampa", state="FL", zip_code="33611",
        parcel_number="A-30-29-17-ZZZ-000000-00110",
        estimated_value=21_000_000, total_sqft=160_000,
        filed_date=datetime.now() - timedelta(days=16),
    ),
    RawPermit(
        source_id="TAMPA-2024-BLD-045600",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2024-045600", permit_type="Commercial Tenant Improvement",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Stellar Group Inc",
        description="Full interior renovation 47,500 SF supermarket — new deli, bakery, pharmacy",
        address="1523 S Dale Mabry Hwy", city="Tampa", state="FL", zip_code="33629",
        parcel_number="A-24-29-18-ZZZ-000000-00440",
        estimated_value=3_800_000, total_sqft=47_500,
        filed_date=datetime.now() - timedelta(days=6),
    ),
    RawPermit(
        source_id="TAMPA-2024-BLD-042200",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2024-042200", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Marriott International Inc",
        owner_name="Marriott Hotel Services LLC",
        contractor_name="Suffolk Construction Co",
        description="New 14-story, 312-room Courtyard by Marriott — downtown Tampa",
        address="400 N Ashley Dr", city="Tampa", state="FL", zip_code="33602",
        parcel_number="A-01-29-18-ZZZ-000000-00880",
        estimated_value=54_000_000, total_sqft=210_000,
        filed_date=datetime.now() - timedelta(days=28),
    ),
    RawPermit(
        source_id="TAMPA-2024-BLD-046100",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2024-046100", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="McGough Construction LLC",
        description="New 24,000 SF small-format Target store",
        address="601 N Ashley Dr", city="Tampa", state="FL", zip_code="33602",
        parcel_number="A-01-29-18-ZZZ-000000-00330",
        estimated_value=5_600_000, total_sqft=24_000,
        filed_date=datetime.now() - timedelta(days=4),
    ),
    RawPermit(
        source_id="TAMPA-2024-BLD-043900",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2024-043900", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="McDonalds Corporation",
        owner_name="McDonald's USA LLC",
        contractor_name="Conlan Company",
        description="New 4,200 SF McDonald's restaurant with double drive-through",
        address="5030 W Kennedy Blvd", city="Tampa", state="FL", zip_code="33609",
        parcel_number="A-22-29-17-ZZZ-000000-00660",
        estimated_value=1_850_000, total_sqft=4_200,
        filed_date=datetime.now() - timedelta(days=11),
    ),

    # ── Pasco County ─────────────────────────────────────────────────────
    RawPermit(
        source_id="PASCO-2024-BD-031441",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-031441", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon Logistics Inc",
        owner_name="Vadata Inc",
        contractor_name="Clancy & Theys Construction Co",
        description="New 200,000 SF Amazon delivery station (DSP4) — tilt-wall",
        address="2850 Trouble Creek Rd", city="New Port Richey", state="FL", zip_code="34655",
        parcel_number="13-26-16-0000-00400-0010",
        estimated_value=19_500_000, total_sqft=200_000,
        filed_date=datetime.now() - timedelta(days=7),
    ),
    RawPermit(
        source_id="PASCO-2024-BD-030800",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-030800", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Welbro Building Corporation",
        description="New 52,600 SF supermarket — Epperson Ranch Town Center",
        address="7800 Epperson Blvd", city="Wesley Chapel", state="FL", zip_code="33545",
        parcel_number="20-25-21-0000-00100-0130",
        estimated_value=7_400_000, total_sqft=52_600,
        filed_date=datetime.now() - timedelta(days=10),
    ),
    RawPermit(
        source_id="PASCO-2024-BD-031900",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-031900", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="FedEx Ground Package System Inc",
        owner_name="FedEx Ground Package System Inc",
        contractor_name="Conlan Company",
        description="New 260,000 SF FedEx Ground distribution hub",
        address="29100 SR-54", city="Wesley Chapel", state="FL", zip_code="33543",
        parcel_number="10-26-20-0000-00200-0010",
        estimated_value=31_200_000, total_sqft=260_000,
        filed_date=datetime.now() - timedelta(days=15),
    ),
    RawPermit(
        source_id="PASCO-2024-BD-032100",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-032100", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="Barton Malow Company",
        description="New 135,000 SF Target store with drive-up, Starbucks, CVS pharmacy",
        address="5860 Cypress Ranch Blvd", city="Wesley Chapel", state="FL", zip_code="33544",
        parcel_number="09-26-20-0000-00100-0200",
        estimated_value=15_800_000, total_sqft=135_000,
        filed_date=datetime.now() - timedelta(days=22),
    ),
    RawPermit(
        source_id="PASCO-2024-BD-030200",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-030200", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="CFA Properties Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Axiom Construction Inc",
        description="New 5,100 SF Chick-fil-A with dual drive-through lanes",
        address="2050 Zephyrhills Bypass Rd", city="Zephyrhills", state="FL", zip_code="33540",
        parcel_number="25-26-21-0000-01100-0010",
        estimated_value=2_400_000, total_sqft=5_100,
        filed_date=datetime.now() - timedelta(days=19),
    ),
    RawPermit(
        source_id="PASCO-2024-BD-029800",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-029800", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="United Parcel Service Inc",
        owner_name="UPS Supply Chain Solutions Inc",
        contractor_name="Skanska USA Building Inc",
        description="New 185,000 SF UPS package hub and customer center",
        address="4100 Land O Lakes Blvd", city="Land O Lakes", state="FL", zip_code="34639",
        parcel_number="18-26-19-0000-00500-0010",
        estimated_value=22_000_000, total_sqft=185_000,
        filed_date=datetime.now() - timedelta(days=25),
    ),
    RawPermit(
        source_id="PASCO-2024-BD-031200",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-031200", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Hensel Phelps Construction Co",
        description="New 158,000 SF Costco warehouse — Wiregrass Ranch area",
        address="5500 Wesley Chapel Blvd", city="Wesley Chapel", state="FL", zip_code="33544",
        parcel_number="11-26-20-0000-00300-0010",
        estimated_value=19_500_000, total_sqft=158_000,
        filed_date=datetime.now() - timedelta(days=13),
    ),
    RawPermit(
        source_id="PASCO-2024-BD-033000",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2024-033000", permit_type="Residential New Construction",
        status="Permit Issued",
        applicant_name="Lennar Homes LLC",
        owner_name="Lennar Homes LLC",
        contractor_name="Lennar Homes LLC",
        description="New single-family residence 2,210 SF",
        address="3245 Rustling Oaks Dr", city="Land O Lakes", state="FL", zip_code="34638",
        parcel_number="03-26-18-0000-02200-0010",
        estimated_value=285_000, total_sqft=2_210,
        filed_date=datetime.now() - timedelta(days=2),
    ),
]


def run_demo():
    init_db("sqlite:///demo_permits.db")

    watch_data = yaml.safe_load(
        (Path(__file__).parent / "targets" / "companies.yaml").read_text()
    )
    matcher = CompanyMatcher(watch_data["watch_list"])
    classifier = PermitClassifier(matcher)

    all_matched: list[dict] = []
    all_records: list[dict] = []

    with get_session() as session:
        for raw in SAMPLE_PERMITS:
            enrichment = classifier.classify(raw)

            db = Permit(
                source_id=raw.source_id,
                county_id=raw.county_id, county_name=raw.county_name,
                permit_number=raw.permit_number, permit_type=raw.permit_type,
                status=raw.status, description=raw.description,
                applicant_name=raw.applicant_name, owner_name=raw.owner_name,
                contractor_name=raw.contractor_name,
                address=raw.address, city=raw.city, state=raw.state,
                zip_code=raw.zip_code, parcel_number=raw.parcel_number,
                estimated_value=raw.estimated_value, total_sqft=raw.total_sqft,
                filed_date=raw.filed_date,
                matched_company_id=enrichment["matched_company_id"],
                matched_company_name=enrichment["matched_company_name"],
                match_score=enrichment["match_score"],
            )
            session.add(db)

            row = {
                "permit_number":       raw.permit_number,
                "county":              raw.county_name,
                "permit_type":         raw.permit_type,
                "status":              raw.status,
                "address":             raw.address,
                "city":                raw.city,
                "zip_code":            raw.zip_code,
                "applicant_name":      raw.applicant_name,
                "owner_name":          raw.owner_name,
                "contractor_name":     raw.contractor_name,
                "description":         raw.description,
                "estimated_value":     f"${raw.estimated_value:,.0f}" if raw.estimated_value else "",
                "total_sqft":          f"{raw.total_sqft:,.0f}" if raw.total_sqft else "",
                "filed_date":          raw.filed_date.strftime("%Y-%m-%d") if raw.filed_date else "",
                "parcel_number":       raw.parcel_number,
                "matched_company":     enrichment["matched_company_name"] or "",
                "match_score":         f"{enrichment['match_score']:.0f}%" if enrichment["match_score"] else "",
                "is_commercial":       "Yes" if enrichment["is_commercial"] else "",
                "is_industrial":       "Yes" if enrichment["is_industrial"] else "",
            }
            all_records.append(row)
            if enrichment["matched_company_name"] and not enrichment["skip"]:
                all_matched.append(row)

    return all_records, all_matched


if __name__ == "__main__":
    all_records, matched = run_demo()

    out_all = Path("permit_scraper/output_all_permits.csv")
    out_matched = Path("permit_scraper/output_matches.csv")
    fields = list(all_records[0].keys())

    with open(out_all, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(all_records)

    with open(out_matched, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(matched)

    print(f"Total permits processed : {len(all_records)}")
    print(f"Company matches found   : {len(matched)}")
    print(f"All permits CSV         : {out_all}")
    print(f"Matches only CSV        : {out_matched}")
