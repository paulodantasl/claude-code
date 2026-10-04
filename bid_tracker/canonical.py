"""Canonical import package: column specs, parsing, and package loading.

A package is a directory of CSVs. solicitations.csv is required; the rest are optional:

    agencies.csv        new agencies not in reference/agencies.csv
    solicitations.csv   one row per solicitation (keyed by sol_ref)
    bids.csv            one row per bidder per solicitation
    bid_items.csv       unit-price lines per bidder
    rate_cards.csv      term/disaster contract rates per bidder
    ideal_pursuits.csv  Ideal's own go/no-go, cost, bid and result (private)
    cost_index.csv      escalation index values (written by `ingest bls-ppi`)
    areas.csv           square footage per solicitation, by kind, each with its cited page

Derived values (ranks, gaps, $/SF, escalation) are computed by the tool and are refused in input.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from bid_tracker import taxonomy

# column -> (type, required). Types: text, money, num, int, bool, date, enum:<name>, json
SPECS: dict[str, dict[str, tuple[str, bool]]] = {
    "agencies.csv": {
        "agency_id": ("text", True), "name": ("text", True), "agency_type": ("enum:agency_type", True),
        "county": ("text", False), "region": ("text", False), "portal_platform": ("text", False),
        "portal_url": ("text", False), "watch": ("int", False), "notes": ("text", False),
    },
    "solicitations.csv": {
        "sol_ref": ("text", True), "agency_id": ("text", True), "solicitation_no": ("text", True),
        "title": ("text", True), "procurement_method": ("enum:method", True), "award_basis": ("enum:award_basis", True),
        "work_class": ("enum:work_class", True), "project_type": ("enum:project_type", True),
        "facility_type": ("text", False), "county": ("text", False), "gsf": ("num", False),
        "gsf_basis": ("enum:gsf_basis", False), "area_kind": ("enum:area_kind", False), "advertise_date": ("date", False), "bid_open_date": ("date", True),
        "date_basis": ("enum:date_basis", False),
        "engineers_estimate": ("money", False), "ee_source": ("enum:ee_source", False),
        "award_amount": ("money", False), "award_is_nte": ("bool", False), "awardee_name": ("text", False),
        "award_date": ("date", False), "award_status": ("enum:award_status", False),
        "bid_bond_pct": ("num", False), "pp_bond_required": ("bool", False), "sbe_goal_pct": ("num", False),
        "contract_days": ("int", False), "ld_per_day": ("money", False), "federal_funds": ("bool", False),
        "prequal_required": ("bool", False), "protest_filed": ("bool", False),
        "source_url": ("text", True), "source_excerpt": ("text", True), "evidence_class": ("enum:evidence", True),
        "retrieved_at": ("date", True), "extracted_by": ("text", True), "notes": ("text", False),
    },
    "bids.csv": {
        "sol_ref": ("text", True), "bidder_name_raw": ("text", True), "fl_license_no": ("text", False),
        "base_bid": ("money", False), "alternates_json": ("json", False), "total_bid": ("money", False),
        "total_basis": ("enum:total_basis", False), "rank_published": ("int", False),
        "score_total": ("num", False), "score_price": ("num", False), "responsive": ("bool", False),
        "withdrawn": ("bool", False), "is_awardee": ("bool", False), "page_ref": ("text", False),
        "source_url": ("text", True), "source_excerpt": ("text", False),
    },
    "bid_items.csv": {
        "sol_ref": ("text", True), "bidder_name_raw": ("text", True), "line_no": ("text", True),
        "item_desc": ("text", True), "unit": ("text", False), "qty": ("num", False),
        "unit_price": ("money", False), "extended": ("money", False), "item_code": ("text", False),
        "csi_division": ("text", False), "is_allowance": ("bool", False),
    },
    "rate_cards.csv": {
        "sol_ref": ("text", True), "bidder_name_raw": ("text", True), "service": ("enum:service", True),
        "service_desc": ("text", False), "size_min_sf": ("num", False), "size_max_sf": ("num", False),
        "unit": ("text", True), "price": ("money", True), "after_hours_premium_pct": ("num", False),
        "response_hrs": ("num", False), "source_url": ("text", True), "source_excerpt": ("text", False),
    },
    "ideal_pursuits.csv": {
        "sol_ref": ("text", True), "decision": ("enum:decision", False), "decision_date": ("date", False),
        "decision_reason": ("text", False), "est_direct_cost": ("money", False), "est_cost_pre_ohp": ("money", False),
        "bid_amount": ("money", False), "markup_pct": ("num", False), "result": ("enum:result", False),
        "rank": ("int", False), "score_total": ("num", False), "score_breakdown_json": ("json", False),
        "debrief": ("text", False), "lessons": ("text", False), "estimate_dir": ("text", False),
    },
    "cost_index.csv": {
        "series_id": ("text", True), "period": ("text", True), "value": ("num", True),
        "preliminary": ("bool", False), "retrieved_at": ("date", True), "source_url": ("text", True),
    },
    "areas.csv": {
        "sol_ref": ("text", True), "area_kind": ("enum:area_kind", True), "sf": ("num", True),
        "basis": ("enum:gsf_basis", True), "source_url": ("text", True), "source_page": ("text", True),
        "excerpt": ("text", True), "retrieved_at": ("date", True), "notes": ("text", False),
    },
}
FILE_ORDER = list(SPECS)

# Columns the tool computes. Seeing one in input means someone pasted derived numbers.
FORBIDDEN_COLUMNS = {
    "low_bid", "second_bid", "gap", "gap_pct", "low_psf", "cost_psf", "price_psf", "low_ee", "low_to_ee",
    "price_rank", "n_bidders", "escalated", "escalated_amount", "pct_above_low", "region_band", "size_band",
}

ENUMS = {
    "agency_type": taxonomy.AGENCY_TYPES,
    "method": taxonomy.PROCUREMENT_METHODS,
    "award_basis": taxonomy.AWARD_BASIS,
    "work_class": taxonomy.WORK_CLASSES,
    "project_type": tuple(sorted(taxonomy.PROJECT_TYPE_CODES)),
    "gsf_basis": taxonomy.GSF_BASIS,
    "area_kind": taxonomy.AREA_KINDS,
    "ee_source": taxonomy.EE_SOURCES,
    "award_status": taxonomy.AWARD_STATUS,
    "evidence": taxonomy.EVIDENCE_CLASSES,
    "date_basis": taxonomy.DATE_BASIS,
    "total_basis": taxonomy.TOTAL_BASIS,
    "service": taxonomy.RATE_SERVICES,
    "decision": taxonomy.PURSUIT_DECISIONS,
    "result": taxonomy.PURSUIT_RESULTS,
}


class ParseError(ValueError):
    pass


def parse_money(value: str) -> float | None:
    s = (value or "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").strip()
    if s.startswith("-"):
        neg, s = True, s[1:]
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        raise ParseError(f"not a dollar amount: {value!r}")
    v = float(s)
    return -v if neg else v


def parse_num(value: str) -> float | None:
    s = (value or "").strip().replace(",", "")
    if not s:
        return None
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError as exc:
        raise ParseError(f"not a number: {value!r}") from exc


def parse_int(value: str) -> int | None:
    v = parse_num(value)
    if v is None:
        return None
    if v != int(v):
        raise ParseError(f"not a whole number: {value!r}")
    return int(v)


def parse_bool(value: str) -> int | None:
    s = (value or "").strip().lower()
    if not s:
        return None
    if s in ("1", "y", "yes", "true", "t", "x"):
        return 1
    if s in ("0", "n", "no", "false", "f"):
        return 0
    raise ParseError(f"not yes/no: {value!r}")


def parse_date(value: str) -> str | None:
    s = (value or "").strip()
    if not s:
        return None
    s = s[:10]
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError as exc:
        raise ParseError(f"not an ISO date (YYYY-MM-DD): {value!r}") from exc


def parse_json(value: str):
    s = (value or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError as exc:
        raise ParseError(f"bad JSON: {value!r}") from exc


def parse_value(kind: str, value: str):
    if kind == "text":
        s = (value or "").strip()
        return s or None
    if kind == "money":
        return parse_money(value)
    if kind == "num":
        return parse_num(value)
    if kind == "int":
        return parse_int(value)
    if kind == "bool":
        return parse_bool(value)
    if kind == "date":
        return parse_date(value)
    if kind == "json":
        return parse_json(value)
    if kind.startswith("enum:"):
        s = (value or "").strip()
        if not s:
            return None
        allowed = ENUMS[kind[5:]]
        if s not in allowed:
            raise ParseError(f"{s!r} not one of {', '.join(allowed)}")
        return s
    raise ValueError(kind)


def make_sol_ref(agency_id: str, solicitation_no: str) -> str:
    no = re.sub(r"\s+", "", (solicitation_no or "").upper())
    no = re.sub(r"[^A-Z0-9\-\.]", "-", no).strip("-")
    return f"{(agency_id or '').strip().lower()}:{no}"


@dataclass
class Row:
    file: str
    line: int          # 1-based CSV line number (header is line 1)
    raw: dict
    values: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)   # (column, message)


@dataclass
class Package:
    path: Path
    files: dict[str, list[Row]] = field(default_factory=dict)
    headers: dict[str, list[str]] = field(default_factory=dict)

    def rows(self, name: str) -> list[Row]:
        return self.files.get(name, [])

    def sha256(self) -> str:
        h = hashlib.sha256()
        for name in FILE_ORDER:
            p = self.path / name
            if p.exists():
                h.update(name.encode())
                h.update(p.read_bytes())
        return h.hexdigest()


def load_package(path: Path | str) -> Package:
    path = Path(path)
    if not path.is_dir():
        raise FileNotFoundError(f"package directory not found: {path}")
    pkg = Package(path=path)
    for name, spec in SPECS.items():
        p = path / name
        if not p.exists():
            continue
        with open(p, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            pkg.headers[name] = [h.strip() for h in (reader.fieldnames or [])]
            rows = []
            for i, raw in enumerate(reader, start=2):
                raw = {(k or "").strip(): (v if v is not None else "") for k, v in raw.items()}
                if not any(str(v).strip() for v in raw.values()):
                    continue
                row = Row(file=name, line=i, raw=raw)
                for col, (kind, _req) in spec.items():
                    try:
                        row.values[col] = parse_value(kind, raw.get(col, ""))
                    except ParseError as exc:
                        row.values[col] = None
                        row.errors.append((col, str(exc)))
                rows.append(row)
            pkg.files[name] = rows
    return pkg


def record_hash(values: dict) -> str:
    payload = json.dumps({k: values[k] for k in sorted(values)}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
