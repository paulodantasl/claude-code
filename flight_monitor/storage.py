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
                UNIQUE(origin, destination, departure_date, return_date, stay_days, source, airline, total_price_usd)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT NOT NULL,
                queries_run INTEGER NOT NULL,
                offers_found INTEGER NOT NULL,
                best_price_usd REAL,
                best_origin TEXT,
                best_departure TEXT,
                best_return TEXT,
                notes TEXT
            )
            """
        )


def save_offer(offer: FlightOffer) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO offers (
                checked_at, origin, destination, departure_date, return_date,
                stay_days, total_price_usd, currency, airline, stops,
                duration_minutes, booking_link, source, raw_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
    queries_run: int,
    offers_found: int,
    best: FlightOffer | None,
    notes: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO run_log (
                checked_at, queries_run, offers_found, best_price_usd,
                best_origin, best_departure, best_return, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                queries_run,
                offers_found,
                best.total_price_usd if best else None,
                best.origin if best else None,
                best.departure_date if best else None,
                best.return_date if best else None,
                notes,
            ),
        )


def get_searched_combos() -> set[tuple[str, str, str]]:
    """Return (origin, departure_date, return_date) combos already queried."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT origin, departure_date, return_date
            FROM offers
            """
        ).fetchall()
    return {(r["origin"], r["departure_date"], r["return_date"]) for r in rows}


def get_all_time_best() -> FlightOffer | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM offers
            ORDER BY total_price_usd ASC
            LIMIT 1
            """
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


def get_top_offers(limit: int = 10) -> list[FlightOffer]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT origin, destination, departure_date, return_date, stay_days,
                   MIN(total_price_usd) AS total_price_usd, currency,
                   airline, stops, duration_minutes, booking_link, source, raw_summary,
                   MAX(checked_at) AS checked_at
            FROM offers
            GROUP BY origin, departure_date, return_date, stay_days
            ORDER BY total_price_usd ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_offer(r) for r in rows]


def _row_to_offer(row: sqlite3.Row) -> FlightOffer:
    return FlightOffer(
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


def export_summary() -> dict:
    best = get_all_time_best()
    top = get_top_offers(5)
    return {
        "all_time_best": asdict(best) if best else None,
        "top_offers": [asdict(o) for o in top],
    }


def summary_json() -> str:
    return json.dumps(export_summary(), indent=2)
