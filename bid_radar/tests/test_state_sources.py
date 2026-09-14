"""
The state-file collectors: Sunbiz and HCAA.

Sunbiz is dormant — its daily files sit behind a credentialed SFTP account
(401 to anonymous, observed from a runner 2026-09-14) — so what is tested here
is the parser and the guards, which are what will be wrong if the layout is
wrong. HCAA's parser is tested against the shape of the real report.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "sources"))

from sources import hcaa_ppo, sunbiz  # noqa: E402


# ------------------------------------------------------------------ sunbiz

def _fixed(**over) -> str:
    """Build one record at the published offsets."""
    fields = {"doc_number": "L26000123456", "name": "WAGAMAMA TAMPA LLC",
              "status": "A", "filing_type": "FLAL",
              "addr1": "1050 WATER ST", "addr2": "SUITE 100",
              "city": "TAMPA", "state": "FL", "zip": "33602",
              "country": "US", "mail_addr1": "1050 WATER ST", "mail_addr2": "",
              "mail_city": "TAMPA", "mail_state": "FL", "mail_zip": "33602",
              "mail_country": "US", "file_date": "20260902",
              "fei_number": "99-1234567"}
    fields.update(over)
    line = ""
    for field, start, length in sunbiz.LAYOUT:
        line = line.ljust(start)
        line += str(fields[field])[:length].ljust(length)
    return line


def test_a_record_parses_at_the_published_offsets():
    rec = sunbiz.parse_line(_fixed())
    assert rec is not None
    assert rec["doc_number"] == "L26000123456"
    assert rec["name"] == "WAGAMAMA TAMPA LLC"
    assert rec["addr1"] == "1050 WATER ST"
    assert rec["zip"] == "33602"
    assert rec["file_date"] == "20260902"


def test_a_short_line_is_rejected_rather_than_sliced_past_the_end():
    """A wrong offset must produce nothing, never a plausible-looking name."""
    assert sunbiz.parse_line("L26000123456 SOMETHING SHORT") is None
    assert sunbiz.parse_line("") is None


def test_only_submarket_zips_are_interesting():
    assert sunbiz.is_interesting(sunbiz.parse_line(_fixed(zip="33602")))
    # Orlando. Sunbiz is statewide and nearly all of it is noise.
    assert not sunbiz.is_interesting(sunbiz.parse_line(_fixed(zip="32801")))


def test_a_registered_agent_address_is_not_a_tenant():
    rec = sunbiz.parse_line(_fixed(addr1="C T CORPORATION SYSTEM"))
    assert not sunbiz.is_interesting(rec)


def test_the_collector_is_dormant_without_credentials_and_says_so(capsys, monkeypatch):
    monkeypatch.delenv("SUNBIZ_USER", raising=False)
    monkeypatch.delenv("SUNBIZ_PASS", raising=False)
    assert sunbiz.collect() == []
    out = capsys.readouterr().out
    assert "SKIPPED" in out and "sftp.floridados.gov" in out


def test_the_layout_is_flagged_unverified_until_a_real_file_confirms_it():
    """It is transcribed from the published definition, not observed. The flag
    rides on every emitted row so nobody mistakes it for checked."""
    assert sunbiz.LAYOUT_VERIFIED is False
    sig = sunbiz._signal(sunbiz.parse_line(_fixed()), "http://x", "2026-09-14T00:00:00")
    assert sig["layout_verified"] is False
    assert sig["hood"] is None          # no geometry in the file, so no guess
    assert sig["filed_at"] == "2026-09-02"


# -------------------------------------------------------------------- hcaa

REPORT = """
Planned Procurement Opportunities Report - September 2026

Request for Proposals to establish a prequalified contractors list for
building construction, site work and paving
Planning and Development Department
Advertise 4/20/2026  Pre-proposal 4/27/2026  Due 9/3/2026
Contact: Nick Diaz ndiaz@tampaairport.com
Estimated value $25,000,000

Airside C concourse terminal renovation - general trades
Advertise 11/15/2026  Due 1/20/2027
Contact: procurement@tampaairport.com
Estimated value $4,500,000

Janitorial services for the main terminal
Advertise 10/1/2026
Contact: procurement@tampaairport.com

