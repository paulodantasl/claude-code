"""Generate departure/return date pairs for the Natal trip window."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterator


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_date_pairs(
    departure_anchors: list[str],
    min_stay_days: int,
    preferred_stays: list[int] | None = None,
    departure_start: str | None = None,
    departure_end: str | None = None,
) -> Iterator[tuple[str, str, int]]:
    """Yield (departure, return, stay_days) tuples."""
    start = parse_date(departure_start) if departure_start else None
    end = parse_date(departure_end) if departure_end else None
    stays = preferred_stays or [min_stay_days]

    for anchor in departure_anchors:
        dep = parse_date(anchor)
        if start and dep < start:
            continue
        if end and dep > end:
            continue
        for stay in stays:
            if stay < min_stay_days:
                continue
            ret = dep + timedelta(days=stay)
            yield dep.isoformat(), ret.isoformat(), stay


def rotate_pairs(
    pairs: list[tuple[str, str, int]],
    run_index: int,
    batch_size: int,
) -> list[tuple[str, str, int]]:
    """Pick a rotating batch so each scheduled run covers different dates."""
    if not pairs:
        return []
    start = (run_index * batch_size) % len(pairs)
    batch: list[tuple[str, str, int]] = []
    for i in range(batch_size):
        batch.append(pairs[(start + i) % len(pairs)])
    return batch
