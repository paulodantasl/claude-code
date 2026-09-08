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


def freedraw_path(pid: str, pts, color: str, *, closed: bool = False,
                  negative: bool = False, width: int = 3, fill: bool = False,
                  fill_opacity: float = 0.15, page: int = 1) -> dict:
    """Path whose points are a FLAT [x1,y1,x2,y2,...] array — the 'freedraw' form.

    *** DO NOT USE THIS FOR TAKEOFF GEOMETRY. ***

    JobTread does NOT measure a freedraw path: the server recomputes the owning
    parameter's value as 0. It is freehand markup, which is what the schema calls
    it. Verified on job 2026-404 with a matched control pair (identical 4-point
    closed square, one freedraw / one ref): freedraw 0, ref 640.044. Thirty live
    parameters were silently zeroed before this was caught — the round-trip is
    byte-perfect and an offline recompute agrees, so nothing warns you.

    Use path() with {annotationId} refs for anything that must carry a quantity.
    To shrink a payload, strip server-generated fields instead (see strip_server_
    fields()). Kept here only so the encoding can be produced for genuine markup
    and so --selftest can assert the round-trip.
    """
    flat = []
    for p in pts:
        if isinstance(p, (list, tuple)):
            flat += [round(float(p[0]), 1), round(float(p[1]), 1)]
        else:
            flat.append(round(float(p), 1))
    if not 2 <= len(flat) <= 2000 or len(flat) % 2:
        raise ValueError(f"freedraw needs an even 2..2000 numbers, got {len(flat)}")
    d = {"type": "path", "page": page, "id": pid, "points": flat,
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

DIMENSIONED_TYPES = {"linearArea", "areaVolume", "linearVolume"}


def measurement(name: str, value: float, plan_id: str, color: str,
                annotations: list[dict], **extra) -> dict:
    """One measurement inside a parameter.

    Dimensioned types (linearArea/areaVolume/linearVolume) need their dimension(s)
    AND their own non-null `unit` ON THE MEASUREMENT -- the parameter-level `unit`
    is not enough. Verified 2026-09-05 on Job 2026-404, which failed with:
        A non-null value is required at ..."parameters"."5"."measurements"."0"."unit"
    So pass e.g. measurement(..., unit="foot", depth=10).
    """
    m = {"name": name, "value": round(value, 2), "planId": plan_id,
         "color": color, "annotations": annotations}
    m.update(extra)
    if ("depth" in m or "width" in m) and "unit" not in m:
        raise ValueError("dimensioned measurement needs its own unit= (e.g. 'foot') "
                         "alongside depth/width -- the server rejects it otherwise")
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


def check_payload(params: list[dict]) -> dict:
    """The three pre-send asserts. Run this on the assembled array, every time.

    Independent builder scripts each restarting their id counter is how 49
    duplicated ids once reached a payload; path->point refs would then have
    resolved to the wrong vertices with no server error, just wrong quantities.
    """
    n_ids = check_unique_ids(params)
    names = [p["name"] for p in params]
    dupe_names = sorted({n for n in names if names.count(n) > 1})
    if dupe_names:
        raise ValueError(f"duplicate parameter names: {dupe_names}")
    unresolved = []
    for p in params:
        for m in p.get("measurements", []):
            anns = m.get("annotations", [])
            pids = {a["id"] for a in anns if a.get("type") == "point"}
            for a in anns:
                pts = a.get("points")
                if pts and isinstance(pts[0], dict):
                    unresolved += [r["annotationId"] for r in pts
                                   if r["annotationId"] not in pids]
    if unresolved:
        raise ValueError(f"unresolved path refs: {sorted(set(unresolved))}")
    return {"parameters": len(params), "annotations": n_ids}


def check_no_freedraw(params: list[dict]) -> int:
    """Assert no path carries a flat-array (freedraw) point list.

    JobTread does not measure freedraw paths -- the server recomputes the owning
    parameter to 0 -- so a freedraw path in a takeoff payload is a silent zero.
    Run this alongside check_payload() before every send.
    """
    bad = []
    for p in params:
        for m in p.get("measurements", []):
            for a in m.get("annotations", []):
                pts = a.get("points")
                if pts and not isinstance(pts[0], dict):
                    bad.append(p["name"])
    if bad:
        raise ValueError(f"freedraw paths (these would measure 0): {sorted(set(bad))}")
    return sum(len(m.get("annotations", []))
               for p in params for m in p.get("measurements", []))


def strip_server_fields(params: list[dict]) -> list[dict]:
    """Remove everything the SERVER generates -- the only lossless compaction.

    Read-back adds `value` to parameters and measurements, `page: 1` to every
    annotation, and `fillColor` to every `point`. None of it needs to be sent
    back. Worth ~25 KB on a 120 KB payload, and safe in a way that re-encoding
    geometry is not. `strokeColor`/`strokeWidth` are REQUIRED on paths, so they
    are kept there; on points they are optional and dropped.
    """
    import copy
    out = copy.deepcopy(params)
    for p in out:
        if p.get("measurements"):
            p.pop("value", None)          # measured params: the server computes it
        for m in p.get("measurements", []):
            m.pop("value", None)
            for a in m.get("annotations", []):
                if a.get("page") == 1:
                    a.pop("page", None)
                if a.get("type") == "point":
                    for k in ("fillColor", "strokeColor", "strokeWidth"):
                        a.pop(k, None)
    return out


_BASE = {"area": "area", "linear": "linear", "count": "count",
         "linearArea": "linear", "areaVolume": "area", "linearVolume": "linear",
         "areaPitch": "area", "linearPitch": "linear"}


def recompute_value(param: dict, scales: dict) -> float | None:
    """Recompute a parameter's value from its geometry x each plan's stored scale.

    `scales` maps planId -> plan.scale (PDF points per METRE). Use this to verify a
    write immediately: the server recomputes `value` asynchronously, so a read-back
    seconds after a write carries values only for plain-`number` parameters.
    Returns None if a needed scale is missing.
    """
    mtype = param.get("measurementType")
    if not mtype:
        return param.get("value")
    base = _BASE[mtype]
    total = 0.0
    for m in param.get("measurements", []):
        anns = m.get("annotations", [])
        by_id = {a["id"]: a for a in anns if a.get("type") == "point"}
        if base == "count":
            total += sum(1 for a in anns if a.get("type") == "point")
            continue
        sc = scales.get(m.get("planId"))
        if sc is None:
            return None
        ppf = sc / FT_PER_M
        mult = 1.0
        if mtype in ("linearArea", "areaVolume"):
            mult = m["depth"]
        elif mtype == "linearVolume":
            mult = m["depth"] * m["width"]
        elif mtype in ("areaPitch", "linearPitch"):
            # pitchX = RUN, pitchY = RISE; the server returns plan x the slope factor
            mult = math.sqrt(1.0 + (m["pitchY"] / m["pitchX"]) ** 2)
        for a in anns:
            if a.get("type") != "path":
                continue
            pts = a.get("points") or []
            if pts and isinstance(pts[0], dict):
                if any(r["annotationId"] not in by_id for r in pts):
                    return None
                v = [(by_id[r["annotationId"]]["x"], by_id[r["annotationId"]]["y"])
                     for r in pts]
            else:
                v = [(pts[i], pts[i + 1]) for i in range(0, len(pts), 2)]
            if base == "area":
                if not a.get("isClosed"):
                    continue
                sh = abs(sum(v[i][0] * v[(i + 1) % len(v)][1]
                             - v[(i + 1) % len(v)][0] * v[i][1]
                             for i in range(len(v)))) / 2.0
                q = sh / (ppf * ppf) * mult
                total += -q if a.get("isNegative") else q
            else:
                L = sum(math.dist(v[i], v[i + 1]) for i in range(len(v) - 1))
                if a.get("isClosed"):
                    L += math.dist(v[-1], v[0])
                total += L / ppf * mult
    return total


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
    import fitz  # PyMuPDF
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
        try:
            measurement("bad", 1, "P", "#000", [], depth=10)      # missing unit
            raise AssertionError("dimensioned measurement without unit must raise")
        except ValueError:
            pass
        ok = measurement("good", 1, "P", "#000", [], unit="foot", depth=10)
        assert ok["unit"] == "foot" and ok["depth"] == 10
        merged = merge_parameters([{"name": "A", "measurements": []}], [p, n])
        assert [q["name"] for q in merged] == ["A", "GF Footprint Area", "Net"]

        # freedraw: flat point array, same length as the vertex-ref form
        fd = freedraw_path("fd1", [(0, 0), (720, 0), (720, 360)], "#cf1620", width=4)
        assert fd["points"] == [0.0, 0.0, 720.0, 0.0, 720.0, 360.0]
        try:
            freedraw_path("bad", [(0, 0)], "#000")                # only 2 numbers is legal
        except ValueError:
            raise AssertionError("2 numbers must be accepted")
        lin_fd = {"name": "FD", "measurementType": "linear", "unit": "foot",
                  "measurements": [{"name": "", "color": "#cf1620", "planId": "P",
                                    "annotations": [fd]}]}
        lin_ref = {"name": "REF", "measurementType": "linear", "unit": "foot",
                   "measurements": [{"name": "", "color": "#cf1620", "planId": "P",
                                     "annotations": [
                                         point("r1", 0, 0), point("r2", 720, 0),
                                         point("r3", 720, 360),
                                         path("rp", ["r1", "r2", "r3"], "#cf1620",
                                              width=4)]}]}
        sc = {"P": SCALE_QUARTER_INCH, "PLAN": SCALE_QUARTER_INCH}
        a, b = recompute_value(lin_fd, sc), recompute_value(lin_ref, sc)
        # The two forms are geometrically identical OFFLINE -- and that is exactly
        # the trap: JobTread measures the freedraw one as 0. This assert records
        # the equivalence; check_no_freedraw() is what keeps it out of a payload.
        assert abs(a - b) < 1e-9, (a, b)
        assert abs(a - 60.0) < 0.01, a            # 720 pt + 360 pt at 1/4" = 40 + 20 ft
        try:
            check_no_freedraw([lin_fd])
            raise AssertionError("freedraw in a payload must raise")
        except ValueError as e:
            assert "measure 0" in str(e)
        assert check_no_freedraw([lin_ref]) == 4

        # strip_server_fields drops only what the server generates
        dirty = {"name": "D", "measurementType": "area", "unit": "foot",
                 "value": 1.0,
                 "measurements": [{"name": "", "color": "#000", "planId": "P",
                                   "value": 1.0,
                                   "annotations": [
                                       {"id": "a", "type": "point", "x": 0, "y": 0,
                                        "page": 1, "fillColor": "#000"},
                                       {"id": "b", "type": "path", "page": 1,
                                        "points": [{"annotationId": "a"}],
                                        "strokeColor": "#000", "strokeWidth": 3}]}]}
        cl = strip_server_fields([dirty])[0]
        assert "value" not in cl and "value" not in cl["measurements"][0]
        anns = cl["measurements"][0]["annotations"]
        assert anns[0] == {"id": "a", "type": "point", "x": 0, "y": 0}
        assert anns[1]["strokeColor"] == "#000" and "page" not in anns[1]
        assert "value" in dirty, "strip_server_fields must not mutate its input"

        # recompute area, incl. isNegative, and the depth/width multipliers
        assert abs(recompute_value(p, sc) - 2586.67) < 0.05
        assert abs(recompute_value(n, sc) - 1943.62) < 0.05
        lv = dict(lin_fd, name="LV", measurementType="linearVolume")
        lv["measurements"] = [dict(lv["measurements"][0], unit="foot",
                                   width=1.0, depth=1.0)]
        assert abs(recompute_value(lv, sc) - 60.0) < 0.01

        # areaPitch: server returns plan area x the slope factor (pitchX=RUN, pitchY=RISE)
        ap = dict(p, name="AP", measurementType="areaPitch")
        ap["measurements"] = [dict(p["measurements"][0], pitchX=12, pitchY=3)]
        assert abs(recompute_value(ap, sc) - 2586.67 * 1.0307764) < 0.05, recompute_value(ap, sc)
        ap15 = dict(ap, name="AP15")
        ap15["measurements"] = [dict(p["measurements"][0], pitchX=12, pitchY=1.5)]
        assert abs(recompute_value(ap15, sc) - 2586.67 * 1.0077822) < 0.05

        # pre-send asserts
        assert check_payload([p, n])["parameters"] == 2
        for bad, why in (([p, dict(p)], "duplicate parameter names"),
                         ([p, dict(n, name="N2", measurements=p["measurements"])],
                          "duplicate annotation ids")):
            try:
                check_payload(bad)
                raise AssertionError(f"{why} must raise")
            except ValueError:
                pass
        orphan = {"name": "O", "measurementType": "linear", "unit": "foot",
                  "measurements": [{"name": "", "color": "#000", "planId": "P",
                                    "annotations": [path("op", ["nope"], "#000")]}]}
        try:
            check_payload([orphan])
            raise AssertionError("unresolved path refs must raise")
        except ValueError:
            pass
        check_unique_ids([p, n])
        print("selftest OK — scale table, closure, area math (incl. isNegative), dimensioned-unit\n"
              "         guard, merge, ids, freedraw round-trip + no-freedraw assert,\n"
              "         strip_server_fields, value recompute (incl. pitch),\n"
              "         pre-send asserts")
    else:
        print(__doc__)
