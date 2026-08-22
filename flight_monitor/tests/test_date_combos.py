"""Tests for flight monitor date logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from date_combos import iter_date_pairs, rotate_pairs


def test_departure_window():
    pairs = list(
        iter_date_pairs(
            ["2026-12-20", "2027-01-30", "2027-02-01"],
            min_stay_days=14,
            departure_start="2026-12-20",
            departure_end="2027-01-30",
        )
    )
    assert len(pairs) >= 2
    for dep, ret, stay in pairs:
        assert stay >= 14
        assert dep >= "2026-12-20"
        assert dep <= "2027-01-30"


def test_rotate_covers_all():
    pairs = [(f"2026-12-{20+i:02d}", f"2027-01-{3+i:02d}", 14) for i in range(6)]
    seen = set()
    for run in range(3):
        batch = rotate_pairs(pairs, run, batch_size=2)
        seen.update(batch)
    assert len(seen) == len(pairs)
