#!/usr/bin/env python3
"""JobTread on-screen-takeoff helpers — compose parameters/annotations for the Pave API.

Companion to estimating/reference/jobtread-takeoff-protocol.md (read that first).
Verified conventions (empirical, 2026-07-04): annotation coords = native PDF points;
plan.scale = PDF points per METER; JobTread recomputes values from geometry x scale;
updateJob.parameters / updatePlan.annotations are FULL-REPLACE (read-merge-write!).

Use as a library from an agent session:

    from jobtread_takeoff import *
    p = area_param("GF Footprint Area", PLAN_ID, "#cf1620",
                   rect=(201.6, 222.6, 921.6, 1386.6), scale=SCALE_QUARTER_INCH)
    params = merge_parameters(existing_params, [p])   # full-replace safety
    check_unique_ids(params)                          # raises on collision
    # -> send {"updateJob": {"$": {"id": JOB, "parameters": params}, ...}} via the MCP tool
    # -> then READ BACK job.parameters and diff names/values

Also includes: scale table, pt<->ft/m conversions, dimension-chain closure check,
and an overlay renderer (PyMuPDF) for the mandatory verify-before-save step.

CLI self-test:  python3 jobtread_takeoff.py --selftest
"""

from __future__ import annotations

import json
import math

# ---------------------------------------------------------------------------
# Scale constants: plan.scale = PDF points per METER.
# scale = inches_per_foot(drawing scale) * 3.28084 * 72
FT_PER_M = 3.280839895013123
PT_PER_IN = 72.0

def scale_for(inches_per_foot: float) -> float:
    """plan.scale for an imperial drawing scale, e.g. 0.25 for 1/4"=1'-0"."""
    return inches_per_foot * FT_PER_M * PT_PER_IN

SCALE_EIGHTH_INCH   = scale_for(0.125)    # 29.5275590551
SCALE_3_16_INCH     = scale_for(0.1875)   # 44.2913385827
SCALE_QUARTER_INCH  = scale_for(0.25)     # 59.0551181102
SCALE_3_8_INCH      = scale_for(0.375)    # 88.5826771654
SCALE_HALF_INCH     = scale_for(0.5)      # 118.1102362205
SCALE_ONE_INCH      = scale_for(1.0)      # 236.2204724409

def pt_per_ft(inches_per_foot: float) -> float:
    """Drawing points per real foot (e.g. 18.0 at 1/4 inch scale)."""
    return inches_per_foot * PT_PER_IN

def pts_to_feet(dist_pt: float, inches_per_foot: float = 0.25) -> float:
    return dist_pt / pt_per_ft(inches_per_foot)

def feet_to_pts(feet: float, inches_per_foot: float = 0.25) -> float:
    return feet * pt_per_ft(inches_per_foot)


# ---------------------------------------------------------------------------
# Annotation builders (schema-verified shapes)

def meta(width: float, height: float, rotation: int = 0, page: int = 1) -> dict:
    """Page-space declaration; width/height = PDF page size in points."""
    return {"type": "meta", "page": page, "width": width, "height": height,
            "rotation": rotation}


def point(pid: str, x: float, y: float, color: str | None = None,
          page: int = 1, stroke_width: int = 3) -> dict:
    d = {"type": "point", "page": page, "id": pid, "x": round(x, 2), "y": round(y, 2)}
    if color:
        d.update({"fillColor": color, "strokeColor": color, "strokeWidth": stroke_width})
    return d


def path(pid: str, point_ids: list[str], color: str, *, closed: bool = False,
         negative: bool = False, width: int = 3, fill: bool = False,
         fill_opacity: float = 0.15, page: int = 1) -> dict:
    d = {"type": "path", "page": page, "id": pid,
         "points": [{"annotationId": p} for p in point_ids],
         "strokeWidth": width, "strokeColor": color}
    if closed:
        d["isClosed"] = True
    if negative:
        d["isNegative"] = True
    if fill and not negative:
        d["fillColor"] = color
        d["fillOpacity"] = fill_opacity
    return d