Employee staffing and temporary labor
Advertise 10/5/2026
"""


def test_the_report_parser_keeps_construction_and_drops_the_rest():
    rows = hcaa_ppo.parse_rows(REPORT)
    titles = " | ".join(r["title"] for r in rows)
    assert "prequalified contractors" in titles
    assert "concourse terminal renovation" in titles
    # Real lines from a real report that Ideal cannot bid.
    assert "Janitorial" not in titles
    assert "staffing" not in titles.lower()


def test_the_prequal_row_carries_its_dates_contact_and_value():
    row = next(r for r in hcaa_ppo.parse_rows(REPORT)
               if "prequalified" in r["title"])
    assert "2026-04-20" in row["dates"]
    assert "2026-09-03" in row["dates"]
    assert "ndiaz@tampaairport.com" in row["emails"]
    assert row["value_est"] == 25_000_000.0


def test_a_stray_dollar_figure_is_not_taken_as_a_contract_value():
    assert hcaa_ppo._money(["12.50", "900"]) is None       # below the floor
    assert hcaa_ppo._money(["25,000,000"]) == 25_000_000.0


def test_the_month_candidates_try_the_report_month_and_the_one_before():
    """Discovery found the April 2026 report filed under 2026-04 next to
    another, so the folder is not always the report's own month."""
    cands = hcaa_ppo._month_candidates(1)
    folders = {c[0] for c in cands}
    assert len(folders) >= 2
    assert all(len(c[0]) == 7 and c[0][4] == "-" for c in cands)


# -------------------------------------------------------------------- dbpr

from sources import dbpr_hr  # noqa: E402

# The exact 38-name header the four extracts ship.
FOOD_HEADER = ['Application Number', 'Application Type', 'Application Approval Date ',
               'Board Code', 'License Type Code', 'Licensee Name', 'Rank Code',
               'Modifier Code', 'Mailing Name', 'Mailing Street Address',
               'Mailing Address Line 2', 'Mailing Address Line 3', 'Mailing City',
               'Mailing State Code', 'Mailing Zip Code', 'Primary Phone Number',
               'Mailing County Code', 'Business Name', 'Filler',
               'Location Street Address', 'Location Address Line 2',
               'Location Address Line 3', 'Location City', 'Location State Code',
               'Location Zip Code', 'Location County Code', 'Location County',
               'Secondary Phone Number', 'District', 'Region', 'License Number',
               'Primary Status Code', 'Secondary Status Code', 'License Expiry Date',
               'Last Inspection Date', 'Number of Seats', 'Base Risk Level',
               'Secondary Risk Level']

# Verbatim from newfood.csv, 2026-09-14. Phone at 15, county code at 16.
ROW_BLUSH = ['1634414', 'Plan Review and Initial (COMBO SEAT)', '08/13/2026', '200',
             '2010', 'FNS RESTAURANTS INC', 'SEAT', '', 'FNS RESTAURANTS INC', '',
             '20156 OAKFLOWER AVE', ' ', 'TAMPA', 'FL', '33647', '646-251-4814',
             '39', 'BLUSH SOCIAL', ' ', '101 PHILIPPE PKWY SUITE B', '', '',
             'SAFETY HARBOR', 'FL', '34695', '62', 'Pinellas', '646-251-4814',
             'D3', '10', 'SEA6218939', '20', '20', '02/01/2027', '08/13/2026', '128']

# Verbatim from chgownr_food.csv, same day. Phone and county code SWAPPED.
ROW_HAVELI = ['1863868', 'Approve Change Owner Request', '07/17/2026', '200', '2010',
              'JAI BUA RANI LLC', 'SEAT', '', 'JAI BUA RANI LLC', '',
              '12908 N DALE MABRY HWY', ' ', 'TAMPA', 'FL', '33618', '39',
              '8134886294', 'HAVELI INDIAN KITCHEN', ' ', '12908  N DALE MABRY HWY',
              '', '', 'TAMPA ', 'FL', '33618', '39', 'Hillsborough', '813-488-6294',
              'D3', '15', 'SEA3917924', '20', '20', '02/01/2027', '07/17/2026', '40']


