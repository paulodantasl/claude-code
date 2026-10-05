"""Shared fixtures. Every number here is synthetic: fake- agencies, example.invalid URLs."""

import csv
import math
import random
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from bid_tracker import db  # noqa: E402
from bid_tracker.canonical import SPECS, make_sol_ref  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_VALID = FIXTURES / "fake_valid"


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    # Never let a test touch a real data dir.
    monkeypatch.setenv("BID_TRACKER_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("BID_TRACKER_DB", raising=False)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "scratch.db")
    db.init_db(c)
    yield c
    c.close()


@pytest.fixture
def pkg_copy(tmp_path):
    dest = tmp_path / "pkg"
    shutil.copytree(FAKE_VALID, dest)
    return dest


def edit_csv(path: Path, fn) -> None:
    """Rewrite a CSV; fn(rows) mutates the list of dicts in place."""
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames
        rows = list(reader)
    fn(rows)
    for r in rows:
        cols += [k for k in r if k not in cols]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(rows)


def synth_package(dest: Path, n_jobs: int = 30, seed: int = 7, sigma: float = 0.12,
                  project_type: str = "V-REN", agency_type: str = "county") -> Path:
    """Many low-bid tabs with lognormal bids around the EE, for analytics tests."""
    rng = random.Random(seed)
    dest.mkdir(parents=True, exist_ok=True)
    agencies = [{"agency_id": "fake-synth", "name": "FAKE Synth Agency", "agency_type": agency_type,
                 "county": "Hillsborough", "watch": "0"}]
    sols, bids = [], []
    for j in range(n_jobs):
        no = f"ITB-{j:03d}"
        ref = make_sol_ref("fake-synth", no)
        ee = 200_000 + 50_000 * (j % 7)
        n = 3 + (j % 5)
        totals = sorted(round(ee * math.exp(rng.gauss(0.0, sigma)), 2) for _ in range(n))
        low = totals[0]
        sols.append({
            "sol_ref": ref, "agency_id": "fake-synth", "solicitation_no": no, "title": f"FAKE job {j}",
            "procurement_method": "ITB", "award_basis": "low_bid", "work_class": "vertical",
            "project_type": project_type, "county": "Hillsborough", "gsf": str(2000 + 400 * (j % 6)),
            "gsf_basis": "stated", "bid_open_date": f"2025-{1 + j % 12:02d}-15", "engineers_estimate": f"{ee:.2f}",
            "ee_source": "ee", "award_status": "opened",
            "source_url": f"https://example.invalid/synth/{no}.pdf",
            "source_excerpt": f"Tabulation {no}: apparent low {low:,.2f}; estimate {ee:,.2f}",
            "evidence_class": "official_tab", "retrieved_at": "2026-01-15", "extracted_by": "test",
        })
        for i, t in enumerate(totals):
            bids.append({"sol_ref": ref, "bidder_name_raw": f"FAKE Bidder {chr(65 + (i + j) % 12)} LLC",
                         "total_bid": f"{t:.2f}", "base_bid": f"{t:.2f}", "total_basis": "base",
                         "responsive": "1", "page_ref": "p1",
                         "source_url": f"https://example.invalid/synth/{no}.pdf"})
    for name, rows in (("agencies.csv", agencies), ("solicitations.csv", sols), ("bids.csv", bids)):
        cols = list(SPECS[name])
        with open(dest / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
    return dest
