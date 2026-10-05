"""Square footage by kind: areas.csv, the stronger-basis rule, the preferred-kind pick, and like-with-like $/SF."""

import csv
from pathlib import Path

from bid_tracker.areas import coverage
from bid_tracker.benchmark import benchmark
from bid_tracker.canonical import SPECS
from bid_tracker.importer import import_package
from bid_tracker.validate import has_errors

from conftest import edit_csv, synth_package

URL = "https://example.invalid/plans/A0.1.pdf"


def write_areas(dest: Path, rows: list[dict]) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    cols = list(SPECS["areas.csv"])
    with open(dest / "areas.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return dest


def area(ref, kind, sf, basis="stated", **kw):
    row = {"sol_ref": ref, "area_kind": kind, "sf": str(sf), "basis": basis, "source_url": URL,
           "source_page": "sheet A0.1", "excerpt": f"BUILDING AREA: {sf:,} SF (code data)", "retrieved_at": "2026-01-20"}
    row.update(kw)
    return row


def sol(conn, ref):
    return conn.execute("SELECT gsf, gsf_basis, area_kind FROM solicitations WHERE sol_ref = ?", (ref,)).fetchone()


def test_legacy_gsf_becomes_an_area_of_the_preferred_kind(conn, pkg_copy):
    import_package(conn, pkg_copy, fixtures=True)
    assert tuple(sol(conn, "fake-schools:ITB-25-033")) == (6000, "stated", "scope_area")
    assert tuple(sol(conn, "fake-city:ITB-24-001")) == (1800, "stated", "scope_area")
    assert sol(conn, "fake-county:RFP-25-010")["gsf"] is None


def test_area_survives_a_later_update_with_blank_gsf(conn, pkg_copy, tmp_path):
    import_package(conn, pkg_copy, fixtures=True)
    res = import_package(conn, write_areas(tmp_path / "a", [area("fake-schools:ITB-25-033", "scope_area", 7250)]),
                         fixtures=True)
    assert res.status == "ok" and res.areas == 1 and res.updated_refs == ["fake-schools:ITB-25-033"]
    assert sol(conn, "fake-schools:ITB-25-033")["gsf"] == 7250

    def blank(rows):
        for r in rows:
            r["gsf"] = r["gsf_basis"] = ""
            r["title"] += " (re-posted)"
    edit_csv(pkg_copy / "solicitations.csv", blank)
    res = import_package(conn, pkg_copy, fixtures=True)
    assert res.status == "ok" and "fake-schools:ITB-25-033" in res.updated_refs
    assert tuple(sol(conn, "fake-schools:ITB-25-033")) == (7250, "stated", "scope_area")


def test_preferred_kind_and_stronger_basis(conn, pkg_copy, tmp_path):
    import_package(conn, pkg_copy, fixtures=True)
    ref = "fake-schools:ITB-25-033"   # V-REN: scope area only
    import_package(conn, write_areas(tmp_path / "a", [area(ref, "building_gsf", 40000, "derived",
                                                           excerpt="Heated area 40,000 SF per appraiser")]),
                   fixtures=True)
    assert sol(conn, ref)["area_kind"] == "scope_area"           # the legacy 6,000 SF scope area still wins
    # A derived figure can't replace a stated one of the same kind; a stated one replaces a derived one.
    import_package(conn, write_areas(tmp_path / "b", [area(ref, "scope_area", 9999, "derived",
                                                           excerpt="Area 9,999 SF per appraiser")]), fixtures=True)
    assert sol(conn, ref)["gsf"] == 6000
    import_package(conn, write_areas(tmp_path / "c", [area(ref, "building_gsf", 41000)]), fixtures=True)
    row = conn.execute("SELECT sf, basis FROM solicitation_areas WHERE sol_ref = ? AND area_kind = 'building_gsf'",
                       (ref,)).fetchone()
    assert tuple(row) == (41000, "stated")
    # A kind the project type doesn't use never becomes its gsf: a whole building isn't a remodel's scope.
    conn.execute("DELETE FROM solicitation_areas WHERE sol_ref = ? AND area_kind = 'scope_area'", (ref,))
    import_package(conn, write_areas(tmp_path / "e", [area("fake-city:ITB-24-001", "scope_area", 1800)]), fixtures=True)
    assert sol(conn, ref)["gsf"] is None and sol(conn, ref)["area_kind"] is None
    conn.execute("DELETE FROM solicitation_areas WHERE sol_ref = ?", (ref,))
    import_package(conn, write_areas(tmp_path / "d", [area(ref, "roof_area", 12000)]), fixtures=True)
    assert sol(conn, ref)["gsf"] is None


def test_validation(conn, pkg_copy, tmp_path):
    import_package(conn, pkg_copy, fixtures=True)
    ref = "fake-schools:ITB-25-033"
    rows = [
        area(ref, "scope_area", 5000, excerpt="Renovate the media center, about five thousand SF"),   # E-NOSRC
        area(ref, "building_gsf", 30000, "measured", excerpt="Scaled from floor plan sheet A1.1"),   # E-AREA
        area(ref, "building_gsf", 30000),                                                           # E-DUP
        area("fake-schools:ITB-99-999", "scope_area", 2000),                                         # W-REF only
        area(ref, "roof_area", 0),                                                                   # E-NUM
        area("fake-city:ITB-24-001", "building_gsf", 31700, "derived",                               # a sum: ok
             excerpt="the 20,700 square foot training center and the 11,000 square foot clubhouse"),
        area("fake-city:ITB-24-001", "scope_area", 31700,                                           # E-NOSRC
             excerpt="the 20,700 square foot training center and the 11,000 square foot clubhouse"),
    ]
    res = import_package(conn, write_areas(tmp_path / "a", rows), fixtures=True)
    codes = {(i.severity, i.code, i.line) for i in res.issues}
    assert has_errors(res.issues) and res.status == "failed"
    assert {("ERROR", "E-NOSRC", 2), ("ERROR", "E-AREA", 3), ("ERROR", "E-DUP", 4), ("WARN", "W-REF", 5),
            ("ERROR", "E-NUM", 6), ("ERROR", "E-NOSRC", 8)} <= codes
    assert not any(i.line == 7 and i.severity == "ERROR" for i in res.issues)


def test_orphans_apply_once_the_solicitation_arrives(conn, pkg_copy, tmp_path):
    ref = "fake-schools:ITB-25-033"
    res = import_package(conn, write_areas(tmp_path / "a", [area(ref, "scope_area", 6100)]), fixtures=True)
    assert res.status == "ok"
    assert [o["sol_ref"] for o in coverage(conn)["orphans"]] == [ref]
    edit_csv(pkg_copy / "solicitations.csv", lambda rows: [r.update(gsf="", gsf_basis="") for r in rows])
    import_package(conn, pkg_copy, fixtures=True)
    assert sol(conn, ref)["gsf"] == 6100 and coverage(conn)["orphans"] == []
    c = coverage(conn)["coverage"]
    assert (c["tabs"], c["with_area"]) == (2, 1)   # the term contract isn't a per-project tab


def test_psf_compares_one_kind_only(conn, tmp_path):
    # V-MEP uses whole-building GSF first, then scope area: both kinds can be a tab's gsf.
    pkg = synth_package(tmp_path / "synth", n_jobs=12, project_type="V-MEP")
    import_package(conn, pkg, fixtures=True)
    conn.execute("UPDATE solicitation_areas SET area_kind = 'scope_area' WHERE sol_ref IN "
                 "(SELECT sol_ref FROM solicitations ORDER BY sol_ref LIMIT 4)")
    from bid_tracker.importer import sync_areas
    sync_areas(conn)
    b = benchmark(conn, project_type="V-MEP", since=None)
    assert b["n"] == 12 and b["low_psf_kind"] == "building_gsf" and b["low_psf_esc"]["n"] == 8
    b = benchmark(conn, project_type="V-MEP", since=None, area_kind="scope_area")
    assert b["low_psf_esc"]["n"] == 4
    # The default follows the data: with most tabs on scope area, $/SF pools those.
    conn.execute("UPDATE solicitation_areas SET area_kind = 'scope_area' WHERE sol_ref IN "
                 "(SELECT sol_ref FROM solicitations ORDER BY sol_ref LIMIT 8)")
    sync_areas(conn)
    b = benchmark(conn, project_type="V-MEP", since=None)
    assert b["low_psf_kind"] == "scope_area" and b["low_psf_esc"]["n"] == 8


def test_notion_clears_an_area_that_goes_away(conn, pkg_copy, tmp_path):
    import json
    from bid_tracker.importer import sync_areas
    from bid_tracker.notion import ack, export

    import_package(conn, pkg_copy, fixtures=True)
    for _ in range(3):   # sync until settled: tab relations resolve on the pass after bidders exist
        ops = [o for o in json.loads(export(conn, tmp_path).read_text())["ops"] if o["db"] != "updates"]
        ack(conn, [{"db": o["db"], "ref": o["ref"], "page_id": o["page_id"] or f"page-{o['ref']}",
                    "hash": o["hash"]} for o in ops])
    assert not ops
    ref = "fake-schools:ITB-25-033"
    conn.execute("DELETE FROM solicitation_areas WHERE sol_ref = ?", (ref,))
    sync_areas(conn)
    ops = [o for o in json.loads(export(conn, tmp_path).read_text())["ops"] if o["db"] == "bid_tabs"]
    assert [o["ref"] for o in ops] == [ref]          # tabs that never had an area don't churn
    assert ops[0]["op"] == "update" and ops[0]["properties"]["GSF"] is None
    assert ops[0]["properties"]["Area Kind"] is None and ops[0]["properties"]["Low $/SF"] is None
