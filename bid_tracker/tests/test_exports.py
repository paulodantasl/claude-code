import json
import subprocess
from pathlib import Path

import pytest

from bid_tracker.importer import import_package
from bid_tracker import db
from bid_tracker.notion import NOTION_SCHEMA, ack, ddl, export, load_map, save_map
from conftest import FAKE_VALID, REPO


@pytest.fixture
def loaded(conn):
    assert import_package(conn, FAKE_VALID, fixtures=True).status == "ok"
    return conn


def test_xlsx_export(loaded, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from bid_tracker.export_xlsx import SHEETS, build

    out = build(loaded, tmp_path / "t.xlsx")
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == SHEETS
    assert wb["Solicitations"].max_row == 4
    assert wb["Bids"]["B1"].value == "Bidder"


def test_notion_manifest_matches_schema_and_deltas(loaded, tmp_path):
    path = export(loaded, tmp_path)
    m = json.loads(path.read_text())
    tabs = [o for o in m["ops"] if o["db"] == "bid_tabs"]
    assert len(tabs) == 3 and all(o["op"] == "create" for o in tabs)
    for op in m["ops"]:
        allowed = set(NOTION_SCHEMA[op["db"]]["properties"])
        for key in op["properties"]:
            name = key.split(":")[1] if key.startswith("date:") else key
            assert name in allowed, f"{op['db']}: {key} not in NOTION_SCHEMA"
    assert all(o["properties"]["Source URL"] for o in tabs)
    opts = m["options"]
    assert "FAKE City of Testville" in opts["bid_tabs"]["Agency"]
    assert "fake-city" in opts["bidders"]["Agencies"]
    with_bids = [o for o in tabs if o["ref"] != "fake-county:RFP-25-010"]   # rate-card-only tab has no bidders
    assert all(o.get("pending_relations") for o in with_bids)              # bidders not in Notion yet
    acks = [{"db": o["db"], "ref": o["ref"], "page_id": f"page-{i}", "hash": o["hash"]}
            for i, o in enumerate(m["ops"]) if o["db"] != "updates"]
    assert ack(loaded, acks) == len(acks)
    second = json.loads(export(loaded, tmp_path).read_text())
    # Relations now resolve, so tabs re-sync once; nothing else changed.
    assert {o["db"] for o in second["ops"]} <= {"bid_tabs", "pursuits", "updates"}
    acks2 = [{"db": o["db"], "ref": o["ref"], "page_id": o["page_id"], "hash": o["hash"]}
             for o in second["ops"] if o["db"] != "updates"]
    ack(loaded, acks2)
    third = json.loads(export(loaded, tmp_path).read_text())
    assert third["ops"] == []
    # A rebuilt DB that reloads the saved map updates the same pages instead of creating new ones.
    assert save_map(loaded, tmp_path / "notion_map.csv") == len(acks)
    fresh = db.connect(tmp_path / "rebuilt.db")
    db.init_db(fresh)
    assert import_package(fresh, FAKE_VALID, fixtures=True).status == "ok"
    assert load_map(fresh, tmp_path / "notion_map.csv") == len(acks)
    assert json.loads(export(fresh, tmp_path).read_text())["ops"] == []


def test_notion_ddl_has_every_property():
    for key, spec in NOTION_SCHEMA.items():
        text = ddl(key)
        for name in spec["properties"]:
            assert f'"{name}"' in text


def test_repo_hygiene():
    """This repo is public: only code, docs and synthetic fixtures may be tracked under bid_tracker/."""
    files = subprocess.run(["git", "ls-files", "--others", "--cached", "--exclude-standard", "bid_tracker"],
                           cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    allowed_suffix = (".py", ".md", ".sql", ".toml", ".ini", ".txt")
    for f in files:
        ok = f.endswith(allowed_suffix) or f.startswith("bid_tracker/tests/fixtures/") or f == "bid_tracker/reference/agencies.csv"
        assert ok, f"{f} would be committed; data belongs in the private data repo"
    for f in files:
        if f.startswith("bid_tracker/tests/fixtures/") and f.endswith(".csv"):
            text = (REPO / f).read_text()
            for line in text.splitlines()[1:]:
                urls = [w for w in line.replace('"', " ").replace(",", " ").split() if w.startswith("http")]
                assert all(u.startswith("https://example.invalid/") for u in urls), f"{f}: real URL in a fixture"
    ignored = subprocess.run(["git", "check-ignore", "bid_tracker/data/bids.db", "bid_tracker/data/x/solicitations.csv",
                              "bid_tracker/foo.xlsx"], cwd=REPO, capture_output=True, text=True).stdout.split()
    assert len(ignored) == 3


def test_reference_agencies_are_public_metadata_only():
    header = (Path(REPO) / "bid_tracker/reference/agencies.csv").read_text().splitlines()[0]
    assert header == "agency_id,name,agency_type,county,portal_platform,portal_url,watch,notes"