def test_a_tampa_mailing_address_is_not_a_tampa_job():
    """BLUSH SOCIAL mails to Tampa 33647 and builds in Safety Harbor, Pinellas.
    A blanket text match for 'Tampa' imports it as a Tampa lead."""
    rec = dbpr_hr._row(FOOD_HEADER, ROW_BLUSH)
    assert rec["Mailing City"] == "TAMPA"
    assert rec["Location County"] == "Pinellas"
    assert dbpr_hr._in_tampa(rec) is False


def test_a_real_hillsborough_row_is_kept():
    rec = dbpr_hr._row(FOOD_HEADER, ROW_HAVELI)
    assert dbpr_hr._in_tampa(rec) is True
    assert rec["Business Name"] == "HAVELI INDIAN KITCHEN"


def test_the_phone_and_county_code_swap_is_repaired():
    """The same 38-name header ships with two different column orders. In
    chgownr_food.csv the phone lands in the county-code column."""
    ok = dbpr_hr._row(FOOD_HEADER, ROW_BLUSH)
    assert ok["Primary Phone Number"] == "646-251-4814"
    assert not ok.get("_swapped_phone_county")

    swapped = dbpr_hr._row(FOOD_HEADER, ROW_HAVELI)
    assert swapped["_swapped_phone_county"] is True
    assert swapped["Primary Phone Number"] == "8134886294"   # repaired
    assert swapped["Mailing County Code"] == "39"


def test_the_signal_carries_the_trading_name_a_phone_and_the_seat_count():
    rec = dbpr_hr._row(FOOD_HEADER, ROW_HAVELI)
    sig = dbpr_hr._signal(rec, "chgownr_food.csv", "Food-service change of ownership",
                          "restaurant", "dbpr_hr", "2026-07-17",
                          "2026-09-14T00:00:00", None)
    # The trading name is what you ask for on the phone, not the holding company.
    assert sig["entity"] == "HAVELI INDIAN KITCHEN"
    assert sig["applicant"] == "JAI BUA RANI LLC"
    assert {"kind": "phone", "value": "(813) 488-6294"} in sig["contacts"]
    assert sig["seats"] == 40
    assert sig["licence_number"] == "SEA3917924"
    assert sig["trade"] == "restaurant"


def test_without_a_geocoder_the_row_admits_it_does_not_know_the_submarket():
    """ZIP is not a submarket — 33602 alone spans Downtown, the Riverwalk,
    Water Street and the Channel District."""
    rec = dbpr_hr._row(FOOD_HEADER, ROW_HAVELI)
    sig = dbpr_hr._signal(rec, "x.csv", "l", "restaurant", "dbpr_hr", None,
                          "2026-09-14T00:00:00", None)
    assert sig["hood"] is None
    assert sig["needs_geocode"] is True


def test_with_a_geocoder_the_row_lands_in_a_real_submarket():
    sig = dbpr_hr._signal(dbpr_hr._row(FOOD_HEADER, ROW_HAVELI), "x.csv", "l",
                          "restaurant", "dbpr_hr", None, "2026-09-14T00:00:00",
                          lambda s, c, st, z: (-82.4400, 27.9560))   # Ybor
    assert sig["needs_geocode"] is False
    assert sig["hood"] == "ybor"


def test_a_single_family_rental_is_not_a_commercial_fitout():
    """newlodg.csv is full of DWEL/SNGL rows — somebody's house on a rental
    licence. They are not buildouts."""
    header = [h for h in FOOD_HEADER if h != "Location County"]
    row = list(ROW_HAVELI)
    row[6] = "DWEL"
    rec = dbpr_hr._row(FOOD_HEADER, row)
    sig = dbpr_hr._signal(rec, "newlodg.csv", "New lodging licence", "hospitality",
                          "dbpr_hr", None, "2026-09-14T00:00:00", None)
    assert sig["is_dwelling"] is True
    assert sig["is_fitout"] is False
    assert header  # newlodg genuinely lacks Location County


def test_newlodg_has_no_location_county_and_falls_back_to_the_city():
    """Trap 2: the lodging file ships a different, shorter header."""
    header = [h for h in FOOD_HEADER if h != "Location County"]
    values = [v for i, v in enumerate(ROW_HAVELI) if FOOD_HEADER[i] != "Location County"]
    rec = dbpr_hr._row(header, values)
    assert "Location County" not in rec
    assert rec["Location City"] == "TAMPA"
    assert dbpr_hr._in_tampa(rec) is True
