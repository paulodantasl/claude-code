"""Connection, paths, and schema initialisation."""

from __future__ import annotations

import csv
import os
import sqlite3
import tomllib
from pathlib import Path

from bid_tracker import taxonomy
from bid_tracker.names import name_key

PKG_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = PKG_DIR / "schema.sql"
SOURCES_PATH = PKG_DIR / "sources.toml"
AGENCIES_PATH = PKG_DIR / "reference" / "agencies.csv"
LOCAL_DATA_DIR = PKG_DIR / "data"
SCHEMA_VERSION = "1"


def data_dir() -> Path:
    """Root of the private data repo clone, or the gitignored local folder."""
    env = os.environ.get("BID_TRACKER_DATA")
    return Path(env).expanduser().resolve() if env else LOCAL_DATA_DIR


def default_db_path() -> Path:
    env = os.environ.get("BID_TRACKER_DB")
    return Path(env).expanduser().resolve() if env else data_dir() / "bids.db"


def is_default_db(path: Path) -> bool:
    return Path(path).resolve() == default_db_path()


def load_sources() -> dict:
    with open(SOURCES_PATH, "rb") as fh:
        return tomllib.load(fh)


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else default_db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection, seed: bool = True) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    cols = {r[1] for r in conn.execute("PRAGMA table_info(solicitations)")}
    if "area_kind" not in cols:   # DB made before area kinds; `rebuild` gives the full schema
        conn.execute("ALTER TABLE solicitations ADD COLUMN area_kind TEXT "
                     "CHECK (area_kind IN ('building_gsf','scope_area','roof_area'))")
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
    )
    if seed:
        seed_reference(conn)
    conn.commit()


def seed_reference(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO project_types(code, work_class, label, phase1_core) VALUES (?,?,?,?)",
        taxonomy.PROJECT_TYPES,
    )
    with open(AGENCIES_PATH, newline="") as fh:
        for row in csv.DictReader(fh):
            upsert_agency(conn, row)
    sources = load_sources()
    for s in sources.get("cost_index_series", []):
        conn.execute(
            "INSERT OR REPLACE INTO cost_index_series(series_id, title, applies_to) VALUES (?,?,?)",
            (s["series_id"], s.get("title"), ",".join(s.get("applies_to", []))),
        )
    ideal = sources.get("ideal_bidder")
    if ideal:
        ensure_ideal_bidder(conn, ideal)


def upsert_agency(conn: sqlite3.Connection, row: dict) -> None:
    county = (row.get("county") or "").strip() or None
    region = (row.get("region") or "").strip() or taxonomy.region_for(county) or "other"
    conn.execute(
        """INSERT INTO agencies(agency_id, name, agency_type, county, region, portal_platform, portal_url, watch, notes)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(agency_id) DO UPDATE SET
             name=excluded.name, agency_type=excluded.agency_type, county=excluded.county,
             region=excluded.region,
             portal_platform=coalesce(excluded.portal_platform, agencies.portal_platform),
             portal_url=coalesce(excluded.portal_url, agencies.portal_url),
             watch=excluded.watch, notes=coalesce(excluded.notes, agencies.notes)""",
        (
            row["agency_id"].strip(),
            row["name"].strip(),
            row["agency_type"].strip(),
            county,
            region,
            (row.get("portal_platform") or "").strip() or None,
            (row.get("portal_url") or "").strip() or None,
            int(row.get("watch") or 0),
            (row.get("notes") or "").strip() or None,
        ),
    )


def ensure_ideal_bidder(conn: sqlite3.Connection, ideal: dict) -> int:
    key = name_key(ideal["canonical_name"])
    row = conn.execute("SELECT bidder_id FROM bidders WHERE name_key = ?", (key,)).fetchone()
    if row:
        bidder_id = row["bidder_id"]
    else:
        bidder_id = conn.execute(
            """INSERT INTO bidders(canonical_name, name_key, fl_license_no, hq_city, hq_county, is_ideal)
               VALUES (?,?,?,?,?,1)""",
            (ideal["canonical_name"], key, ideal.get("fl_license_no"), ideal.get("hq_city"), ideal.get("hq_county")),
        ).lastrowid
    for alias in ideal.get("aliases", []):
        conn.execute(
            "INSERT OR IGNORE INTO bidder_aliases(alias_key, bidder_id, alias_raw) VALUES (?,?,?)",
            (name_key(alias), bidder_id, alias),
        )
    return bidder_id


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = ["agencies", "solicitations", "bids", "bidders", "bid_items", "rate_cards", "cost_index", "ideal_pursuits",
              "solicitation_areas"]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
