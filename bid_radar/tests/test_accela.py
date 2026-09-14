"""
Accela record-page parsing.

The fixture is the real page for BLD-26-0526061 — the Wagamama fitout at
1050 Water St — saved from a GitHub Actions run on 2026-09-14. It is the page
that showed this source carries everything the ArcGIS layer does not.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import accela  # noqa: E402
import enrich  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "accela_BLD-26-0526061.html")

pytestmark = pytest.mark.skipif(not os.path.exists(FIXTURE),
                                reason="accela fixture not present")


@pytest.fixture(scope="module")
def parsed():
    with open(FIXTURE, encoding="utf-8", errors="replace") as fh:
        return accela.parse(fh.read())


def test_the_contractor_of_record_is_the_whole_point(parsed):
    """Without this the win-rate dataset does not exist."""
    gc = parsed["contractor"]
    assert gc["company"] == "TWT RESTAURANT DESIGN CONSTRUCTION & DEVELOPMENT COMPANY"
    assert gc["licence"] == "CBC1262713"
    assert "permits@twtconstruction.com" in gc["emails"]


def test_the_applicant_carries_a_phone_and_an_email(parsed):
    a = parsed["applicant"]
    assert a["name"] == "Stephen Torres"
    assert a["phones"] == ["9728079257"]
    assert a["emails"] == ["storres@weareharrison.com"]


def test_the_valuation_the_arcgis_layer_omits(parsed):
    assert parsed["job_value"] == 300_000.0
    assert parsed["sqft"] == 4_525.0


def test_the_owner_is_named(parsed):
    assert "Strategic Property Partners" in parsed["owner"]


def test_the_subcontractors_on_the_record(parsed):
    companies = [s["company"] for s in parsed["subs"]]
    assert any("DUFFY ELECTRIC" in c for c in companies)
    assert any("JOHNSON CONTROLS" in c for c in companies)
    assert all(s["licence"] for s in parsed["subs"])


def test_contacts_are_deduped_and_attributed(parsed):
    contacts = accela.contacts_from(parsed)
    values = [c["value"] for c in contacts]
    assert len(values) == len(set(values))
    assert all(c["from"].startswith("accela.") for c in contacts)
    assert {c["kind"] for c in contacts} <= {"phone", "email"}


def test_merge_fills_what_the_permit_layer_could_not(parsed):
    sig = {"source": "permit", "source_id": "BLD-26-0526061", "hood": "waterst",
           "entity": "Wagamama Pan Asian", "value_est": None, "sqft": None,
           "contacts": []}
    enrich._merge(sig, parsed)
    assert sig["value_est"] == 300_000.0
    assert sig["sqft"] == 4_525.0
    assert sig["contacts"]
    assert sig["contractor_name"].startswith("TWT")
    assert sig["contractor_licence"] == "CBC1262713"
    assert sig["enriched"] == "accela"
    # a name the description already gave us is never overwritten by the
    # permit expediter's
    assert sig["entity"] == "Wagamama Pan Asian"


def test_merge_only_fills_a_missing_entity(parsed):
    sig = {"source": "permit", "source_id": "X", "hood": "waterst",
           "entity": None, "contacts": []}
    enrich._merge(sig, parsed)
    assert sig["entity"] == "Stephen Torres"


def test_merge_does_not_duplicate_a_contact_already_present(parsed):
    sig = {"source": "permit", "source_id": "X", "hood": "waterst", "entity": "X",
           "contacts": [{"kind": "email", "value": "permits@twtconstruction.com",
                         "from": "elsewhere"}]}
    enrich._merge(sig, parsed)
    values = [c["value"].lower() for c in sig["contacts"]]
    assert len(values) == len(set(values))


def test_to_text_strips_scripts_and_styles():
    out = accela.to_text("<div>keep<script>var x=1</script><style>a{}</style>this</div>")
    assert "var x" not in out and "a{}" not in out
    assert "keep" in out and "this" in out


@pytest.mark.parametrize("text,expected", [
    ("Building Contractor CBC1262713", "CBC1262713"),
    ("Electrical Contractor EC13008796", "EC13008796"),
    ("Private Provider-Qualifier BU1376", "BU1376"),
    ("no licence here", None),
])
def test_licence_formats(text, expected):
    m = accela.LICENCE.search(text)
    assert (m.group(1).replace(" ", "") if m else None) == expected