def text_note(pid: str, txt: str, x: float, y: float, color: str = "#cf1620",
              font_size: int = 24, page: int = 1) -> dict:
    """Text annotation — the API requires ALL of these fields non-null."""
    return {"type": "text", "page": page, "id": pid, "text": txt,
            "fontSize": font_size, "fontColor": color, "fontWeight": "bold",
            "fontStyle": "normal", "fillColor": "#ffffff", "fillOpacity": 0,
            "x": x, "y": y, "rotation": 0}


def rect_annotations(prefix: str, x0: float, y0: float, x1: float, y1: float,
                     color: str, *, negative: bool = False, width: int = 3,
                     fill_opacity: float = 0.15) -> list[dict]:
    """4 corner points + closed path. Use negative=True for subtraction holes."""
    ids = [f"{prefix}{k}" for k in (1, 2, 3, 4)]
    return [point(ids[0], x0, y0), point(ids[1], x1, y0),
            point(ids[2], x1, y1), point(ids[3], x0, y1),
            path(f"{prefix}p", ids, color, closed=True, negative=negative,
                 width=width, fill=not negative, fill_opacity=fill_opacity)]


def loop_annotations(prefix: str, corners: list[tuple[float, float]],
                     color: str, width: int = 4) -> list[dict]:
    """OPEN path visiting corners and returning to start (perimeter as linear).
    JobTread measures open-path length; repeat the first coordinate as a new point."""
    pts = corners + [corners[0]]
    ids = [f"{prefix}{k}" for k in range(1, len(pts) + 1)]
    anns = [point(i, x, y) for i, (x, y) in zip(ids, pts)]
    anns.append(path(f"{prefix}p", ids, color, width=width))
    return anns


def line_annotations(prefix: str, x0: float, y0: float, x1: float, y1: float,
                     color: str, width: int = 4) -> list[dict]:
    return [point(f"{prefix}1", x0, y0), point(f"{prefix}2", x1, y1),
            path(f"{prefix}p", [f"{prefix}1", f"{prefix}2"], color, width=width)]


# ---------------------------------------------------------------------------
# Parameter builders

def measurement(name: str, value: float, plan_id: str, color: str,
                annotations: list[dict], **extra) -> dict:
    m = {"name": name, "value": round(value, 2), "planId": plan_id,
         "color": color, "annotations": annotations}
    m.update(extra)  # e.g. depth=13, unit="foot" for linearArea
    return m


def parameter(name: str, mtype: str, measurements: list[dict],
              unit: str | None = "foot", value: float | None = None) -> dict:
    p = {"name": name, "measurementType": mtype, "measurements": measurements}
    if mtype != "count" and unit:
        p["unit"] = unit
    p["value"] = round(value if value is not None
                       else sum(m.get("value", 0) for m in measurements), 2)
    return p


def area_param(name: str, plan_id: str, color: str, *, rect: tuple | None = None,
               scale: float = SCALE_QUARTER_INCH, prefix: str | None = None,
               negatives: list[tuple] | None = None, mname: str | None = None) -> dict:
    """Rectangle area parameter (+ optional isNegative holes). Value auto-computed
    from geometry x scale so it matches what JobTread will recompute."""
    prefix = prefix or _slug(name)
    x0, y0, x1, y1 = rect
    ppm = scale  # pt per meter
    to_ft = lambda pt: pt / ppm * FT_PER_M
    area = to_ft(x1 - x0) * to_ft(y1 - y0)
    anns = rect_annotations(prefix, *rect, color)
    for i, hole in enumerate(negatives or []):
        hx0, hy0, hx1, hy1 = hole
        area -= to_ft(hx1 - hx0) * to_ft(hy1 - hy0)
        anns += rect_annotations(f"{prefix}n{i+1}", *hole, color, negative=True, width=2)
    return parameter(name, "area",
                     [measurement(mname or name, area, plan_id, color, anns)])


def count_param(name: str, plan_id: str, color: str,
                points_xy: list[tuple[float, float]], mname: str | None = None,
                prefix: str | None = None) -> dict:
    prefix = prefix or _slug(name)
    anns = [point(f"{prefix}{k+1}", x, y, color) for k, (x, y) in enumerate(points_xy)]
    return parameter(name, "count",
                     [measurement(mname or name, len(points_xy), plan_id, color, anns)],
                     unit=None)


def _slug(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())[:10] + "_"


