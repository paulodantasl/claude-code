"""
Demo test — runs the full pipeline against a synthetic Central West FL
permit dataset and exports results to CSV.

All records are fictional: permit numbers, addresses, parcels, contractors,
values, and dates are made up. Applicant/owner names are watch-list
companies and their filing entities (including subsidiaries / shell
companies) so the matcher has something to hit; city and ZIP are generic.
Do not replace these with real filings — this file is public, and the CSV
outputs are gitignored.
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
        source_id="DEMO-HC-0001",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0001", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Vadata Inc",
        owner_name="Vadata Inc",
        contractor_name="Sample Builders 01 Inc",
        description="New 987,000 SF fulfillment center - tilt-wall Class A",
        address="125 Sample Way", city="Tampa", state="FL", zip_code="33619",
        parcel_number="00-00-00-DEMO-0001",
        estimated_value=137_600_000, total_sqft=987_000,
        filed_date=d(2025, 1, 15),
    ),
    RawPermit(
        source_id="DEMO-HC-0002",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0002", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Wal-Mart Stores East LP",
        owner_name="Walmart Real Estate Business Trust",
        contractor_name="Sample Builders 02 Inc",
        description="New 166,000 SF Walmart Supercenter — garden center & tire/lube",
        address="150 Placeholder Blvd", city="Gibsonton", state="FL", zip_code="33534",
        parcel_number="00-00-00-DEMO-0002",
        estimated_value=19_700_000, total_sqft=166_000,
        filed_date=d(2025, 2, 6),
    ),
    RawPermit(
        source_id="DEMO-HC-0003",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0003", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Sample Builders 03 Inc",
        description="New 45,000 SF supermarket with pharmacy and fuel center",
        address="175 Demo Ave", city="Riverview", state="FL", zip_code="33569",
        parcel_number="00-00-00-DEMO-0003",
        estimated_value=7_600_000, total_sqft=45_000,
        filed_date=d(2025, 3, 22),
    ),
    RawPermit(
        source_id="DEMO-HC-0004",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0004", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Home Depot USA Inc",
        owner_name="Home Depot USA Inc",
        contractor_name="Sample Builders 04 Inc",
        description="55,000 SF garden center expansion and warehouse addition",
        address="200 Fixture Ln", city="Tampa", state="FL", zip_code="33614",
        parcel_number="00-00-00-DEMO-0004",
        estimated_value=3_700_000, total_sqft=55_000,
        filed_date=d(2025, 4, 26),
    ),
    RawPermit(
        source_id="DEMO-HC-0005",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0005", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Chick-fil-A Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Sample Builders 05 Inc",
        description="New 4,550 SF Chick-fil-A restaurant with drive-through",
        address="225 Mockup Dr", city="Brandon", state="FL", zip_code="33596",
        parcel_number="00-00-00-DEMO-0005",
        estimated_value=2_000_000, total_sqft=4_550,
        filed_date=d(2025, 5, 16),
    ),
    RawPermit(
        source_id="DEMO-HC-0006",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0006", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Prologis USLF III LLC",
        owner_name="Prologis LP",
        contractor_name="Sample Builders 06 Inc",
        description="New 349,000 SF Class A industrial/distribution building — spec",
        address="250 Prototype Rd", city="Gibsonton", state="FL", zip_code="33534",
        parcel_number="00-00-00-DEMO-0006",
        estimated_value=30_500_000, total_sqft=349_000,
        filed_date=d(2025, 6, 23),
    ),
    RawPermit(
        source_id="DEMO-HC-0007",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0007", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon Data Services Inc",
        owner_name="Vadata Inc",
        contractor_name="Sample Builders 07 Inc",
        description="New 255,000 SF hyperscale data center (AWS) — two data halls",
        address="275 Specimen Ct", city="Tampa", state="FL", zip_code="33616",
        parcel_number="00-00-00-DEMO-0007",
        estimated_value=461_400_000, total_sqft=255_000,
        filed_date=d(2025, 8, 8),
    ),
    RawPermit(
        source_id="DEMO-HC-0008",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0008", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="HCA Florida Brandon Hospital",
        owner_name="HCA Healthcare Inc",
        contractor_name="Sample Builders 08 Inc",
        description="New 6-story, 191,000 SF hospital patient tower addition",
        address="300 Example Pkwy", city="Brandon", state="FL", zip_code="33511",
        parcel_number="00-00-00-DEMO-0008",
        estimated_value=74_800_000, total_sqft=191_000,
        filed_date=d(2025, 8, 18),
    ),
    RawPermit(
        source_id="DEMO-HC-0009",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0009", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Sample Builders 09 Inc",
        description="New 152,000 SF Costco warehouse",
        address="325 Sample Way", city="Wimauma", state="FL", zip_code="33598",
        parcel_number="00-00-00-DEMO-0009",
        estimated_value=19_300_000, total_sqft=152_000,
        filed_date=d(2025, 9, 7),
    ),
    RawPermit(
        source_id="DEMO-HC-0010",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0010", permit_type="Residential New Construction",
        status="Permit Issued",
        applicant_name="D.R. Horton Inc",
        owner_name="D.R. Horton Inc",
        contractor_name="D.R. Horton Inc",
        description="New single-family residence 2,650 SF",
        address="350 Placeholder Blvd", city="Riverview", state="FL", zip_code="33579",
        parcel_number="00-00-00-DEMO-0010",
        estimated_value=330_000, total_sqft=2_650,
        filed_date=d(2025, 10, 10),
    ),
    RawPermit(
        source_id="DEMO-HC-0011",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0011", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="Sample Builders 10 Inc",
        description="New 116,000 SF Target store",
        address="375 Demo Ave", city="Lithia", state="FL", zip_code="33547",
        parcel_number="00-00-00-DEMO-0011",
        estimated_value=15_900_000, total_sqft=116_000,
        filed_date=d(2026, 1, 19),
    ),
    RawPermit(
        source_id="DEMO-HC-0012",
        county_id="hillsborough_county", county_name="Hillsborough County, FL",
        permit_number="DEMO-HC-0012", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Amazon Logistics Inc",
        owner_name="Amazon Logistics Inc",
        contractor_name="Sample Builders 11 Inc",
        description="New 111,000 SF last-mile delivery station",
        address="400 Fixture Ln", city="Tampa", state="FL", zip_code="33610",
        parcel_number="00-00-00-DEMO-0012",
        estimated_value=10_900_000, total_sqft=111_000,
        filed_date=d(2026, 3, 8),
    ),

    # ════════════════════════════════════════════════════════════════════
    # CITY OF TAMPA
    # ════════════════════════════════════════════════════════════════════

    RawPermit(
        source_id="DEMO-TPA-0013",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0013", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Sample Builders 09 Inc",
        description="New 150,000 SF Costco warehouse with tire center and fuel station",
        address="425 Mockup Dr", city="Tampa", state="FL", zip_code="33611",
        parcel_number="00-00-00-DEMO-0013",
        estimated_value=19_500_000, total_sqft=150_000,
        filed_date=d(2025, 1, 27),
    ),
    RawPermit(
        source_id="DEMO-TPA-0014",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0014", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Marriott International Inc",
        owner_name="Marriott Hotel Services LLC",
        contractor_name="Sample Builders 12 Inc",
        description="New 12-story 290-room Courtyard by Marriott hotel",
        address="450 Prototype Rd", city="Tampa", state="FL", zip_code="33602",
        parcel_number="00-00-00-DEMO-0014",
        estimated_value=57_800_000, total_sqft=229_000,
        filed_date=d(2025, 2, 20),
    ),
    RawPermit(
        source_id="DEMO-TPA-0015",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0015", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon.com Services LLC",
        owner_name="Amazon Logistics Inc",
        contractor_name="Sample Builders 13 Inc",
        description="New 86,000 SF last-mile delivery station",
        address="475 Specimen Ct", city="Tampa", state="FL", zip_code="33610",
        parcel_number="00-00-00-DEMO-0015",
        estimated_value=12_500_000, total_sqft=86_000,
        filed_date=d(2025, 3, 24),
    ),
    RawPermit(
        source_id="DEMO-TPA-0016",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0016", permit_type="Commercial Tenant Improvement",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Sample Builders 14 Inc",
        description="Full interior renovation 50,000 SF supermarket — new deli/bakery/pharmacy",
        address="500 Example Pkwy", city="Tampa", state="FL", zip_code="33629",
        parcel_number="00-00-00-DEMO-0016",
        estimated_value=3_300_000, total_sqft=50_000,
        filed_date=d(2025, 5, 10),
    ),
    RawPermit(
        source_id="DEMO-TPA-0017",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0017", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Meta Platforms Inc",
        owner_name="Facebook Real Estate LLC",
        contractor_name="Sample Builders 15 Inc",
        description="New 376,000 SF hyperscale data center campus — Phase 1 of 3",
        address="525 Sample Way", city="Tampa", state="FL", zip_code="33619",
        parcel_number="00-00-00-DEMO-0017",
        estimated_value=576_600_000, total_sqft=376_000,
        filed_date=d(2025, 6, 10),
    ),
    RawPermit(
        source_id="DEMO-TPA-0018",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0018", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="McDonalds Corporation",
        owner_name="McDonald's USA LLC",
        contractor_name="Sample Builders 16 Inc",
        description="New 4,600 SF McDonald's restaurant with double drive-through",
        address="550 Placeholder Blvd", city="Tampa", state="FL", zip_code="33609",
        parcel_number="00-00-00-DEMO-0018",
        estimated_value=2_000_000, total_sqft=4_600,
        filed_date=d(2025, 7, 17),
    ),
    RawPermit(
        source_id="DEMO-TPA-0019",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0019", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="Sample Builders 17 Inc",
        description="New 22,000 SF small-format Target store",
        address="575 Demo Ave", city="Tampa", state="FL", zip_code="33602",
        parcel_number="00-00-00-DEMO-0019",
        estimated_value=6_300_000, total_sqft=22_000,
        filed_date=d(2025, 9, 3),
    ),
    RawPermit(
        source_id="DEMO-TPA-0020",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0020", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Microsoft Corporation",
        owner_name="Microsoft Azure Real Estate LLC",
        contractor_name="Sample Builders 18 Inc",
        description="New 339,000 SF Azure data center — two-hall campus build-out",
        address="600 Fixture Ln", city="Tampa", state="FL", zip_code="33634",
        parcel_number="00-00-00-DEMO-0020",
        estimated_value=431_200_000, total_sqft=339_000,
        filed_date=d(2025, 10, 12),
    ),
    RawPermit(
        source_id="DEMO-TPA-0021",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0021", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Sample Builders 19 Inc",
        description="New 49,000 SF Publix GreenWise Market",
        address="625 Mockup Dr", city="Tampa", state="FL", zip_code="33629",
        parcel_number="00-00-00-DEMO-0021",
        estimated_value=6_700_000, total_sqft=49_000,
        filed_date=d(2025, 11, 26),
    ),
    RawPermit(
        source_id="DEMO-TPA-0022",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0022", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Home Depot USA Inc",
        owner_name="Home Depot USA Inc",
        contractor_name="Sample Builders 20 Inc",
        description="New 114,000 SF The Home Depot store",
        address="650 Prototype Rd", city="Tampa", state="FL", zip_code="33610",
        parcel_number="00-00-00-DEMO-0022",
        estimated_value=14_400_000, total_sqft=114_000,
        filed_date=d(2026, 1, 11),
    ),
    RawPermit(
        source_id="DEMO-TPA-0023",
        county_id="city_tampa", county_name="City of Tampa",
        permit_number="DEMO-TPA-0023", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Chick-fil-A Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Sample Builders 05 Inc",
        description="New 4,750 SF Chick-fil-A with dual drive-through",
        address="675 Specimen Ct", city="Tampa", state="FL", zip_code="33607",
        parcel_number="00-00-00-DEMO-0023",
        estimated_value=2_700_000, total_sqft=4_750,
        filed_date=d(2026, 2, 23),
    ),

    # ════════════════════════════════════════════════════════════════════
    # PASCO COUNTY
    # ════════════════════════════════════════════════════════════════════

    RawPermit(
        source_id="DEMO-PAS-0024",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0024", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="FedEx Ground Package System Inc",
        owner_name="FedEx Ground Package System Inc",
        contractor_name="Sample Builders 16 Inc",
        description="New 276,000 SF FedEx Ground distribution hub",
        address="700 Example Pkwy", city="Wesley Chapel", state="FL", zip_code="33543",
        parcel_number="00-00-00-DEMO-0024",
        estimated_value=27_500_000, total_sqft=276_000,
        filed_date=d(2025, 2, 4),
    ),
    RawPermit(
        source_id="DEMO-PAS-0025",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0025", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Sample Builders 19 Inc",
        description="New 49,000 SF Publix supermarket",
        address="725 Sample Way", city="Wesley Chapel", state="FL", zip_code="33545",
        parcel_number="00-00-00-DEMO-0025",
        estimated_value=6_900_000, total_sqft=49_000,
        filed_date=d(2025, 3, 15),
    ),
    RawPermit(
        source_id="DEMO-PAS-0026",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0026", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Amazon Logistics Inc",
        owner_name="Vadata Inc",
        contractor_name="Sample Builders 21 Inc",
        description="New 218,000 SF Amazon delivery station — tilt-wall",
        address="750 Placeholder Blvd", city="New Port Richey", state="FL", zip_code="34655",
        parcel_number="00-00-00-DEMO-0026",
        estimated_value=20_900_000, total_sqft=218_000,
        filed_date=d(2025, 4, 23),
    ),
    RawPermit(
        source_id="DEMO-PAS-0027",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0027", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="Target Corporation",
        owner_name="Target Real Estate LLC",
        contractor_name="Sample Builders 10 Inc",
        description="New 123,000 SF Target store — drive-up + Starbucks",
        address="775 Demo Ave", city="Wesley Chapel", state="FL", zip_code="33544",
        parcel_number="00-00-00-DEMO-0027",
        estimated_value=17_700_000, total_sqft=123_000,
        filed_date=d(2025, 5, 24),
    ),
    RawPermit(
        source_id="DEMO-PAS-0028",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0028", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="United Parcel Service Inc",
        owner_name="UPS Supply Chain Solutions Inc",
        contractor_name="Sample Builders 20 Inc",
        description="New 196,000 SF UPS package hub and customer center",
        address="800 Fixture Ln", city="Land O Lakes", state="FL", zip_code="34639",
        parcel_number="00-00-00-DEMO-0028",
        estimated_value=19_400_000, total_sqft=196_000,
        filed_date=d(2025, 6, 18),
    ),
    RawPermit(
        source_id="DEMO-PAS-0029",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0029", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Costco Wholesale Corporation",
        owner_name="Costco Wholesale Corporation",
        contractor_name="Sample Builders 09 Inc",
        description="New 149,000 SF Costco warehouse",
        address="825 Mockup Dr", city="Wesley Chapel", state="FL", zip_code="33544",
        parcel_number="00-00-00-DEMO-0029",
        estimated_value=18_100_000, total_sqft=149_000,
        filed_date=d(2025, 7, 11),
    ),
    RawPermit(
        source_id="DEMO-PAS-0030",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0030", permit_type="Commercial New Construction",
        status="Permit Issued",
        applicant_name="CFA Properties Inc",
        owner_name="CFA Properties Inc",
        contractor_name="Sample Builders 05 Inc",
        description="New 5,550 SF Chick-fil-A with dual drive-through lanes",
        address="850 Prototype Rd", city="Zephyrhills", state="FL", zip_code="33540",
        parcel_number="00-00-00-DEMO-0030",
        estimated_value=2_600_000, total_sqft=5_550,
        filed_date=d(2025, 8, 12),
    ),
    RawPermit(
        source_id="DEMO-PAS-0031",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0031", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Vadata Inc",
        owner_name="Vadata Inc",
        contractor_name="Sample Builders 07 Inc",
        description="New 410,000 SF Amazon fulfillment center",
        address="875 Specimen Ct", city="Lutz", state="FL", zip_code="33558",
        parcel_number="00-00-00-DEMO-0031",
        estimated_value=69_400_000, total_sqft=410_000,
        filed_date=d(2025, 9, 27),
    ),
    RawPermit(
        source_id="DEMO-PAS-0032",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0032", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Sample Builders 19 Inc",
        description="New 52,000 SF Publix supermarket",
        address="900 Example Pkwy", city="Land O Lakes", state="FL", zip_code="34638",
        parcel_number="00-00-00-DEMO-0032",
        estimated_value=5_800_000, total_sqft=52_000,
        filed_date=d(2025, 11, 8),
    ),
    RawPermit(
        source_id="DEMO-PAS-0033",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0033", permit_type="Residential New Construction",
        status="Permit Issued",
        applicant_name="Lennar Homes LLC",
        owner_name="Lennar Homes LLC",
        contractor_name="Lennar Homes LLC",
        description="New single-family residence 2,100 SF",
        address="925 Sample Way", city="Land O Lakes", state="FL", zip_code="34638",
        parcel_number="00-00-00-DEMO-0033",
        estimated_value=265_000, total_sqft=2_100,
        filed_date=d(2025, 11, 12),
    ),
    RawPermit(
        source_id="DEMO-PAS-0034",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0034", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Amazon Data Services Inc",
        owner_name="Vadata Inc",
        contractor_name="Sample Builders 07 Inc",
        description="New 240,000 SF hyperscale data center",
        address="950 Placeholder Blvd", city="Dade City", state="FL", zip_code="33523",
        parcel_number="00-00-00-DEMO-0034",
        estimated_value=331_700_000, total_sqft=240_000,
        filed_date=d(2026, 2, 3),
    ),
    RawPermit(
        source_id="DEMO-PAS-0035",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0035", permit_type="Commercial New Construction",
        status="Plan Review",
        applicant_name="Walmart Real Estate Business Trust",
        owner_name="Walmart Real Estate Business Trust",
        contractor_name="Sample Builders 02 Inc",
        description="New 141,000 SF Walmart Supercenter",
        address="975 Demo Ave", city="Wesley Chapel", state="FL", zip_code="33545",
        parcel_number="00-00-00-DEMO-0035",
        estimated_value=19_900_000, total_sqft=141_000,
        filed_date=d(2026, 2, 24),
    ),
    RawPermit(
        source_id="DEMO-PAS-0036",
        county_id="pasco_county", county_name="Pasco County, FL",
        permit_number="DEMO-PAS-0036", permit_type="Commercial New Construction",
        status="Application Received",
        applicant_name="Publix Super Markets Inc",
        owner_name="Publix Realty LLC",
        contractor_name="Sample Builders 03 Inc",
        description="New 53,000 SF Publix supermarket",
        address="1000 Fixture Ln", city="San Antonio", state="FL", zip_code="33576",
        parcel_number="00-00-00-DEMO-0036",
        estimated_value=6_200_000, total_sqft=53_000,
        filed_date=d(2026, 3, 6),
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
        session.query(Permit).filter(Permit.source_id.like("DEMO-%")).delete(synchronize_session=False)

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
