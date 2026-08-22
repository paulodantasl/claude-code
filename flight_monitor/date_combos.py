"""Generate departure/return date pairs for flexible trip windows."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterator


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_flexible_pairs(
    departure_start: str,
    latest_return: str,
    min_stay_days: int = 7,
    departure_step_days: int = 1,
    stay_lengths: list[int] | None = None,
) -> Iterator[tuple[str, str, int]]:
    """
    Yield all valid (departure, return, stay) combos where:
    - departure >= departure_start
    - return <= latest_return
    - stay >= min_stay_days
  Duration is flexible — every valid stay length is tried per departure.
    """
    start = parse_date(departure_start)
    end = parse_date(latest_return)
    stays = stay_lengths or _default_stay_lengths(start, end, min_stay_days)

    dep = start
    while dep <= end:
        latest_dep = end - timedelta(days=min_stay_days)
        if dep > latest_dep:
            break
        for stay in stays:
            if stay < min_stay_days:
                continue
            ret = dep + timedelta(days=stay)
            if ret > end:
                continue
            yield dep.isoformat(), ret.isoformat(), stay
        dep += timedelta(days=departure_step_days)


def coarse_pairs(
    departure_start: str,
    latest_return: str,
    min_stay_days: int = 7,
    departure_step_days: int = 4,
    stay_lengths: list[int] | None = None,
) -> list[tuple[str, str, int]]:
    """Sampled grid across the full window for initial exploration."""
    return list(
        iter_flexible_pairs(
            departure_start,
            latest_return,
            min_stay_days=min_stay_days,
            departure_step_days=departure_step_days,
            stay_lengths=stay_lengths,
        )
    )


def refine_pairs(
    center_departure: str,
    center_return: str,
    departure_start: str,
    latest_return: str,
    min_stay_days: int = 7,
    window_days: int = 3,
    stay_lengths: list[int] | None = None,
) -> list[tuple[str, str, int]]:
    """Search +/- window_days around a promising (departure, return) combo."""
    dep0 = parse_date(center_departure)
    ret0 = parse_date(center_return)
    start = parse_date(departure_start)
    end = parse_date(latest_return)
    stays = stay_lengths or _default_stay_lengths(start, end, min_stay_days)

    pairs: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for dep_offset in range(-window_days, window_days + 1):
        dep = dep0 + timedelta(days=dep_offset)
        if dep < start or dep > end - timedelta(days=min_stay_days):
            continue
        for ret_offset in range(-window_days, window_days + 1):
            ret = ret0 + timedelta(days=ret_offset)
            if ret <= dep or ret > end:
                continue
            stay = (ret - dep).days
            if stay < min_stay_days:
                continue
            key = (dep.isoformat(), ret.isoformat())
            if key in seen:
                continue
            seen.add(key)
            pairs.append((dep.isoformat(), ret.isoformat(), stay))
        for stay in stays:
            ret = dep + timedelta(days=stay)
            if ret > end:
                continue
            key = (dep.isoformat(), ret.isoformat())
            if key in seen:
                continue
            seen.add(key)
            pairs.append((dep.isoformat(), ret.isoformat(), stay))
    return pairs


def rotate_pairs(
    pairs: list[tuple[str, str, int]],
    run_index: int,
    batch_size: int,
) -> list[tuple[str, str, int]]:
    """Pick a rotating batch so each scheduled run covers different dates."""
    if not pairs:
        return []
    start = (run_index * batch_size) % len(pairs)
    return [pairs[(start + i) % len(pairs)] for i in range(min(batch_size, len(pairs)))]


def _default_stay_lengths(start: date, end: date, min_stay: int) -> list[int]:
    max_stay = (end - start).days
    candidates = [7, 10, 12, 14, 17, 21, 24, 28, 35, 42, 49, 56]
    return [s for s in candidates if min_stay <= s <= max_stay] or [min_stay]
