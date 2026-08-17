#!/usr/bin/env python3
"""Build corrected JobTread parameters for Job 2026-374 SunLife / Advantage Dental+.

Read-merge-write safety: loads current params, preserves live MEP geometry, replaces
broken ARCH finish/door params, adds TI gap quantities. Writes:
  - /tmp/sunlife_params_out.json  (full array for updateJob)
  - overlays/*.png                (verify-before-save)
  - takeoff quantities summary JSON
"""
from __future__ import annotations

import json
import math
import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/workspace/estimating/scripts")
from jobtread_takeoff import (  # noqa: E402
    FT_PER_M,
    SCALE_3_16_INCH,
    check_unique_ids,
    count_param,
    measurement,
    meta,
    parameter,
    path,
    point,
    rect_annotations,
    render_overlay,
    text_note,
)

PROJ = Path("/workspace/estimating/projects/sunlife-advantage-dental-wesley-chapel")
PT_PER_FT = 13.5  # 3/16" = 1'-0"
SCALE = SCALE_3_16_INCH

A0 = "22PcWyeHswAz"
A1 = "22PcWycUvzh8"
A2 = "22PcWyeHu4rs"
A6 = "22PcWyfwvkcA"
P1 = "22PcWyfwwtK4"
M1 = "22PcWyfwwtK5"
FP1 = "22PcZFNCS3ut"
E1 = "22PcZFND5gQL"
E2 = "22PcZFNDh9hW"


def uid(prefix: str = "t") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def shoelace_sf(corners: list[tuple[float, float]]) -> float:
    a = 0.0
    n = len(corners)
    for i in range(n):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0 / (PT_PER_FT**2)


def poly_area_param(
    name: str,
    plan_id: str,
    color: str,
    corners: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None = None,
    mname: str | None = None,
) -> dict:
    """Closed polygon area (+ optional hole polygons as isNegative)."""
    prefix = uid("poly")
    ids = [f"{prefix}{i}" for i in range(len(corners))]
    anns = [point(i, x, y) for i, (x, y) in zip(ids, corners)]
    anns.append(path(f"{prefix}p", ids, color, closed=True, fill=True, fill_opacity=0.12))
    area = shoelace_sf(corners)
    for hi, hole in enumerate(holes or []):
        hids = [f"{prefix}h{hi}_{i}" for i in range(len(hole))]
        anns += [point(i, x, y) for i, (x, y) in zip(hids, hole)]
        anns.append(
            path(f"{prefix}hn{hi}", hids, color, closed=True, negative=True, width=2)
        )
        area -= shoelace_sf(hole)
    return parameter(
        name,
        "area",
        [measurement(mname or name, area, plan_id, color, anns)],
        unit="foot",
        value=area,
    )


def number_param(name: str, value: float, unit: str = "foot") -> dict:
    """Advisory quantity with no geometry (printed / derived)."""
    return {
        "name": name,
        "measurementType": "number",
        "unit": unit,
        "value": round(value, 2),
        "measurements": [],
    }


def slim_ann(a: dict) -> dict:
    """Drop page:1 and optional fill styling to shrink payload."""
    out = {k: v for k, v in a.items() if not (k == "page" and v == 1)}
    if out.get("type") == "path":
        out.pop("fillColor", None)
        out.pop("fillOpacity", None)
    if out.get("type") == "point":
        # keep stroke if present (count markers need color)
        pass
    return out


def slim_param(p: dict) -> dict:
    p = json.loads(json.dumps(p))  # deep copy
    for m in p.get("measurements") or []:
        if "annotations" in m:
            m["annotations"] = [slim_ann(a) for a in m["annotations"]]
    return p


def keep_names_startswith(params: list[dict], prefixes: list[str]) -> list[dict]:
    out = []
    for p in params:
        if any(p["name"].startswith(pref) for pref in prefixes):
            out.append(p)
    return out


