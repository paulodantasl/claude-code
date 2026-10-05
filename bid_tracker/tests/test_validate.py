from datetime import date

import pytest

from bid_tracker.canonical import load_package, make_sol_ref, parse_money
from bid_tracker.validate import appears_in, check_url, has_errors, validate_package
from conftest import FAKE_VALID, edit_csv

KNOWN = {"known_agencies": set(), "known_sol_refs": set(), "known_bidders": {}}


def codes(path, fixtures=True, **kw):
    issues = validate_package(load_package(path), fixtures=fixtures, today=date(2026, 10, 1), **{**KNOWN, **kw})
    return {i.code for i in issues if i.severity == "ERROR"}, issues


def test_valid_package_has_no_errors():
    errors, issues = codes(FAKE_VALID)
    assert not errors, [str(i) for i in issues]


def test_money_parsing():
    assert parse_money("$1,234.50") == 1234.5
    assert parse_money("(500)") == -500
    assert parse_money("") is None


def test_sol_ref_normalisation():
    assert make_sol_ref("Fake-City", " itb 25-001 ") == "fake-city:ITB25-001"


def test_numbers_must_come_from_excerpts():
    assert appears_in(100000, ["low bidder $100,000.00"])
    assert not appears_in(100000, ["low bidder $1.0 million"])


@pytest.mark.parametrize("mutate, file, code", [
    (lambda r: r[0].update(source_url=""), "solicitations.csv", "E-SCHEMA"),
    (lambda r: r[0].update(source_excerpt="too short"), "solicitations.csv", "E-URL"),
    (lambda r: r[0].update(source_url="https://www.tampa.gov/real.pdf"), "solicitations.csv", "E-URL"),
    (lambda r: r[0].update(award_amount="$100,500.00"), "solicitations.csv", "E-NOSRC"),
    (lambda r: r[0].update(award_date="2024-01-01"), "solicitations.csv", "E-DATE"),
    (lambda r: r[0].update(date_basis="someday"), "solicitations.csv", "E-ENUM"),
    (lambda r: r[0].update(engineers_estimate="$900,000.00"), "solicitations.csv", "E-EE"),
    (lambda r: r[0].update(project_type="R-MOLD"), "solicitations.csv", "E-ENUM"),
    (lambda r: r[0].update(procurement_method="handshake"), "solicitations.csv", "E-ENUM"),
    (lambda r: r[0].update(sol_ref="fake-city:WRONG"), "solicitations.csv", "E-REF"),
    (lambda r: r[0].update(awardee_name="FAKE Delta Builders Corp"), "solicitations.csv", "E-LOW"),
    (lambda r: r[0].update(awardee_name="FAKE Delta Builders Corp"), "solicitations.csv", "E-AWARD"),
    (lambda r: r[0].update(total_bid="$101,000.00"), "bids.csv", "E-TOTAL"),
    (lambda r: r[1].update(rank_published="3"), "bids.csv", "E-RANK"),
    (lambda r: r.append(dict(r[1])), "bids.csv", "E-DUP"),
    (lambda r: r[0].update(extended="$16,000.00"), "bid_items.csv", "E-TOTAL"),
    (lambda r: r[0].update(price="$1,499.00"), "rate_cards.csv", "E-NOSRC"),
    (lambda r: r[0].update(markup_pct="7"), "ideal_pursuits.csv", "E-NUM"),
    (lambda r: r[0].update(period="2024-13"), "cost_index.csv", "E-DATE"),
])
def test_validator_rejects(pkg_copy, mutate, file, code):
    edit_csv(pkg_copy / file, mutate)
    errors, issues = codes(pkg_copy)
    assert code in errors, [str(i) for i in issues]


def test_derived_columns_are_refused(pkg_copy):
    p = pkg_copy / "solicitations.csv"
    lines = p.read_text().splitlines()
    lines[0] += ",low_bid"
    lines[1:] = [ln + ",1" for ln in lines[1:]]
    p.write_text("\n".join(lines) + "\n")
    errors, _ = codes(pkg_copy)
    assert "E-SCHEMA" in errors


def test_real_data_rules_reject_fixtures_outside_fixture_mode():
    errors, _ = codes(FAKE_VALID, fixtures=False)
    assert "E-URL" in errors   # example.invalid and fake- agencies are test-only
    assert check_url("https://example.invalid/x", "official_tab", False)
    assert check_url("https://www.tampa.gov/x.pdf", "official_tab", False) is None
    assert check_url("notion://page", "internal", False) is None
    assert check_url("notion://page", "official_tab", False)


def test_non_low_award_allowed_with_reason(pkg_copy):
    def reason(rows):
        rows[0].update(awardee_name="FAKE Builder Beta, Inc.", award_amount="$110,000.00",
                       source_excerpt="Award to FAKE Builder Beta, Inc. $110,000.00; low bidder non-responsive",
                       notes="low bidder found non-responsive")
    edit_csv(pkg_copy / "solicitations.csv", reason)

    def flags(rows):
        for r in rows:
            r["is_awardee"] = "1" if r["bidder_name_raw"] == "FAKE Builder Beta, Inc." else "0"
    edit_csv(pkg_copy / "bids.csv", flags)
    errors, issues = codes(pkg_copy)
    assert not errors, [str(i) for i in issues]


def test_near_duplicate_bidder_warns():
    _, issues = codes(FAKE_VALID, known_bidders={"fake builder alpha": "FAKE Builder Alpha LLC",
                                                  "fake builder alfa": "FAKE Builder Alfa LLC"})
    assert any(i.code == "W-NAME" for i in issues)
    assert not has_errors(issues)


def test_rows_added_to_a_known_solicitation_may_cite_internal_docs(tmp_path):
    import csv as _csv
    from bid_tracker.canonical import SPECS
    pkg = tmp_path / "private"
    pkg.mkdir()
    cols = list(SPECS["bids.csv"])
    with open(pkg / "bids.csv", "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerow({"sol_ref": "fake-city:ITB-24-001", "bidder_name_raw": "Ideal Remodeling LLC",
                    "total_bid": "$130,000.00", "total_basis": "base", "base_bid": "$130,000.00",
                    "source_url": "file:private/debrief.md", "source_excerpt": "Ideal bid $130,000.00"})
    errors, issues = codes(pkg, fixtures=False, known_sol_refs={"fake-city:ITB-24-001"})
    assert "E-URL" not in errors, [str(i) for i in issues]
