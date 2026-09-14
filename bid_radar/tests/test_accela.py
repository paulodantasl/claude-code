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


# --------------------------------------- defects found in the first live run

@pytest.mark.parametrize("block,name,company", [
    # A street address read as a construction firm. The first live run put
    # "N HOWARD AVE TAMPA" and "E FLETCHER AVE TAMPA" in the market-share table.
    ("Kelly Smith 1234 N Howard Ave Tampa, FL, 33607 Building Contractor CGC049808",
     "Kelly Smith", None),
    ("Justin Starnes 55 E Fletcher Ave Tampa, FL Building Contractor CGC1533664",
     "Justin Starnes", None),
    # Accela prints the qualifier and the firm in one run.
    ("Matthew Gilbert BARR & BARR INC 100 Main St Tampa, FL Building Contractor CGC1513535",
     "Matthew Gilbert", "BARR & BARR INC"),
    # The firm name must not be cut short at its first suffix word.
    ("Nicholas Tyson Roland permits@twt.com TWT RESTAURANT DESIGN CONSTRUCTION & "
     "DEVELOPMENT COMPANY 5553 W Waters Ave Tampa Building Contractor CBC1262713",
     "Nicholas Tyson Roland", "TWT RESTAURANT DESIGN CONSTRUCTION & DEVELOPMENT COMPANY"),
])
def test_party_parsing_defects_from_the_first_live_run(block, name, company):
    p = accela._party(block)
    assert p["name"] == name
    assert p["company"] == company


@pytest.mark.parametrize("text,suspect", [
    ("Job Value: 300000", False),
    ("Job Value: 75000", False),
    ("Job Value: 49000000", False),
    ("Job Value: 280000000", True),     # seen once; a fitout is not $280M
    ("Job Value: 500", True),           # seen once
])
def test_an_implausible_valuation_is_flagged_not_trusted(text, suspect):
    parsed = accela.parse(f"<html><body>{text}</body></html>")
    assert parsed["value_suspect"] is suspect


def test_a_suspect_value_is_kept_on_the_row_but_excluded_from_averages():
    import collect
    sig = {"source": "permit", "source_id": "X", "hood": "waterst", "contacts": []}
    enrich._merge(sig, {"job_value": 280_000_000.0, "value_suspect": True,
                        "contractor": {"company": "SOME BUILDERS INC",
                                       "licence": "CGC1", "emails": [], "phones": []}})
    assert sig["value_est"] == 280_000_000.0      # the record still says so
    assert sig["value_suspect"] is True
    row = collect.market_share([sig])[0]
    assert row["with_value"] == 0
    assert row["avg_value"] is None


def test_a_cancelled_run_keeps_the_pages_it_already_paid_for(tmp_path, monkeypatch):
    """A new push cancels the workflow mid-fetch. Nine minutes of 370 KB pages
    must not be thrown away because the run did not reach its final save."""
    monkeypatch.setattr(enrich, "CACHE_PATH", str(tmp_path / "accela_cache.json"))
    monkeypatch.setattr(enrich, "SAVE_EVERY", 2)
    monkeypatch.setattr(enrich, "PAUSE", 0.0)

    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        if len(fetched) == 5:            # the run is cancelled here
            raise KeyboardInterrupt
        return {"job_value": 250_000.0}

    monkeypatch.setattr(enrich, "fetch_one", fake_fetch)
    signals = [{"source": "permit", "source_id": f"BLD-{i}", "hood": "waterst",
                "source_url": f"https://aca.example/{i}"} for i in range(6)]

    with pytest.raises(KeyboardInterrupt):
        enrich.enrich(signals)

    kept = enrich.load_cache()
    assert sorted(k for k in kept if not k.startswith("_")) == ["BLD-0", "BLD-1",
                                                               "BLD-2", "BLD-3"]