def main() -> None:
    existing = json.loads(Path("/tmp/sunlife_params_full.json").read_text())
    by_name = {p["name"]: p for p in existing}

    # --- Preserve live MEP / verified geometry ---
    preserve_exact = [
        "PLUMB W - Waste / sanitary (287.6 LF)",
        "PLUMB CW - Cold water (220.9 LF)",
        "PLUMB CA - Compressed air (76.3 LF)",
        "PLUMB VAC - Dental vacuum (131.0 LF)",
        "ARCH Partitions NEW (418.1 LF, 44 runs)",
        "ELEC Lighting fixtures - marked (121: A 27, B 2, C 4, D 63, DE 14, UC 3, X1 4, X2 4)",
        "HVAC Air terminals + exhaust fans - marked (46)",
        "PLUMB Fixtures + equipment - marked (21)",
        "ELEC Junction boxes (J) - marked (31)",
    ]
    kept = [by_name[n] for n in preserve_exact if n in by_name]

    # V: live geometry measures 196.3 LF (name previously claimed 238.1 — fix name)
    v_old = by_name.get("PLUMB V - Vent (238.1 LF)")
    if v_old:
        v_fix = json.loads(json.dumps(v_old))
        v_fix["name"] = (
            "PLUMB V - Vent (196.3 LF live) — was labeled 238.1; geometry recomputes 196.3. "
            "RFI: confirm vent vs HW swap / missing vent runs"
        )
        kept.append(v_fix)

    # HW: geometry was wiped — restore advisory from prior verified recompute + RFI
    kept.append(
        number_param(
            "PLUMB HW - Hot water 196.4 LF (ADVISORY — geometry missing, re-trace RFI) "
            "+ HWR not included",
            196.4,
            "foot",
        )
    )

    # HVAC duct / fire pipe — keep as advisory numbers (no live geometry)
    kept.append(
        number_param(
            "HVAC Duct CENTRELINE 297.5 LF (approx; was 595 outline/2) — per-size RFI; "
            "sheetmetal SF assumption",
            297.5,
            "foot",
        )
    )
    kept.append(
        number_param(
            "FIRE PROT pipe 336.7 LF drawn (NOT purchase qty) — reconfig existing wet system",
            336.7,
            "foot",
        )
    )

    # --- Suite area (printed A0 governs) ---
    kept.append(
        number_param(
            "AREA Suite 2,797 SF (printed A0 Project Area) — RFI vs permit 2,999 RSF",
            2797.0,
            "foot",
        )
    )

    # --- Floor finishes (schedule + printed area; LVT prior 614 was chair pads — WRONG) ---
    # Base bid: toilets remain LVT-1; ALT T-1 = 110.1 SF measured toilets
    CONC_SF = 222.0  # IT+Equip+Stor117+Stor119 derived; approx ±15%
    VCT_SF = 44.0  # Pano 8'-4" x 5'-4" from A1 dims
    TOILET_SF = 110.1  # measured T-1 polygons on A6 (keep geometry)
    LVT_SF = 2797.0 - CONC_SF - VCT_SF  # 2531; toilets included as LVT base bid

    # Keep measured toilet polygons as ALT T-1
    t1_old = by_name.get("ARCH Floor T-1 tile (SF)")
    if t1_old:
        t1 = json.loads(json.dumps(t1_old))
        t1["name"] = (
            "ARCH Floor T-1 ALT toilets (110.1 SF measured) — base bid is LVT-1 in 104/105; "
            "take ALT to convert"
        )
        kept.append(t1)

    # CONC room rects on A6 (geometry-anchored; sum targeted ~222)
    conc_rects = [
        # IT 107 ~30 SF
        (448, 945, 448 + 5.0 * PT_PER_FT, 945 + 6.0 * PT_PER_FT),
        # Equip 108 9.25 x 14.04 ~130 SF
        (448, 745, 448 + 9.25 * PT_PER_FT, 745 + 14.04 * PT_PER_FT),
        # Storage 117 ~59 SF
        (655, 235, 655 + 8.0 * PT_PER_FT, 235 + 7.4 * PT_PER_FT),
        # Storage 119 ~14 SF
        (880, 245, 880 + 4.0 * PT_PER_FT, 245 + 3.5 * PT_PER_FT),
    ]
    conc_anns: list[dict] = []
    conc_total = 0.0
    for i, (x0, y0, x1, y1) in enumerate(conc_rects):
        pref = f"conc{i}_"
        conc_anns += rect_annotations(pref, x0, y0, x1, y1, "#78716c", fill_opacity=0.25)
        conc_total += abs(x1 - x0) / PT_PER_FT * abs(y1 - y0) / PT_PER_FT
    kept.append(
        parameter(
            f"ARCH Floor CONC sealed (SF) — IT/Equip/Stor117/119 ≈{conc_total:.0f} SF",
            "area",
            [
                measurement(
                    f"4 CONC rooms ≈{conc_total:.1f} SF",
                    conc_total,
                    A6,
                    "#78716c",
                    conc_anns,
                )
            ],
            unit="foot",
            value=conc_total,
        )
    )

    # VCT Pano
    px0, py0 = 735, 615
    pano = (px0, py0, px0 + 8.333 * PT_PER_FT, py0 + 5.333 * PT_PER_FT)
    pano_sf = 8.333 * 5.333
    kept.append(
        parameter(
            "ARCH Floor VCT-1 Pano 110 (SF)",
            "area",
            [
                measurement(
                    "Pano 8'-4\" x 5'-4\"",
                    pano_sf,
                    A6,
                    "#a855f7",
                    rect_annotations("vct1_", *pano, "#a855f7", fill_opacity=0.25),
                )
            ],
            unit="foot",
            value=pano_sf,
        )
    )

    # LVT net = suite − CONC − VCT (number; geometry of full suite pending exact outline)
    kept.append(
        number_param(
            f"ARCH Floor LVT-1 {LVT_SF:.0f} SF (suite 2797 − CONC {CONC_SF:.0f} − VCT {VCT_SF:.0f}) "
            "— REPLACES prior 614 SF chair-pad error; toilets as LVT base bid",
            LVT_SF,
            "foot",
        )
    )

    # --- Ceilings ---
    # GYP: IT + Equip rooms (~160) + soffits ~90 → use 250; ACT = 2797-250
    GYP_SF = 250.0
    ACT_SF = 2797.0 - GYP_SF
    kept.append(
        number_param(
            f"ARCH Ceiling ACT-1 {ACT_SF:.0f} SF (suite − GYP zones) — Armstrong Calla 2x2",
            ACT_SF,
            "foot",
        )
    )
    kept.append(
        number_param(
            f"ARCH Ceiling GYP {GYP_SF:.0f} SF (IT/Equip + soffits approx) — verify RCP",
            GYP_SF,
            "foot",
        )
    )

    # --- Doors (A5 schedule governs: 10 NEW + 3 EX = 13) ---
    door_new = {
        "102": (640, 1165),
        "103": (720, 1110),
        "104": (470, 1160),
        "105": (545, 1160),
        "107": (470, 980),
        "108": (530, 880),
        "117": (720, 290),
        "119": (910, 290),
        "125A": (980, 1160),
        "100B": (600, 1240),
    }
    door_ex = {
        "100A": (550, 1310),
        "118": (840, 260),
        "125B": (1040, 1280),
    }
    kept.append(
        count_param(
            "ARCH Doors NEW (10 EA) — A5: 9×Type1 + 1×Type2 100B; frames Type A",
            A1,
            "#c2185b",
            list(door_new.values()),
            mname="A5 new doors",
            prefix="dn_",
        )
    )
    kept.append(
        count_param(
            "ARCH Doors EXISTING remain (3 EA) — A5 EX: 100A pair, 118, 125B pair",
            A1,
            "#5d4037",
            list(door_ex.values()),
            mname="A5 existing doors",
            prefix="dx_",
        )
    )

    # --- Partitions type split (from prior fill analysis; total 418.1 live) ---
    kept.append(number_param("ARCH Partitions Type1 to 6\" AFCE ≈365 LF (of 418.1)", 365.0))
    kept.append(number_param("ARCH Partitions Type2 to deck ≈14 LF (of 418.1)", 14.0))
    kept.append(number_param("ARCH Partitions Type3 furred ≈39 LF (of 418.1)", 39.0))

    # --- Base B-1: ~2× interior partition + perimeter demising estimate ---
    # Partitions 418 both sides ≈ 836; demising perimeter ~2×(45+62)=214; shared walls adjust
    # Prior 820 LF — keep as approx with note
    kept.append(
        number_param(
            "ARCH Base B-1 ≈820 LF (approx; 4\" Flexco cove) — verify room perimeters",
            820.0,
        )
    )

    # --- Casework: GC vs Henry Schein ---
    kept.append(
        number_param(
            "ARCH Casework GC CF/CI ≈76 LF (reception/lab/break/toilet vanities) — A2 hatch",
            76.0,
        )
    )
    kept.append(
        number_param(
            "ARCH Casework HS OFCI ≈55 LF (sterile island + 7 ops wall cabs) — A2 blue; "
            "GC installs utilities only",
            55.0,
        )
    )

    # --- Dental ops / equipment counts ---
    kept.append(
        count_param(
            "DENTAL Ops chairs (7 EA) — Hyg 111/113/116 + Exam 120/121/123/124",
            A2,
            "#0d9488",
            [
                (500, 700),
                (500, 820),
                (500, 940),  # hygiene approx
                (1000, 700),
                (1000, 820),
                (1000, 940),
                (1000, 1060),  # exam approx
            ],
            mname="7 dental chairs HS OFCI",
            prefix="op_",
        )
    )
    kept.append(
        number_param(
            "DENTAL Pano unit (1 EA) + lead lining RFI if required by HS/physicist",
            1.0,
            "each",
        )
    )

    # --- Fire sprinkler heads ---
    # ~39 unique small-circle candidates on FP1; use 34 ±4 with Piper lump-sum quote
    kept.append(
        number_param(
            "FIRE PROT sprinkler heads ≈34 EA (±4) — NFPA13 reconfig; Piper quote 250307 "
            "lump $19,353; count from FP1 symbols",
            34.0,
            "each",
        )
    )

    # --- FEC ---
    kept.append(
        number_param("FIRE FEC cabinets (2 EA) shown on A0/A1 corridors", 2.0, "each")
    )

    # --- Demo / TI allowances (quantity flags) ---
    kept.append(
        number_param(
            "DEMO MEP6 existing TI demo (LS) — count devices from MEP6; slab saw-cut "
            "for dental utilities per A2 note",
            1.0,
            "allow",
        )
    )
    kept.append(
        number_param(
            "FIRESTOP new penetrations in existing 1-HR U419 N/E demising (LS)",
            1.0,
            "allow",
        )
    )

    # --- Code / register ---
    kept.append(
        {
            "name": "REGISTER Code A0 — B / II-B / sprinklered / 46 occ / FBC 2023 8th / "
            "Pasco COMALT-2026-000467 / service 480Y/277V",
            "measurementType": "count",
            "value": 1,
            "measurements": [
                {
                    "name": "Occupancy B || Constr II-B || EXISTING SPRINKLERED water "
                    "monitored || 46 occupants || Project Area 2,797 SF (2355 biz + "
                    "282 waiting + 160 break) || EXISTING 1-HR U419 N+E || Level 2 "
                    "alteration (work area ~35% of 7,904 SF bldg). Permit cites 2,999 "
                    "RSF — RFI. Shell: existing multi-tenant retail; no site/civil shell "
                    "work in GC scope.",
                    "value": 1,
                    "color": "#cf1620",
                    "annotations": [],
                }
            ],
        }
    )
    kept.append(
        {
            "name": "REGISTER 2026-08-17 takeoff completion — fixed LVT chair-pad error "
            "(614→2531); doors 15→13 per A5; HW geometry missing→advisory; V live 196.3",
            "measurementType": "count",
            "value": 1,
            "measurements": [
                {
                    "name": "Preserved live: PLUMB W/CW/CA/VAC, Partitions 418.1, Lighting "
                    "121, HVAC 46, Fixtures 21, J-boxes 31, T-1 toilets 110.1. Replaced: "
                    "LVT (was chair pads), doors, ceilings, finishes. Added: CONC, VCT, "
                    "ops×7, heads≈34, partition type split, HS vs GC casework, FEC, "
                    "firestop/demo flags. Open RFIs in takeoff.md.",
                    "value": 1,
                    "color": "#cf1620",
                    "annotations": [],
                }
            ],
        }
    )

    # Unique ids on freshly authored geometry only
    fresh_prefixes = (
        "ARCH Doors NEW",
        "ARCH Doors EXISTING",
        "ARCH Floor CONC",
        "ARCH Floor VCT",
        "DENTAL Ops",
    )
    new_only = [p for p in kept if p["name"].startswith(fresh_prefixes)]
    check_unique_ids(new_only)

    # Slim for API
    out = [slim_param(p) for p in kept]
    Path("/tmp/sunlife_params_out.json").write_text(json.dumps(out))
    Path("/tmp/sunlife_params_names.json").write_text(
        json.dumps(
            [{"name": p["name"], "type": p.get("measurementType"), "value": p.get("value")} for p in out],
            indent=2,
        )
    )
    print(f"Wrote {len(out)} parameters")
    for p in out:
        print(f"  [{p.get('measurementType','?'):8}] {str(p.get('value')):>10}  {p['name'][:90]}")

    # Overlays
    overlays = PROJ / "overlays"
    overlays.mkdir(exist_ok=True)
    pdf_a1 = str(PROJ / "plans/A1_Dimension_RCP.pdf")
    pdf_a6 = str(PROJ / "plans/A6_Finish_Plan.pdf")

    render_overlay(
        pdf_a1,
        0,
        str(overlays / "A1_doors_markers.png"),
        dots=[(x, y, "#c2185b") for x, y in door_new.values()]
        + [(x, y, "#5d4037") for x, y in door_ex.values()],
        clip=(300, 180, 1150, 1380),
        dpi=120,
    )
    render_overlay(
        pdf_a6,
        0,
        str(overlays / "A6_CONC_VCT_rects.png"),
        rects=[(*r, "#78716c") for r in conc_rects] + [(*pano, "#a855f7")],
        clip=(300, 180, 1150, 1380),
        dpi=120,
    )
    print("Overlays written")


if __name__ == "__main__":
    main()
