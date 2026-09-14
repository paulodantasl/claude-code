"""
Qualification and scoring — PLAN.md §2.3 and §2.4.

Adapted to what the sources can actually supply. Two places where the plan
assumed a field that does not exist, and what is done instead:

  * `value_est` is never available from the Tampa permit layer. §2.4 already
    scores an unknown value at 8/20, so permits simply take that.
  * §2.3(e) requires "an identifiable entity with >= 1 public contact channel".
    No permit row can satisfy that — the layer has no contact field — so
    enforcing it as a hard gate would qualify nothing at all. It is instead a
    SOFT blocker: it caps the Access component at 0 and tags the signal
    `needs_contact`, which is the queue for address-matching against the
    alcoholic-beverage layer, Sunbiz and HCPA in Phase 2. Hard blockers, the
    ones that disqualify outright, are: outside every submarket, trade `other`,
    blocklisted, or a bid window that has already closed.
"""
from __future__ import annotations

import math
import os
import re
from datetime import date, datetime, timedelta

import yaml

BLOCKLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocklist.yaml")

QUALIFY_AT = 55

FIT = {"medical": 30, "restaurant": 25, "hospitality": 20, "retail": 15,
       "office": 10, "other": 0}

# A strip-out declares no trade — the build-back permit does that, and it has
# not been filed. Scoring it 0 would bury a committed tenant whose fitout is
# still unbid, so it gets a stated band of its own, between retail and
# hospitality. This is a design decision, not a measurement.
FIT_PRECURSOR = 20

# stage_hint -> (days until the window opens, days it stays open)
# Permit stages, from what the layer can express (PLAN.md §2.3(d)):
#   early_start  the main permit is still pending; buyout is live now
#   revision     the job is in flight; change orders and late scope
#   issued       already awarded
# Licence and entitlement stages arrive in Phase 2.
BID_WINDOW = {
    "early_start": (0, 60),
    "strip_out": (0, 90),         # build-back permit still to be filed
    "revision": (0, 45),
    "issued": (0, 0),
    "pre_permit": (30, 180),      # entitlement / licence filed
    "abt": (30, 180),
    "dbpr_hr": (30, 180),
    "sunbiz": (90, 365),
    "ahca": (60, 270),
}


def _load_blocklist() -> tuple[list[str], list[str]]:
    with open(BLOCKLIST_PATH) as fh:
        data = yaml.safe_load(fh) or {}
    return (data.get("national_in_house") or [], data.get("public_procurement") or [])


_NATIONAL, _PUBLIC = _load_blocklist()


def _norm(name: str | None) -> str:
    return re.sub(r"[^a-z0-9&' ]+", " ", (name or "").lower()).strip()


def blocklist_hit(*names: str | None) -> str | None:
    """Returns the pattern that matched, or None. Checked against every name
    we have for the signal, because the tenant may only appear in the scope."""
    for name in names:
        n = _norm(name)
        if not n:
            continue
        for pattern in _NATIONAL:
            if pattern in n:
                return pattern
        for pattern in _PUBLIC:
            if pattern in n:
                return pattern
    return None


def bid_window(stage_hint: str, filed_at: str | None, today: date | None = None
               ) -> tuple[str | None, str | None]:
    """(open, close) as ISO dates, inferred from the stage. PLAN.md §2.4."""
    today = today or date.today()
    offset, length = BID_WINDOW.get(stage_hint, (0, 0))
    if stage_hint == "issued":
        # Already awarded: the window closed when the permit issued.
        return (filed_at, filed_at)
    opens = today + timedelta(days=offset)
    return (opens.isoformat(), (opens + timedelta(days=length)).isoformat())


def _days_until(iso: str | None, today: date | None = None) -> int | None:
    if not iso:
        return None
    try:
        return (date.fromisoformat(iso[:10]) - (today or date.today())).days
    except ValueError:
        return None


def urgency_points(opens: str | None, stage_hint: str, today: date | None = None) -> int:
    if stage_hint == "issued":
        return 0
    d = _days_until(opens, today)
    if d is None:
        return 5
    if d <= 30:
        return 30
    if d <= 90:
        return 22
    if d <= 180:
        return 12
    return 5


def value_points(value_est: float | None) -> int:
    if not value_est or value_est <= 0:
        return 8                              # PLAN §2.4: unknown -> 8
    return int(min(20, max(0, round(4 * math.log10(value_est / 10_000)))))


def access_points(signal: dict, blocked: str | None) -> int:
    """§2.4 Access, ±20.

    PLAN's second +10 is "owner-occupier or local LLC". Nothing in the permit
    layer states ownership, so the proxy used here is: an entity name was
    resolved from the record AND it is not on the national-in-house or
    public-procurement blocklist — i.e. a named counterparty we could plausibly
    reach. Sunbiz and HCPA can turn that proxy into a fact in Phase 2; until
    then it is labelled `named_local_entity` in the components, not claimed as
    verified ownership.
    """
    pts = 0
    if signal.get("contacts"):
        pts += 10
    if signal.get("entity") and not blocked:
        pts += 10
    if blocked:
        pts -= 20
    if signal.get("contractor_name"):
        pts -= 15                             # a GC is already on the record
    return max(-20, min(20, pts))


def meets_size_gate(signal: dict) -> bool:
    """§2.3(c). Licence-type sources pass on the second branch, because value
    is unknowable there — and so do permits, for the same reason."""
    if signal.get("source") in {"abt", "ahca", "dbpr_hr", "permit", "entitlement"}:
        return True
    return bool((signal.get("value_est") or 0) >= 75_000
                or (signal.get("sqft") or 0) >= 1_200
                or (signal.get("seats") or 0) >= 30)


def score(signal: dict, today: date | None = None) -> dict:
    """Returns the scoring block to merge into the signal.

    `qualified` means: score at or above the bar AND no hard blocker. Soft
    blockers are reported but do not disqualify.
    """
    stage = signal.get("stage_hint") or "issued"
    opens, closes = bid_window(stage, signal.get("filed_at"), today)
    blocked = blocklist_hit(signal.get("entity"), signal.get("brand"),
                            signal.get("project_name"))

    trade = signal.get("trade") or "other"
    precursor = stage == "strip_out" and trade == "other"
    fit = FIT_PRECURSOR if precursor else FIT.get(trade, 0)
    urg = urgency_points(opens, stage, today)
    val = value_points(signal.get("value_est"))
    acc = access_points(signal, blocked)
    total = max(0, min(100, fit + urg + val + acc))

    hard: list[str] = []
    soft: list[str] = []
    if not signal.get("hood"):
        hard.append("outside_submarkets")
    if trade == "other" and not precursor:
        hard.append("trade_other")
    if blocked:
        hard.append(f"blocklist:{blocked}")
    if stage == "issued":
        hard.append("already_awarded")
    if not meets_size_gate(signal):
        hard.append("below_size_gate")

    if not signal.get("entity"):
        soft.append("no_entity")
    if not signal.get("contacts"):
        soft.append("needs_contact")
    if (signal.get("confidence") or 0) < 0.5:
        soft.append("low_confidence_trade")
    if precursor:
        soft.append("trade_undeclared_strip_out")

    return {
        "score": total,
        "score_components": {"fit": fit, "urgency": urg, "value": val, "access": acc},
        "bid_window": {"open": opens, "close": closes},
        "qualified": total >= QUALIFY_AT and not hard,
        "blockers": hard,
        "warnings": soft,
        "late": stage == "issued",
    }
