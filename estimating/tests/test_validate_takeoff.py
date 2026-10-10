"""Regression tests for estimating/scripts/validate_takeoff.py.

The golden fixture (655 115th Ave) must stay clean; each mutation below reproduces a
real failure mode from the takeoff accuracy protocol and must be caught.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "estimating" / "scripts" / "validate_takeoff.py"
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden-655-115th"


def run(proj, *args):
    p = subprocess.run([sys.executable, str(SCRIPT), str(proj), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


@pytest.fixture
def proj(tmp_path):
    dst = tmp_path / "proj"
    shutil.copytree(GOLDEN, dst)
    return dst


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_golden_fixture_passes_with_regression_compare():
    code, out = run(GOLDEN, "--golden", str(GOLDEN / "golden.csv"))
    assert code == 0, out
    assert "0 FAIL" in out
    assert "9/9 within tolerance" in out


def test_regression_drift_fails(proj):
    # the original 63% undercount: 5 of 13 grade-beam lines from the calc package
    edit(proj / "takeoff.md", "| Grade beam | 655 |", "| Grade beam | 237.67 |")
    code, out = run(proj, "--golden", str(proj / "golden.csv"))
    assert code == 1
    assert "[FAIL] golden" in out
    assert "[FAIL] csv-qty" in out  # takeoff no longer ties to the seed CSV


def test_misgraded_scale_fails(proj):
    # the 94.4% plot logged as confirmed
    edit(proj / "takeoff.md", "| 37'-9 3/8\" | 5.6 | red |", "| 37'-9 3/8\" | 5.6 | confirmed |")
    code, out = run(proj)
    assert code == 1
    assert "logged 'confirmed' but check dim" in out


def test_scaled_line_without_scale_entry_fails(proj):
    edit(proj / "takeoff.md", "| A2.0 | 1/4\" = 1'-0\" | title-block | 40'-0\" | 37'-9 3/8\" | 5.6 | red |\n", "")
    code, out = run(proj)
    assert code == 1
    assert "qty-scale-scaled" in out


def test_scaled_must_be_approx(proj):
    edit(proj / "takeoff.md", "| scaled | approx |", "| scaled | med-high |")
    code, out = run(proj)
    assert code == 1
    assert "qty-scaled-approx" in out


def test_area_without_gross_net_fails(proj):
    edit(proj / "takeoff.md", "| 2586.67 | SF | gross | A1.0 | measured | med-high | |\n| 06-002",
         "| 2586.67 | SF | | A1.0 | measured | med-high | |\n| 06-002")
    code, out = run(proj)
    assert code == 1
    assert "qty-gross-net" in out


def test_withheld_leaking_into_csv_fails(proj):
    with (proj / "lineitems.csv").open("a", encoding="utf-8") as f:
        f.write("08,,Porte-cochere door,,1,EA,,,,,,,W-01,A1.0,counted,assumed,\n")
    code, out = run(proj)
    assert code == 1
    assert "csv-withheld" in out


def test_unchecked_qa_box_needs_reason(proj):
    edit(proj / "takeoff.md", "☑ Ratio checks run; outliers explained",
         "□ Ratio checks run; outliers explained")
    code, out = run(proj)
    assert code == 1
    assert "unchecked with no stated reason" in out


def test_unchecked_qa_box_with_reason_warns(proj):
    edit(proj / "takeoff.md", "☑ Ratio checks run; outliers explained",
         "□ Ratio checks run — FAILED: duct weights not on set, RFI-09")
    code, out = run(proj)
    assert code == 0, out
    assert "unmet with a stated reason" in out
    code, _ = run(proj, "--strict")
    assert code == 1


def test_unread_plan_sheet_without_reason_fails(proj):
    edit(proj / "takeoff.md", "| S1 | Foundation plan | structural | 2 | read | |",
         "| S1 | Foundation plan | structural | 2 | not read | |")
    code, out = run(proj)
    assert code == 1
    assert "sheet-coverage" in out


def test_ratio_outlier_warns(proj):
    edit(proj / "takeoff.md", "| Rebar, grade beams + SOG | 14500 |", "| Rebar, grade beams + SOG | 45000 |")
    edit(proj / "lineitems.csv", ",14500,", ",45000,")
    code, out = run(proj)
    assert code == 0, out
    assert "[WARN] ratio: rebar lb/CY" in out


def test_legacy_takeoff_without_new_sections_fails(proj):
    text = (proj / "takeoff.md").read_text(encoding="utf-8")
    text = text.replace("## Sheet index", "## Index of drawings").replace("## Scale log", "## Scales")
    (proj / "takeoff.md").write_text(text, encoding="utf-8")
    code, out = run(proj)
    assert code == 1
    assert "missing required section" in out


@pytest.mark.parametrize("text,feet", [
    ("40'-0\"", 40.0), ("64'-8\"", 64 + 8 / 12), ("37'-9 3/8\"", 37 + 9.375 / 12),
    ("40 ft", 40.0), ("480\"", 40.0), ("12.5", 12.5), ("40′-0″", 40.0),
])
def test_parse_length(text, feet):
    sys.path.insert(0, str(SCRIPT.parent))
    import validate_takeoff
    assert validate_takeoff.parse_length_ft(text) == pytest.approx(feet)