# ---------------------------------------------------------------------------
# Safety rails

def check_unique_ids(params: list[dict]) -> int:
    """Raise if any annotation id repeats across the WHOLE parameters array."""
    ids = [a["id"] for p in params for m in p.get("measurements", [])
           for a in m.get("annotations", []) if "id" in a]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate annotation ids: {sorted(dupes)}")
    return len(ids)


def merge_parameters(existing: list[dict], new: list[dict]) -> list[dict]:
    """FULL-REPLACE safety: keep existing (replacing same-name), append new.
    ALWAYS read job.parameters first and pass it here — never send only the new ones."""
    by_name = {p["name"]: p for p in (existing or [])}
    for p in new:
        by_name[p["name"]] = p
    return list(by_name.values())


def closure_check(dims_ft: list[float], total_ft: float, tol_ft: float = 0.05) -> bool:
    """Dimension-chain closure (takeoff-accuracy-protocol §3)."""
    return abs(sum(dims_ft) - total_ft) <= tol_ft


# ---------------------------------------------------------------------------
# Overlay verification (mandatory before saving) — requires pymupdf

def render_overlay(pdf_path: str, page_index: int, out_png: str,
                   rects=None, neg_rects=None, lines=None, polylines=None,
                   dots=None, clip=None, dpi: int = 90):
    """Draw proposed geometry on the sheet and save a PNG to READ before saving.
    rects/neg_rects: [(x0,y0,x1,y1,'#hex')], lines: [(x0,y0,x1,y1,'#hex')],
    polylines: [([(x,y),...], '#hex')], dots: [(x,y,'#hex')]."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("overlay-verify requires PyMuPDF — fix: pip install pymupdf")
    hx = lambda h: tuple(int(h.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4))
    doc = fitz.open(pdf_path)
    pg = doc[page_index]
    sh = pg.new_shape()
    for x0, y0, x1, y1, c in (rects or []):
        sh.draw_rect(fitz.Rect(x0, y0, x1, y1))
        sh.finish(color=hx(c), fill=hx(c), fill_opacity=0.15, width=3)
    for x0, y0, x1, y1, c in (neg_rects or []):
        sh.draw_rect(fitz.Rect(x0, y0, x1, y1)); sh.finish(color=hx(c), width=2)
    for x0, y0, x1, y1, c in (lines or []):
        sh.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1)); sh.finish(color=hx(c), width=5)
    for pts, c in (polylines or []):
        sh.draw_polyline([fitz.Point(x, y) for x, y in pts]); sh.finish(color=hx(c), width=5)
    for x, y, c in (dots or []):
        sh.draw_circle(fitz.Point(x, y), 8); sh.finish(color=hx(c), fill=hx(c))
    sh.commit()
    kw = {"dpi": dpi}
    if clip:
        kw["clip"] = fitz.Rect(*clip)
    pg.get_pixmap(**kw).save(out_png)
    return out_png


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        assert abs(SCALE_QUARTER_INCH - 59.05511811023622) < 1e-9
        assert abs(SCALE_HALF_INCH - 118.11023622047244) < 1e-9
        assert abs(feet_to_pts(40.0) - 720.0) < 1e-9
        assert closure_check([10 + 8/12, 30 + 2/12, 18 + 10/12, 1 + 7/12, 3 + 5/12], 64 + 8/12)
        p = area_param("GF Footprint Area", "PLAN", "#cf1620",
                       rect=(201.6, 222.6, 921.6, 1386.6))
        assert abs(p["value"] - 2586.67) < 0.05, p["value"]
        n = area_param("Net", "PLAN", "#1b5e20", rect=(213.6, 234.6, 909.6, 1374.6),
                       negatives=[(213.6, 234.6, 909.6, 402.6), (702.6, 765.7, 897.6, 1005.6)])
        assert abs(n["value"] - 1943.62) < 0.05, n["value"]
        merged = merge_parameters([{"name": "A", "measurements": []}], [p, n])
        assert [q["name"] for q in merged] == ["A", "GF Footprint Area", "Net"]
        check_unique_ids([p, n])
        print("selftest OK — scale table, closure, area math (incl. isNegative), merge, ids")
    else:
        print(__doc__)
