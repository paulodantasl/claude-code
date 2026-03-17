"""
Demo test — runs the full pipeline against a realistic Central West FL
permit dataset (2025-01-01 through present) and exports results to CSV.

Records modelled on actual filings in Hillsborough, City of Tampa, and
Pasco County: real street addresses, real company filing names (including
subsidiaries / shell companies), real permit types and value ranges.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from permit_scraper.storage import init_db, get_session, Permit
from permit_scraper.scrapers.base import RawPermit
from permit_scraper.agents.classifier import CompanyMatcher, PermitClassifier
import yaml

d = datetime   # shorthand

SAMPLE_PERMITS = [

    # ════════════════════════════════════════════════════════════════════
    # HILLSBOROUGH COUNTY
    # ════════════════════════════════════════════════════════════════════

    RawPermit(
        source_id="HCFL-2025-BC-001122",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-001122", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Vadata Inc",
        owner_name="Vadata Inc",
        contractor_name="Whiting-Turner Contracting Co",
        description="New 1,050,000 SF fulfillment center - tilt-wall Class A",
        address="7850 East Adamo Dr", city="Tampa", state="FL", zip_code="33619",
        parcel_number="U-09-29-19-ZZZ-000000-00000",
        estimated_value=148_000_000, total_sqft=1_050_000,
        filed_date=d(2025, 1, 8),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-003408",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-003408", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Wal-Mart Stores East LP",
        owner_name="Walmart Real Estate Business Trust",
        contractor_name="Harkins Builders Inc",
        description="New 152,000 SF Walmart Supercenter — garden center & tire/lube",
        address="10120 Gibsonton Dr", city="Gibsonton", state="FL", zip_code="33534",
        parcel_number="U-01-31-19-ZZZ-000000-99900",
        estimated_value=18_400_000, total_sqft=152_000,
        filed_date=d(2025, 2, 3),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-005900",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-005900", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Brasfield & Gorrie LLC",
        description="New 49,200 SF supermarket with pharmacy and fuel center",
        address="12301 Boyette Rd", city="Riverview", state="FL", zip_code="33569",
        parcel_number="U-27-30-20-ZZZ-000000-11100",
        estimated_value=6_800_000, total_sqft=49_200,
        filed_date=d(2025, 3, 14),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-007210",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-007210", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Home Depot USA Inc",
        owner_name="Home Depot USA Inc",
        contractor_name="Coreslab Structures Inc",
        description="52,000 SF garden center expansion and warehouse addition",
        address="8701 N Dale Mabry Hwy", city="Tampa", state="FL", zip_code="33614",
        parcel_number="U-10-28-18-ZZZ-000000-44400",
        estimated_value=4_200_000, total_sqft=52_000,
        filed_date=d(2025, 4, 22),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-009340",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-009340", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Chick-fil-A Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Axiom Construction Inc",
        description="New 4,850 SF Chick-fil-A restaurant with drive-through",
        address="2201 Bloomingdale Ave", city="Brandon", state="FL", zip_code="33596",
        parcel_number="U-22-30-20-ZZZ-000000-33300",
        estimated_value=2_100_000, total_sqft=4_850,
        filed_date=d(2025, 5, 7),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-011580",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-011580", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Prologis USLF III LLC",
        owner_name="Prologis LP",
        contractor_name="Sunbelt Structures Inc",
        description="New 320,000 SF Class A industrial/distribution building — spec",
        address="6400 US Hwy 301 S", city="Gibsonton", state="FL", zip_code="33534",
        parcel_number="U-15-31-19-ZZZ-000000-55500",
        estimated_value=28_500_000, total_sqft=320_000,
        filed_date=d(2025, 6, 18),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-014002",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-014002", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon Data Services Inc",
        owner_name="Vadata Inc",
        contractor_name="Turner Construction Company",
        description="New 280,000 SF hyperscale data center (AWS) — 2 x 140k SF halls",
        address="3900 Port Tampa Bay Blvd", city="Tampa", state="FL", zip_code="33616",
        parcel_number="U-18-30-17-ZZZ-000000-88800",
        estimated_value=412_000_000, total_sqft=280_000,
        filed_date=d(2025, 7, 29),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-016455",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-016455", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="HCA Florida Brandon Hospital",
        owner_name="HCA Healthcare Inc",
        contractor_name="Rodgers Builders Inc",
        description="New 6-story, 180,000 SF hospital patient tower addition",
        address="119 Oakfield Dr", city="Brandon", state="FL", zip_code="33511",
        parcel_number="U-14-29-20-ZZZ-000000-22200",
        estimated_value=85_000_000, total_sqft=180_000,
        filed_date=d(2025, 8, 12),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-019877",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-019877", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Hensel Phelps Construction Co",
        description="New 162,000 SF Costco warehouse — Sun City Center area",
        address="3250 SR-674", city="Wimauma", state="FL", zip_code="33598",
        parcel_number="U-30-31-20-ZZZ-000000-66600",
        estimated_value=20_800_000, total_sqft=162_000,
        filed_date=d(2025, 9, 5),
    ),
    RawPermit(
        source_id="HCFL-2025-BC-022100",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2025-022100", permit_type="Residential New Construction",
        status="Permit Issued",
        applicant_name="D.R. Horton Inc",
        owner_name="D.R. Horton Inc",
        contractor_name="D.R. Horton Inc",
        description="New single-family residence 2,450 SF",
        address="14122 Swan Lake Dr", city="Riverview", state="FL", zip_code="33579",
        parcel_number="U-05-31-20-ZZZ-000000-11100",
        estimated_value=310_000, total_sqft=2_450,
        filed_date=d(2025, 10, 3),
    ),
    RawPermit(
        source_id="HCFL-2026-BC-002340",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2026-002340", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="Barton Malow Company",
        description="New 128,000 SF Target — Fishhawk Ranch Town Center",
        address="5505 Lithia Pinecrest Rd", city="Lithia", state="FL", zip_code="33547",
        parcel_number="U-11-30-21-ZZZ-000000-77700",
        estimated_value=14_200_000, total_sqft=128_000,
        filed_date=d(2026, 1, 16),
    ),
    RawPermit(
        source_id="HCFL-2026-BC-004810",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="BC-2026-004810", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Amazon Logistics Inc",
        owner_name="Amazon Logistics Inc",
        contractor_name="Gray Construction Inc",
        description="New 105,000 SF last-mile delivery station (DTA5)",
        address="5200 E Hillsborough Ave", city="Tampa", state="FL", zip_code="33610",
        parcel_number="U-20-28-19-ZZZ-000000-33300",
        estimated_value=12_400_000, total_sqft=105_000,
        filed_date=d(2026, 2, 28),
    ),

    # ════════════════════════════════════════════════════════════════════
    # CITY OF TAMPA
    # ════════════════════════════════════════════════════════════════════

    RawPermit(
        source_id="TAMPA-2025-BLD-010044",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-010044", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Hensel Phelps Construction Co",
        description="New 160,000 SF Costco warehouse with tire center and fuel station",
        address="4811 W Gandy Blvd", city="Tampa", state="FL", zip_code="33611",
        parcel_number="A-30-29-17-ZZZ-000000-00110",
        estimated_value=21_000_000, total_sqft=160_000,
        filed_date=d(2025, 1, 23),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-013890",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-013890", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Marriott International Inc",
        owner_name="Marriott Hotel Services LLC",
        contractor_name="Suffolk Construction Co",
        description="New 14-story 312-room Courtyard by Marriott — downtown Tampa",
        address="400 N Ashley Dr", city="Tampa", state="FL", zip_code="33602",
        parcel_number="A-01-29-18-ZZZ-000000-00880",
        estimated_value=54_000_000, total_sqft=210_000,
        filed_date=d(2025, 2, 11),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-018200",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-018200", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon.com Services LLC",
        owner_name="Amazon Logistics Inc",
        contractor_name="DPR Construction",
        description="New 95,000 SF last-mile delivery station (DST7)",
        address="4215 E Hillsborough Ave", city="Tampa", state="FL", zip_code="33610",
        parcel_number="A-16-29-19-ZZZ-000000-00220",
        estimated_value=11_200_000, total_sqft=95_000,
        filed_date=d(2025, 3, 19),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-022750",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-022750", permit_type="Commercial Tenant Improvement",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Stellar Group Inc",
        description="Full interior renovation 47,500 SF supermarket — new deli/bakery/pharmacy",
        address="1523 S Dale Mabry Hwy", city="Tampa", state="FL", zip_code="33629",
        parcel_number="A-24-29-18-ZZZ-000000-00440",
        estimated_value=3_800_000, total_sqft=47_500,
        filed_date=d(2025, 4, 30),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-027660",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-027660", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Meta Platforms Inc",
        owner_name="Facebook Real Estate LLC",
        contractor_name="Mortenson Construction",
        description="New 400,000 SF hyperscale data center campus — Phase 1 of 3",
        address="9100 E Adamo Dr", city="Tampa", state="FL", zip_code="33619",
        parcel_number="A-05-30-19-ZZZ-000000-00550",
        estimated_value=620_000_000, total_sqft=400_000,
        filed_date=d(2025, 6, 4),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-031020",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-031020", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="McDonalds Corporation",
        owner_name="McDonald's USA LLC",
        contractor_name="Conlan Company",
        description="New 4,200 SF McDonald's restaurant with double drive-through",
        address="5030 W Kennedy Blvd", city="Tampa", state="FL", zip_code="33609",
        parcel_number="A-22-29-17-ZZZ-000000-00660",
        estimated_value=1_850_000, total_sqft=4_200,
        filed_date=d(2025, 7, 15),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-035500",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-035500", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="McGough Construction LLC",
        description="New 24,000 SF small-format Target store — Hyde Park Village area",
        address="601 N Ashley Dr", city="Tampa", state="FL", zip_code="33602",
        parcel_number="A-01-29-18-ZZZ-000000-00330",
        estimated_value=5_600_000, total_sqft=24_000,
        filed_date=d(2025, 8, 27),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-039800",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-039800", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Microsoft Corporation",
        owner_name="Microsoft Azure Real Estate LLC",
        contractor_name="McCarthy Building Companies Inc",
        description="New 320,000 SF Azure data center — two-hall campus build-out",
        address="7400 W Hillsborough Ave", city="Tampa", state="FL", zip_code="33634",
        parcel_number="A-12-28-17-ZZZ-000000-00770",
        estimated_value=490_000_000, total_sqft=320_000,
        filed_date=d(2025, 10, 9),
    ),
    RawPermit(
        source_id="TAMPA-2025-BLD-042100",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2025-042100", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Welbro Building Corporation",
        description="New 51,800 SF Publix GreenWise Market — Westshore district",
        address="3838 Henderson Blvd", city="Tampa", state="FL", zip_code="33629",
        parcel_number="A-19-29-18-ZZZ-000000-00990",
        estimated_value=7_200_000, total_sqft=51_800,
        filed_date=d(2025, 11, 18),
    ),
    RawPermit(
        source_id="TAMPA-2026-BLD-004400",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2026-004400", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Home Depot USA Inc",
        owner_name="Home Depot USA Inc",
        contractor_name="Skanska USA Building Inc",
        description="New 105,000 SF The Home Depot — Ybor City redevelopment corridor",
        address="1601 E Hillsborough Ave", city="Tampa", state="FL", zip_code="33610",
        parcel_number="A-09-29-19-ZZZ-000000-01100",
        estimated_value=13_500_000, total_sqft=105_000,
        filed_date=d(2026, 1, 7),
    ),
    RawPermit(
        source_id="TAMPA-2026-BLD-007780",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="BLD-2026-007780", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Chick-fil-A Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Axiom Construction Inc",
        description="New 5,200 SF Chick-fil-A with dual drive-through — Westshore",
        address="4320 W Boy Scout Blvd", city="Tampa", state="FL", zip_code="33607",
        parcel_number="A-21-29-17-ZZZ-000000-01220",
        estimated_value=2_450_000, total_sqft=5_200,
        filed_date=d(2026, 2, 14),
    ),

    # ════════════════════════════════════════════════════════════════════
    # PASCO COUNTY
    # ════════════════════════════════════════════════════════════════════

    RawPermit(
        source_id="PASCO-2025-BD-005540",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-005540", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="FedEx Ground Package System Inc",
        owner_name="FedEx Ground Package System Inc",
        contractor_name="Conlan Company",
        description="New 260,000 SF FedEx Ground distribution hub",
        address="29100 SR-54", city="Wesley Chapel", state="FL", zip_code="33543",
        parcel_number="10-26-20-0000-00200-0010",
        estimated_value=31_200_000, total_sqft=260_000,
        filed_date=d(2025, 1, 30),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-007820",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-007820", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Welbro Building Corporation",
        description="New 52,600 SF supermarket — Epperson Ranch Town Center",
        address="7800 Epperson Blvd", city="Wesley Chapel", state="FL", zip_code="33545",
        parcel_number="20-25-21-0000-00100-0130",
        estimated_value=7_400_000, total_sqft=52_600,
        filed_date=d(2025, 3, 5),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-010110",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-010110", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon Logistics Inc",
        owner_name="Vadata Inc",
        contractor_name="Clancy & Theys Construction Co",
        description="New 200,000 SF Amazon delivery station (DSP4) — tilt-wall",
        address="2850 Trouble Creek Rd", city="New Port Richey", state="FL", zip_code="34655",
        parcel_number="13-26-16-0000-00400-0010",
        estimated_value=19_500_000, total_sqft=200_000,
        filed_date=d(2025, 4, 17),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-013400",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-013400", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="Barton Malow Company",
        description="New 135,000 SF Target store — Wiregrass Ranch, drive-up + Starbucks",
        address="5860 Cypress Ranch Blvd", city="Wesley Chapel", state="FL", zip_code="33544",
        parcel_number="09-26-20-0000-00100-0200",
        estimated_value=15_800_000, total_sqft=135_000,
        filed_date=d(2025, 5, 22),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-016700",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-016700", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="United Parcel Service Inc",
        owner_name="UPS Supply Chain Solutions Inc",
        contractor_name="Skanska USA Building Inc",
        description="New 185,000 SF UPS package hub and customer center",
        address="4100 Land O Lakes Blvd", city="Land O Lakes", state="FL", zip_code="34639",
        parcel_number="18-26-19-0000-00500-0010",
        estimated_value=22_000_000, total_sqft=185_000,
        filed_date=d(2025, 6, 11),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-019900",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-019900", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Hensel Phelps Construction Co",
        description="New 158,000 SF Costco warehouse — Wiregrass Ranch area",
        address="5500 Wesley Chapel Blvd", city="Wesley Chapel", state="FL", zip_code="33544",
        parcel_number="11-26-20-0000-00300-0010",
        estimated_value=19_500_000, total_sqft=158_000,
        filed_date=d(2025, 7, 8),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-022550",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-022550", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="CFA Properties Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Axiom Construction Inc",
        description="New 5,100 SF Chick-fil-A with dual drive-through lanes",
        address="2050 Zephyrhills Bypass Rd", city="Zephyrhills", state="FL", zip_code="33540",
        parcel_number="25-26-21-0000-01100-0010",
        estimated_value=2_400_000, total_sqft=5_100,
        filed_date=d(2025, 8, 4),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-025800",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-025800", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Vadata Inc",
        owner_name="Vadata Inc",
        contractor_name="Turner Construction Company",
        description="New 450,000 SF Amazon fulfillment center (BNA9 expansion type)",
        address="19200 FL-54", city="Lutz", state="FL", zip_code="33558",
        parcel_number="07-26-18-0000-00800-0010",
        estimated_value=62_000_000, total_sqft=450_000,
        filed_date=d(2025, 9, 23),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-028100",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-028100", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Welbro Building Corporation",
        description="New 48,900 SF Publix — Angeline master-planned community",
        address="3400 Angeline Blvd", city="Land O Lakes", state="FL", zip_code="34638",
        parcel_number="28-25-18-0000-00100-0020",
        estimated_value=6_600_000, total_sqft=48_900,
        filed_date=d(2025, 10, 30),
    ),
    RawPermit(
        source_id="PASCO-2025-BD-030900",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2025-030900", permit_type="Residential New Construction",
        status="Permit Issued",
        applicant_name="Lennar Homes LLC",
        owner_name="Lennar Homes LLC",
        contractor_name="Lennar Homes LLC",
        description="New single-family residence 2,210 SF",
        address="3245 Rustling Oaks Dr", city="Land O Lakes", state="FL", zip_code="34638",
        parcel_number="03-26-18-0000-02200-0010",
        estimated_value=285_000, total_sqft=2_210,
        filed_date=d(2025, 11, 7),
    ),
    RawPermit(
        source_id="PASCO-2026-BD-001800",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2026-001800", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Amazon Data Services Inc",
        owner_name="Vadata Inc",
        contractor_name="Turner Construction Company",
        description="New 220,000 SF hyperscale data center — Pasco Technology Campus",
        address="35500 SR-52", city="Dade City", state="FL", zip_code="33523",
        parcel_number="16-24-21-0000-00100-0010",
        estimated_value=310_000_000, total_sqft=220_000,
        filed_date=d(2026, 1, 24),
    ),
    RawPermit(
        source_id="PASCO-2026-BD-003550",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2026-003550", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Walmart Real Estate Business Trust",
        owner_name="Walmart Real Estate Business Trust",
        contractor_name="Harkins Builders Inc",
        description="New 155,000 SF Walmart Supercenter — SR-56 / Meadow Pointe",
        address="8800 SR-56", city="Wesley Chapel", state="FL", zip_code="33545",
        parcel_number="30-26-20-0000-00400-0010",
        estimated_value=17_800_000, total_sqft=155_000,
        filed_date=d(2026, 2, 18),
    ),
    RawPermit(
        source_id="PASCO-2026-BD-005100",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="BD-2026-005100", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Brasfield & Gorrie LLC",
        description="New 50,400 SF Publix — Mirada master-planned community",
        address="12600 Mirada Blvd", city="San Antonio", state="FL", zip_code="33576",
        parcel_number="05-25-20-0000-00200-0010",
        estimated_value=7_100_000, total_sqft=50_400,
        filed_date=d(2026, 3, 4),
    ),
]


def run_demo():
    init_db("sqlite:///demo_permits.db")

    watch_data = yaml.safe_load(
        (Path(__file__).parent / "targets" / "companies.yaml").read_text()
    )
    matcher  = CompanyMatcher(watch_data["watch_list"])
    classifier = PermitClassifier(matcher)

    all_rows: list[dict] = []
    matched_rows: list[dict] = []

    with get_session() as session:
        # Clear previous demo run
        session.query(Permit).filter(Permit.source_id.like("HCFL-202%")).delete(synchronize_session=False)
        session.query(Permit).filter(Permit.source_id.like("TAMPA-202%")).delete(synchronize_session=False)
        session.query(Permit).filter(Permit.source_id.like("PASCO-202%")).delete(synchronize_session=False)

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
                "filed_date":      raw.filed_date.strftime("%Y-%m-%d"),
                "permit_number":   raw.permit_number,
                "county":          raw.county_name,
                "city":            raw.city,
                "address":         raw.address,
                "zip_code":        raw.zip_code,
                "permit_type":     raw.permit_type,
                "status":          raw.status,
                "applicant_name":  raw.applicant_name,
                "owner_name":      raw.owner_name or "",
                "contractor_name": raw.contractor_name or "",
                "description":     raw.description,
                "est_value":       f"${raw.estimated_value:,.0f}" if raw.estimated_value else "",
                "sqft":            f"{int(raw.total_sqft):,}" if raw.total_sqft else "",
                "parcel_number":   raw.parcel_number or "",
                "matched_company": enrichment["matched_company_name"] or "—",
                "match_score":     f"{enrichment['match_score']:.0f}%" if enrichment["match_score"] else "—",
            }
            all_rows.append(row)
            if enrichment["matched_company_name"] and not enrichment["skip"]:
                matched_rows.append(row)

    return all_rows, matched_rows


if __name__ == "__main__":
    all_rows, matched = run_demo()

    # Sort matched by filed date descending
    matched.sort(key=lambda r: r["filed_date"], reverse=True)
    all_rows.sort(key=lambda r: r["filed_date"], reverse=True)

    fields = list(all_rows[0].keys())
    out_all     = Path("permit_scraper/output_all_permits.csv")
    out_matched = Path("permit_scraper/output_matches.csv")

    for path, rows in [(out_all, all_rows), (out_matched, matched)]:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    print(f"Total permits processed : {len(all_rows)}")
    print(f"Company matches found   : {len(matched)}")
    print(f"Residential filtered    : {len(all_rows) - len(matched)}")
    print(f"All permits CSV         : {out_all}")
    print(f"Matches CSV             : {out_matched}")

    # ── Google Drive export (optional) ──────────────────────────────────────
    # Runs automatically if GOOGLE_SERVICE_ACCOUNT_FILE or
    # GOOGLE_OAUTH_CLIENT_FILE is set in the environment / .env
    import os
    has_google_creds = (
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        or os.environ.get("GOOGLE_OAUTH_CLIENT_FILE")
    )
    if has_google_creds:
        try:
            from permit_scraper.notifications.google_drive import GoogleDriveExporter
            exporter = GoogleDriveExporter.from_env()
            sheet_url = exporter.export_matches(
                matched_rows=matched,
                all_rows=all_rows,
                sheet_title=f"Permit Intelligence — Central West FL — {datetime.now().strftime('%Y-%m-%d')}",
            )
            print(f"\nGoogle Sheet created    : {sheet_url}")
            # Also upload the raw CSVs for archive
            exporter.upload_csv(out_matched, filename=out_matched.name)
            exporter.upload_csv(out_all,     filename=out_all.name)
            print("CSV files uploaded to Drive.")
        except Exception as exc:
            print(f"\n[Google Drive] Export failed: {exc}")
            print("  Check your credentials and that the Google Sheets/Drive APIs are enabled.")
    else:
        print(
            "\nTip: set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_OAUTH_CLIENT_FILE"
            " to automatically export results to Google Drive."
        )
