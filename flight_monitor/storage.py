"""SQLite-backed price history for flight monitoring."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).parent / "data" / "prices.db"


@dataclass
class FlightOffer:
    origin: str
    destination: str
    departure_date: str
    return_date: str
    stay_days: int
    total_price_usd: float
    currency: str
    airline: str
    stops: int
    duration_minutes: int | None
    booking_link: str
    source: str
    raw_summary: str
    monitor_id: str = "natal"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id TEXT NOT NULL DEFAULT 'natal',
                checked_at TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                departure_date TEXT NOT NULL,
                return_date TEXT NOT NULL,
                stay_days INTEGER NOT NULL,
                total_price_usd REAL NOT NULL,
                currency TEXT NOT NULL,
                airline TEXT,
                stops INTEGER,
                duration_minutes INTEGER,
                booking_link TEXT,
                source TEXT NOT NULL,
                raw_summary TEXT,
                UNIQUE(monitor_id, origin, destination, departure_date, return_date, stay_days, source, airline, total_price_usd)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id TEXT NOT NULL DEFAULT 'natal',
                checked_at TEXT NOT NULL,
                queries_run INTEGER NOT NULL,
                offers_found INTEGER NOT NULL,
                best_price_usd REAL,
                best_origin TEXT,
                best_destination TEXT,
                best_departure TEXT,
                best_return TEXT,
                notes TEXT
            )
            """
        )
        _migrate_add_monitor_id(conn)


def _migrate_add_monitor_id(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(offers)")}
    if "monitor_id" not in cols:
        conn.execute("ALTER TABLE offers ADD COLUMN monitor_id TEXT NOT NULL DEFAULT 'natal'")
    run_cols = {row[1] for row in conn.execute("PRAGMA table_info(run_log)")}
    if "monitor_id" not in run_cols:
        conn.execute("ALTER TABLE run_log ADD COLUMN monitor_id TEXT NOT NULL DEFAULT 'natal'")
    if "best_destination" not in run_cols:
        conn.execute("ALTER TABLE run_log ADD COLUMN best_destination TEXT")


def save_offer(offer: FlightOffer) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO offers (
                monitor_id, checked_at, origin, destination, departure_date, return_date,
                stay_days, total_price_usd, currency, airline, stops,
                duration_minutes, booking_link, source, raw_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer.monitor_id,
                datetime.now(timezone.utc).isoformat(),
                offer.origin,
                offer.destination,
                offer.departure_date,
                offer.return_date,
                offer.stay_days,
                offer.total_price_usd,
                offer.currency,
                offer.airline,
                offer.stops,
                offer.duration_minutes,
                offer.booking_link,
                offer.source,
                offer.raw_summary,
            ),
        )


def log_run(
    monitor_id: str,
    queries_run: int,
    offers_found: int,
    best: FlightOffer | None,
    notes: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO run_log (
                monitor_id, checked_at, queries_run, offers_found, best_price_usd,
                best_origin, best_destination, best_departure, best_return, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                monitor_id,
                datetime.now(timezone.utc).isoformat(),
                queries_run,
                offers_found,
                best.total_price_usd if best else None,
                best.origin if best else None,
                best.destination if best else None,
                best.departure_date if best else None,
                best.return_date if best else None,
                notes,
            ),
        )


def get_searched_combos(monitor_id: str) -> set[tuple[str, str, str, str]]:
    """Return (origin, destination, departure_date, return_date) combos already queried."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT origin, destination, departure_date, return_date
            FROM offers WHERE monitor_id = ?
            """,
            (monitor_id,),
        ).fetchall()
    return {(r["origin"], r["destination"], r["departure_date"], r["return_date"]) for r in rows}


def get_all_time_best(monitor_id: str) -> FlightOffer | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM offers
            WHERE monitor_id = ?
            ORDER BY total_price_usd ASC
            LIMIT 1
            """,
            (monitor_id,),
        ).fetchone()
    return _row_to_offer(row) if row else None


def get_recent_best(hours: int = 24) -> FlightOffer | None:
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM offers ORDER BY checked_at DESC LIMIT 500"
        ).fetchall()
    best: FlightOffer | None = None
    for row in rows:
        checked = datetime.fromisoformat(row["checked_at"])
        if checked.timestamp() < cutoff:
            continue
        offer = _row_to_offer(row)
        if best is None or offer.total_price_usd < best.total_price_usd:
            best = offer
    return best


def get_top_offers(monitor_id: str, limit: int = 10) -> list[FlightOffer]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT monitor_id, origin, destination, departure_date, return_date, stay_days,
                   MIN(total_price_usd) AS total_price_usd, currency,
                   airline, stops, duration_minutes, booking_link, source, raw_summary,
                   MAX(checked_at) AS checked_at
            FROM offers
            WHERE monitor_id = ?
            GROUP BY origin, destination, departure_date, return_date, stay_days
            ORDER BY total_price_usd ASC
            LIMIT ?
            """,
            (monitor_id, limit),
        ).fetchall()
    return [_row_to_offer(r) for r in rows]


def _row_to_offer(row: sqlite3.Row) -> FlightOffer:
    keys = row.keys()
    return FlightOffer(
        monitor_id=row["monitor_id"] if "monitor_id" in keys else "natal",
        origin=row["origin"],
        destination=row["destination"],
        departure_date=row["departure_date"],
        return_date=row["return_date"],
        stay_days=row["stay_days"],
        total_price_usd=float(row["total_price_usd"]),
        currency=row["currency"],
        airline=row["airline"] or "",
        stops=int(row["stops"] or 0),
        duration_minutes=row["duration_minutes"],
        booking_link=row["booking_link"] or "",
        source=row["source"],
        raw_summary=row["raw_summary"] or "",
    )


def export_summary(monitor_id: str) -> dict:
    best = get_all_time_best(monitor_id)
    top = get_top_offers(monitor_id, 5)
    return {
        "monitor_id": monitor_id,
        "all_time_best": asdict(best) if best else None,
        "top_offers": [asdict(o) for o in top],
    }


def summary_json(monitor_id: str) -> str:
    return json.dumps(export_summary(monitor_id), indent=2)
