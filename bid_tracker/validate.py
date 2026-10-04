"""Strict validation of an import package. Any ERROR blocks the import.

The rule that matters most is E-NOSRC: the award amount (or the low bid, when there is no
award) and every rate-card price must appear, as a number, in a source excerpt. That is how
"never invent a number" is enforced mechanically.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from urllib.parse import urlparse

from bid_tracker import taxonomy
from bid_tracker.canonical import FORBIDDEN_COLUMNS, SPECS, Package, make_sol_ref
from bid_tracker.names import near_matches, name_key

MONEY_MAX = 1e9
FIXTURE_HOST = "example.invalid"
MULTI_AWARD_BASIS = {"rate_card", "best_value", "qualifications"}
PRIMARY_EVIDENCE = {"official_tab", "board_award_item", "portal_award_notice"}

_NUM_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


@dataclass
class Issue:
    code: str
    severity: str     # ERROR | WARN
    file: str
    line: int | None
    message: str

    def __str__(self) -> str:
        where = f"{self.file}:{self.line}" if self.line else self.file
        return f"{self.severity:5} {self.code:10} {where:28} {self.message}"


def numbers_in(text: str | None) -> list[float]:
    if not text:
        return []
    return [float(m.group(0).replace(",", "")) for m in _NUM_RE.finditer(text)]


def appears_in(target: float, texts: list[str | None], tol: float = 1.0) -> bool:
    return any(abs(n - target) <= tol for t in texts for n in numbers_in(t))


def check_url(url: str | None, evidence: str | None, fixtures: bool) -> str | None:
    """Return an error message, or None if the URL is acceptable."""
    if not url:
        return "source_url is required"
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if fixtures:
        if parsed.scheme != "https" or host != FIXTURE_HOST:
            return f"fixture mode only accepts https://{FIXTURE_HOST}/ URLs (got {url})"
        return None
    if host == FIXTURE_HOST:
        return f"{FIXTURE_HOST} URLs are test fixtures; use --fixtures against a scratch DB"
    if evidence == "internal" and parsed.scheme in ("https", "notion", "file"):
        return None
    if parsed.scheme not in ("https", "http") or not host:
        return f"source_url must be a public http(s) link (got {url})"
    return None


class Validator:
    def __init__(self, pkg: Package, *, fixtures: bool = False, known_agencies: set[str] | None = None,
                 known_sol_refs: set[str] | None = None, known_bidders: dict[str, str] | None = None,
                 today: date | None = None):
        self.pkg = pkg
        self.fixtures = fixtures
        self.known_agencies = set(known_agencies or ())
        self.known_sol_refs = set(known_sol_refs or ())
        self.known_bidders = dict(known_bidders or {})
        self.today = today or date.today()
        self.issues: list[Issue] = []

    def err(self, code, file, line, msg):
        self.issues.append(Issue(code, "ERROR", file, line, msg))

    def warn(self, code, file, line, msg):
        self.issues.append(Issue(code, "WARN", file, line, msg))

    # ------------------------------------------------------------------ structure
    def check_structure(self):
        if not self.pkg.files:
            self.err("E-SCHEMA", str(self.pkg.path), None, "no recognised CSV files in package")
            return
        for name, header in self.pkg.headers.items():
            spec = SPECS[name]
            missing = [c for c, (_k, req) in spec.items() if req and c not in header]
            if missing:
                self.err("E-SCHEMA", name, 1, f"missing required columns: {', '.join(missing)}")
            for col in header:
                if col in FORBIDDEN_COLUMNS:
                    self.err("E-SCHEMA", name, 1, f"derived column {col!r} not allowed in input; the tool computes it")
                elif col and col not in spec:
                    self.warn("W-SCHEMA", name, 1, f"unknown column {col!r} ignored")
        for name, rows in self.pkg.files.items():
            spec = SPECS[name]
            for r in rows:
                for col, msg in r.errors:
                    code = "E-ENUM" if spec[col][0].startswith("enum:") else ("E-DATE" if spec[col][0] == "date" else "E-NUM")
                    self.err(code, name, r.line, f"{col}: {msg}")
                for col, (_kind, req) in spec.items():
                    if req and r.values.get(col) is None and not any(c == col for c, _ in r.errors):
                        self.err("E-SCHEMA", name, r.line, f"{col} is required")

    # ------------------------------------------------------------------ agencies
    def agency_ids(self) -> set[str]:
        ids = set(self.known_agencies)
        for r in self.pkg.rows("agencies.csv"):
            aid = r.values.get("agency_id")
            if aid:
                ids.add(aid)
                self.check_fixture_id(aid, "agencies.csv", r.line)
        return ids

    def check_fixture_id(self, agency_id: str, file: str, line: int):
        is_fake = agency_id.startswith("fake-")
        if self.fixtures and not is_fake:
            self.err("E-URL", file, line, f"fixture mode requires fake- agency ids (got {agency_id})")
        if not self.fixtures and is_fake:
            self.err("E-URL", file, line, f"{agency_id} is a test fixture agency; use --fixtures against a scratch DB")

    # ------------------------------------------------------------------ solicitations
    def check_solicitations(self, agencies: set[str]) -> dict[str, dict]:
        sols: dict[str, dict] = {}
        work_class = {code: wc for code, wc, _l, _c in taxonomy.PROJECT_TYPES}
        for r in self.pkg.rows("solicitations.csv"):
            v, f, ln = r.values, r.file, r.line
            ref = v.get("sol_ref")
            if not ref:
                continue
            if ref in sols:
                self.err("E-DUP", f, ln, f"sol_ref {ref} appears twice in this package")
            sols[ref] = v
            expected = make_sol_ref(v.get("agency_id") or "", v.get("solicitation_no") or "")
            if ref != expected:
                self.err("E-REF", f, ln, f"sol_ref must be {expected!r} (agency_id:solicitation_no)")
            if v.get("agency_id"):
                self.check_fixture_id(v["agency_id"], f, ln)
                if v["agency_id"] not in agencies:
                    self.err("E-REF", f, ln, f"unknown agency_id {v['agency_id']!r}; add it to agencies.csv")
            pt, wc = v.get("project_type"), v.get("work_class")
            if pt and wc and work_class.get(pt) != wc:
                self.err("E-ENUM", f, ln, f"project_type {pt} is {work_class.get(pt)} work, not {wc}")
            if v.get("county") and not taxonomy.region_for(v["county"]) and not self.fixtures:
                self.warn("W-REF", f, ln, f"county {v['county']!r} is not a Florida county name")
            msg = check_url(v.get("source_url"), v.get("evidence_class"), self.fixtures)
            if msg:
                self.err("E-URL", f, ln, msg)
            if len(v.get("source_excerpt") or "") < 20:
                self.err("E-URL", f, ln, "source_excerpt must quote at least 20 characters of the source")
            for col in ("engineers_estimate", "award_amount", "ld_per_day"):
                x = v.get(col)
                if x is not None and not (0 < x < MONEY_MAX):
                    self.err("E-NUM", f, ln, f"{col} {x} out of range")
            if v.get("gsf") is not None and not (0 < v["gsf"] < 5_000_000):
                self.err("E-NUM", f, ln, f"gsf {v['gsf']} out of range")
            if v.get("gsf") and not v.get("gsf_basis"):
                self.err("E-ENUM", f, ln, "gsf needs gsf_basis (stated|measured|derived)")
            if v.get("engineers_estimate") and not v.get("ee_source"):
                self.err("E-EE", f, ln, "engineers_estimate needs ee_source (ee|budget|not_published)")
            for col in ("bid_bond_pct", "sbe_goal_pct"):
                x = v.get(col)
                if x is not None and not (0 <= x <= 100):
                    self.err("E-NUM", f, ln, f"{col} {x} must be a percent 0-100")
            self.check_dates(v, f, ln)
        return sols

    def check_dates(self, v: dict, f: str, ln: int):
        opened = v.get("bid_open_date")
        if not opened:
            return
        d_open = date.fromisoformat(opened)
        if d_open > self.today + timedelta(days=365):
            self.err("E-DATE", f, ln, f"bid_open_date {opened} is more than a year out")
        if v.get("award_date") and v["award_date"] < opened and (v.get("date_basis") or "bid_open") == "bid_open":
            self.err("E-DATE", f, ln, f"award_date {v['award_date']} is before bid_open_date {opened}")
        if v.get("advertise_date") and v["advertise_date"] > opened:
            self.err("E-DATE", f, ln, f"advertise_date {v['advertise_date']} is after bid_open_date {opened}")
        basis = v.get("date_basis") or "bid_open"
        if basis != "bid_open" and not v.get("notes"):
            self.warn("W-DATE", f, ln, f"bid_open_date is the {basis} date; say so in notes")
        if v.get("retrieved_at") and v.get("evidence_class") in PRIMARY_EVIDENCE and v["retrieved_at"] < opened:
            self.err("E-DATE", f, ln, f"retrieved_at {v['retrieved_at']} predates the bid opening; a tab can't exist yet")

    # ------------------------------------------------------------------ bids
    def check_bids(self, sols: dict[str, dict]):
        by_sol: dict[str, list] = defaultdict(list)
        valid_refs = set(sols) | self.known_sol_refs
        for r in self.pkg.rows("bids.csv"):
            v, f, ln = r.values, r.file, r.line
            ref = v.get("sol_ref")
            if ref and ref not in valid_refs:
                self.err("E-REF", f, ln, f"sol_ref {ref} not in solicitations.csv or the DB")
                continue
            msg = check_url(v.get("source_url"), (sols.get(ref) or {}).get("evidence_class"), self.fixtures)
            if msg:
                self.err("E-URL", f, ln, msg)
            for col in ("base_bid", "total_bid"):
                x = v.get(col)
                if x is not None and not (0 < x < MONEY_MAX):
                    self.err("E-NUM", f, ln, f"{col} {x} out of range")
            self.check_total(v, f, ln)
            if v.get("bidder_name_raw") and self.known_bidders:
                close = near_matches(v["bidder_name_raw"], self.known_bidders)
                if close:
                    names = "; ".join(f"{n} ({s})" for n, s in close[:3])
                    self.warn("W-NAME", f, ln, f"{v['bidder_name_raw']!r} looks like existing bidder(s): {names}")
            by_sol[ref].append(r)
        for ref, rows in by_sol.items():
            self.check_tab(ref, sols.get(ref), rows)
        return by_sol

    def check_total(self, v: dict, f: str, ln: int):
        basis, base, total = v.get("total_basis"), v.get("base_bid"), v.get("total_bid")
        alts = v.get("alternates_json")
        alt_sum = 0.0
        if alts is not None:
            if not isinstance(alts, dict) or not all(isinstance(x, (int, float)) for x in alts.values()):
                self.err("E-TOTAL", f, ln, 'alternates_json must be an object like {"Alt 1": 12500}')
                return
            alt_sum = float(sum(alts.values()))
        if basis == "rate_card":
            return
        if total is None and base is None:
            self.warn("W-TOTAL", f, ln, "no base_bid or total_bid on this bid")
            return
        if basis == "base" and base is not None and total is not None and abs(total - base) > 1:
            self.err("E-TOTAL", f, ln, f"total_basis=base but total {total} != base {base}")
        if basis == "base+all_alts" and base is not None and total is not None and abs(total - (base + alt_sum)) > 1:
            self.err("E-TOTAL", f, ln, f"total {total} != base {base} + alternates {alt_sum}")
        if basis == "base+accepted_alts" and base is not None and total is not None and total < base - 1:
            self.err("E-TOTAL", f, ln, f"total {total} is below base {base}")
        if total is not None and basis is None:
            self.err("E-TOTAL", f, ln, "total_bid needs total_basis")

    def check_tab(self, ref: str, sol: dict | None, rows: list):
        f = "bids.csv"
        keys: dict[str, int] = {}
        for r in rows:
            k = name_key(r.values.get("bidder_name_raw") or "")
            if k in keys:
                self.err("E-DUP", f, r.line, f"bidder repeats line {keys[k]} after name normalisation ({k!r})")
            keys[k] = r.line
        if sol is None:
            return
        basis = sol.get("award_basis")
        clean = [r for r in rows
                 if r.values.get("responsive") != 0 and not r.values.get("withdrawn") and r.values.get("total_bid")]
        totals = sorted(r.values["total_bid"] for r in clean)
        clean_ids = {id(r) for r in clean}
        # Published ranks must match what the numbers say.
        for r in rows:
            rp = r.values.get("rank_published")
            if rp is None or id(r) not in clean_ids:
                continue
            if basis == "low_bid":
                expected = 1 + sum(1 for t in totals if t < r.values["total_bid"] - 0.5)
            elif basis == "best_value" and r.values.get("score_total") is not None:
                scores = [x.values.get("score_total") for x in clean if x.values.get("score_total") is not None]
                expected = 1 + sum(1 for s in scores if s > r.values["score_total"] + 1e-9)
            else:
                continue
            if rp != expected:
                self.err("E-RANK", f, r.line, f"rank_published {rp} but the numbers put this bid at {expected}")
        if not totals:
            return
        low = totals[0]
        for r in clean:
            if r.values["total_bid"] > 4 * low:
                self.warn("W-SPREAD", f, r.line, f"bid {r.values['total_bid']:,.0f} is over 4x the low {low:,.0f}: decimal slip?")
        ee = sol.get("engineers_estimate")
        if ee and basis == "low_bid":
            ratio = low / ee
            if not (0.3 <= ratio <= 3.0):
                self.err("E-EE", "solicitations.csv", None, f"{ref}: low/EE = {ratio:.2f} is implausible; check both numbers")
            elif not (0.6 <= ratio <= 1.6):
                self.warn("W-EE", "solicitations.csv", None, f"{ref}: low/EE = {ratio:.2f} is unusual")
        # Awardee checks.
        awardees = [r for r in rows if r.values.get("is_awardee")]
        named = sol.get("awardee_name")
        if named:
            nk = name_key(named)
            match = [r for r in rows if name_key(r.values.get("bidder_name_raw") or "") == nk]
            if rows and not match:
                self.err("E-AWARD", "solicitations.csv", None, f"{ref}: awardee {named!r} is not among the bidders")
            flagged_other = [r for r in awardees if all(r is not m for m in match)]
            if match and flagged_other:
                self.err("E-AWARD", "bids.csv", flagged_other[0].line,
                         f"{ref}: is_awardee flags {flagged_other[0].values.get('bidder_name_raw')!r} "
                         f"but awardee_name is {named!r}")
            awardees = match or awardees
        multi_ok = basis in MULTI_AWARD_BASIS or sol.get("procurement_method") == "term_contract"
        if len(awardees) > 1 and not multi_ok:
            self.warn("W-AWARD", f, None, f"{ref}: {len(awardees)} awardees on a {basis} award")
        if basis == "low_bid" and sol.get("award_status") == "awarded" and awardees:
            a = awardees[0].values
            if a.get("total_bid") and a["total_bid"] > low + 1 and not sol.get("notes"):
                self.err("E-LOW", "solicitations.csv", None,
                         f"{ref}: awarded to {a.get('bidder_name_raw')!r} at {a['total_bid']:,.0f}, not the low "
                         f"{low:,.0f}; say why in notes (non-responsive low, responsibility, alternates)")
        award = sol.get("award_amount")
        if award and awardees and not sol.get("award_is_nte") and not multi_ok:
            at = awardees[0].values.get("total_bid")
            if at:
                diff = abs(award - at) / at
                if diff > 0.5:
                    self.err("E-AWARD", "solicitations.csv", None, f"{ref}: award {award:,.0f} vs awardee bid {at:,.0f} ({diff:.0%} apart)")
                elif diff > 0.1:
                    self.warn("W-AWARD", "solicitations.csv", None, f"{ref}: award {award:,.0f} vs awardee bid {at:,.0f} ({diff:.0%} apart)")

    # ------------------------------------------------------------------ items / rates
    def check_items(self, bids_by_sol: dict[str, list]):
        bid_lookup = {}
        for ref, rows in bids_by_sol.items():
            for r in rows:
                bid_lookup[(ref, name_key(r.values.get("bidder_name_raw") or ""))] = r.values
        sums: dict[tuple, float] = defaultdict(float)
        for r in self.pkg.rows("bid_items.csv"):
            v, f, ln = r.values, r.file, r.line
            key = (v.get("sol_ref"), name_key(v.get("bidder_name_raw") or ""))
            if key not in bid_lookup:
                self.err("E-REF", f, ln, f"no bids.csv row for {v.get('bidder_name_raw')!r} on {v.get('sol_ref')}")
                continue
            q, u, x = v.get("qty"), v.get("unit_price"), v.get("extended")
            if q is not None and u is not None and x is not None:
                if abs(q * u - x) > max(1.0, 0.001 * abs(x)):
                    self.warn("W-EXT", f, ln, f"qty x unit = {q * u:,.2f} but extended = {x:,.2f} (unit price governs)")
            if x is not None:
                sums[key] += x
        for key, total in sums.items():
            base = bid_lookup[key].get("base_bid")
            if base is not None and abs(total - base) > max(1.0, 0.0005 * base):
                self.err("E-TOTAL", "bid_items.csv", None,
                         f"{key[0]} / {key[1]}: items sum to {total:,.2f} but base_bid is {base:,.2f}")

    def check_rates(self, sols: dict[str, dict]):
        valid_refs = set(sols) | self.known_sol_refs
        for r in self.pkg.rows("rate_cards.csv"):
            v, f, ln = r.values, r.file, r.line
            ref = v.get("sol_ref")
            if ref not in valid_refs:
                self.err("E-REF", f, ln, f"sol_ref {ref} not in solicitations.csv or the DB")
                continue
            msg = check_url(v.get("source_url"), (sols.get(ref) or {}).get("evidence_class"), self.fixtures)
            if msg:
                self.err("E-URL", f, ln, msg)
            lo, hi = v.get("size_min_sf"), v.get("size_max_sf")
            if lo is not None and hi is not None and lo > hi:
                self.err("E-NUM", f, ln, f"size_min_sf {lo} > size_max_sf {hi}")
            if v.get("price") is not None and not (0 < v["price"] < MONEY_MAX):
                self.err("E-NUM", f, ln, f"price {v['price']} out of range")
            excerpts = [v.get("source_excerpt"), (sols.get(ref) or {}).get("source_excerpt")]
            if v.get("price") is not None and not appears_in(v["price"], excerpts, tol=0.005):
                self.err("E-NOSRC", f, ln, f"price {v['price']} does not appear in this row's or the solicitation's excerpt")

    # ------------------------------------------------------------------ never invent a number
    def check_sources(self, sols: dict[str, dict], bids_by_sol: dict[str, list]):
        for ref, sol in sols.items():
            rows = bids_by_sol.get(ref, [])
            excerpts = [sol.get("source_excerpt")] + [r.values.get("source_excerpt") for r in rows]
            excerpts += [r.values.get("source_excerpt") for r in self.pkg.rows("rate_cards.csv")
                         if r.values.get("sol_ref") == ref]
            clean = [r.values["total_bid"] for r in rows
                     if r.values.get("responsive") != 0 and not r.values.get("withdrawn") and r.values.get("total_bid")]
            if sol.get("award_amount"):
                target, label = sol["award_amount"], "award_amount"
            elif clean:
                target, label = min(clean), "low bid"
            else:
                target = None
            if target is not None and not appears_in(target, excerpts):
                self.err("E-NOSRC", "solicitations.csv", None,
                         f"{ref}: {label} {target:,.2f} does not appear in any source excerpt; quote the line it came from")
            ee = sol.get("engineers_estimate")
            if ee and not appears_in(ee, excerpts):
                self.warn("W-NOSRC", "solicitations.csv", None, f"{ref}: engineers_estimate {ee:,.2f} not quoted in an excerpt")
            for r in rows:
                t = r.values.get("total_bid")
                if t and not r.values.get("page_ref") and not appears_in(t, excerpts):
                    self.warn("W-NOSRC", "bids.csv", r.line, f"total {t:,.2f} has no page_ref and no quoting excerpt")

    # ------------------------------------------------------------------ private / index
    def check_pursuits(self, sols: dict[str, dict]):
        valid_refs = set(sols) | self.known_sol_refs
        for r in self.pkg.rows("ideal_pursuits.csv"):
            v, f, ln = r.values, r.file, r.line
            if v.get("sol_ref") not in valid_refs:
                self.err("E-REF", f, ln, f"sol_ref {v.get('sol_ref')} not in solicitations.csv or the DB")
            m = v.get("markup_pct")
            if m is not None and not (-0.5 <= m <= 1.0):
                self.err("E-NUM", f, ln, f"markup_pct {m} must be a fraction (0.08 = 8%)")
            for col in ("est_direct_cost", "est_cost_pre_ohp", "bid_amount"):
                x = v.get(col)
                if x is not None and not (0 < x < MONEY_MAX):
                    self.err("E-NUM", f, ln, f"{col} {x} out of range")

    def check_index(self):
        for r in self.pkg.rows("cost_index.csv"):
            v, f, ln = r.values, r.file, r.line
            if v.get("period") and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", v["period"]):
                self.err("E-DATE", f, ln, f"period {v['period']!r} must be YYYY-MM")
            if v.get("value") is not None and v["value"] <= 0:
                self.err("E-NUM", f, ln, "index value must be positive")
            msg = check_url(v.get("source_url"), None, self.fixtures)
            if msg:
                self.err("E-URL", f, ln, msg)

    def run(self) -> list[Issue]:
        self.check_structure()
        agencies = self.agency_ids()
        sols = self.check_solicitations(agencies)
        bids_by_sol = self.check_bids(sols)
        self.check_items(bids_by_sol)
        self.check_rates(sols)
        self.check_sources(sols, bids_by_sol)
        self.check_pursuits(sols)
        self.check_index()
        return self.issues


def validate_package(pkg: Package, **kwargs) -> list[Issue]:
    return Validator(pkg, **kwargs).run()


def has_errors(issues: list[Issue]) -> bool:
    return any(i.severity == "ERROR" for i in issues)


def issues_json(issues: list[Issue]) -> str:
    return json.dumps([asdict(i) for i in issues], indent=2)
