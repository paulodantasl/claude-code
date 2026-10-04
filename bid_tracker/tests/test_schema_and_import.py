import sqlite3

import pytest

from bid_tracker import db, taxonomy
from bid_tracker.importer import import_package
from conftest import FAKE_VALID, edit_csv


def test_init_is_idempotent_and_seeded(conn):
    db.init_db(conn)
    counts = db.table_counts(conn)
    assert counts["agencies"] >= 25
    assert conn.execute("SELECT COUNT(*) FROM project_types").fetchone()[0] == len(taxonomy.PROJECT_TYPES)
    ideal = conn.execute("SELECT * FROM bidders WHERE is_ideal = 1").fetchall()
    assert len(ideal) == 1 and ideal[0]["fl_license_no"] == "CGC1537480"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    for view in ("v_bids_clean", "v_bid_order", "v_solicitation_base", "v_competitor_bids"):
        conn.execute(f"SELECT * FROM {view} LIMIT 1")


def test_schema_checks_accept_every_taxonomy_value(conn):
    # Catches drift between taxonomy.py and the CHECK constraints in schema.sql.
    for t in taxonomy.AGENCY_TYPES:
        conn.execute("INSERT INTO agencies(agency_id, name, agency_type) VALUES (?,?,?)", (f"fake-{t}", t, t))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO agencies(agency_id, name, agency_type) VALUES ('fake-x','x','bogus')")


def test_import_valid_package(conn):
    res = import_package(conn, FAKE_VALID, fixtures=True)
    assert res.status == "ok", [str(i) for i in res.issues]
    assert (res.new, res.bids_written, res.items_written, res.rates_written, res.pursuits, res.index_rows) == (3, 7, 4, 8, 1, 7)
    sol = conn.execute("SELECT * FROM v_solicitation_base WHERE sol_ref = 'fake-city:ITB-24-001'").fetchone()
    assert (sol["n_bidders"], sol["low_bid"], sol["second_bid"]) == (4, 100000, 110000)
    assert sol["awardee_name"] == "FAKE Builder Alpha LLC"
    # "FAKE Builder Beta, Inc." and "FAKE Builder Beta Inc." are one bidder.
    assert conn.execute("SELECT COUNT(*) FROM bidders WHERE name_key = 'fake builder beta'").fetchone()[0] == 1
    # Ideal's bid resolved to the seeded Ideal bidder.
    row = conn.execute("SELECT is_ideal FROM v_bids_clean WHERE sol_ref = 'fake-schools:ITB-25-033' AND total_bid = 845000").fetchone()
    assert row["is_ideal"] == 1


def test_reimport_adds_nothing(conn):
    import_package(conn, FAKE_VALID, fixtures=True)
    res = import_package(conn, FAKE_VALID, fixtures=True)
    assert (res.new, res.updated, res.unchanged) == (0, 0, 3)
    assert db.table_counts(conn)["bids"] == 7


def test_changed_bid_marks_solicitation_updated(conn, pkg_copy):
    import_package(conn, FAKE_VALID, fixtures=True)

    def bump(rows):
        r = next(r for r in rows if r["bidder_name_raw"] == "FAKE Delta Builders Corp")
        r["base_bid"] = r["total_bid"] = "$155,000.00"
    edit_csv(pkg_copy / "bids.csv", bump)
    res = import_package(conn, pkg_copy, fixtures=True)
    assert res.updated == 1 and res.updated_refs == ["fake-city:ITB-24-001"]


def test_lower_evidence_only_adds_a_source(conn, pkg_copy):
    import_package(conn, FAKE_VALID, fixtures=True)

    def downgrade(rows):
        for r in rows:
            r["evidence_class"] = "news"
            r["source_url"] = r["source_url"].replace(".pdf", "-news")
            r["title"] = "changed by a weaker source"
    edit_csv(pkg_copy / "solicitations.csv", downgrade)
    res = import_package(conn, pkg_copy, fixtures=True)
    assert res.source_only == 3
    title = conn.execute("SELECT title FROM solicitations WHERE sol_ref = 'fake-city:ITB-24-001'").fetchone()[0]
    assert title == "FAKE ADA restroom renovation Building A"
    assert conn.execute("SELECT COUNT(*) FROM solicitation_sources").fetchone()[0] == 6


def test_failed_import_writes_nothing_but_the_run_log(conn, pkg_copy):
    edit_csv(pkg_copy / "solicitations.csv", lambda rows: rows[0].update(source_url=""))
    res = import_package(conn, pkg_copy, fixtures=True)
    assert res.status == "failed"
    assert db.table_counts(conn)["solicitations"] == 0
    assert conn.execute("SELECT status FROM ingest_runs").fetchone()[0] == "failed"


def test_fixture_guard_in_cli(tmp_path, monkeypatch):
    from bid_tracker.cli import main
    monkeypatch.setenv("BID_TRACKER_DATA", str(tmp_path / "data"))
    with pytest.raises(SystemExit):
        main(["import-csv", str(FAKE_VALID), "--fixtures"])
    assert main(["--db", str(tmp_path / "scratch.db"), "import-csv", str(FAKE_VALID), "--fixtures"]) == 0


def test_search_snippet_rows_yield_to_official_sources(conn, pkg_copy, tmp_path):
    import shutil
    snippet = tmp_path / "snippet"
    shutil.copytree(pkg_copy, snippet)

    def as_snippet(rows):
        for r in rows:
            r["evidence_class"] = "search_snippet"
            r["date_basis"] = "board"
            r["notes"] = "number from a search-result snippet; page not fetched"
    edit_csv(snippet / "solicitations.csv", as_snippet)
    first = import_package(conn, snippet, fixtures=True)
    assert first.status == "ok" and first.new == 3
    assert conn.execute("SELECT date_basis FROM solicitations LIMIT 1").fetchone()[0] == "board"
    upgraded = import_package(conn, FAKE_VALID, fixtures=True)
    assert upgraded.updated == 3                     # official tab replaces the snippet rows
    row = conn.execute("SELECT evidence_class, date_basis FROM solicitations WHERE sol_ref = 'fake-city:ITB-24-001'").fetchone()
    assert tuple(row) == ("official_tab", "bid_open")
