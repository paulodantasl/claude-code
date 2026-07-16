"""
Permit status normalisation.

Municipal portals each use their own free-text status labels ("Plan Review",
"In Review", "Under Review", "Application Accepted", "Corrections Required",
"Ready to Issue", "Permit Issued", "CO Issued", …). To decide whether a status
*change* is meaningful — and how urgent it is — we normalise each raw label to
a small set of lifecycle **phases** and rank them along the permit's path from
application to close-out.

This mapping is deliberately heuristic and keyword-driven so it can be extended
for a new jurisdiction by adding a keyword, without touching the diff engine.
"""
from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    """Normalised lifecycle phase for a permit."""

    UNKNOWN = "unknown"
    SUBMITTED = "submitted"                 # application received / intake
    IN_REVIEW = "in_review"                 # plan review / routing
    ACTION_REQUIRED = "action_required"     # corrections / on hold / resubmit
    APPROVED = "approved"                   # approved, ready to issue
    ISSUED = "issued"                       # permit issued / active
    INSPECTIONS = "inspections"             # inspections in progress
    FINALED = "finaled"                     # finaled / CO issued / completed
    DENIED = "denied"                       # denied / disapproved
    EXPIRED = "expired"                     # expired
    WITHDRAWN = "withdrawn"                 # withdrawn / cancelled / abandoned


# Progression ladder for "normal" forward movement. Index = how far along.
# Phases not in this list (ACTION_REQUIRED / DENIED / EXPIRED / WITHDRAWN) are
# handled as special cases in ``direction``.
_LADDER: list[Phase] = [
    Phase.SUBMITTED,
    Phase.IN_REVIEW,
    Phase.APPROVED,
    Phase.ISSUED,
    Phase.INSPECTIONS,
    Phase.FINALED,
]

# Phases that demand a field manager do something, or that a project has stalled
# or died. These always notify at HIGH priority.
_ATTENTION: set[Phase] = {Phase.ACTION_REQUIRED, Phase.DENIED, Phase.EXPIRED}

# Terminal phases — the permit is effectively done (good or bad).
_TERMINAL: set[Phase] = {Phase.FINALED, Phase.DENIED, Phase.EXPIRED, Phase.WITHDRAWN}

# Ordered keyword rules. Checked top-to-bottom; first hit wins, so the most
# specific / most negative labels are listed first. Matching is case-insensitive
# substring matching against the raw status text.
_KEYWORD_RULES: list[tuple[Phase, tuple[str, ...]]] = [
    (Phase.ACTION_REQUIRED, (
        "correction", "revision", "resubmit", "on hold", "hold",
        "deficien", "incomplete", "info required", "information required",
        "additional information", "returned to applicant", "returned for",
        "rejected plan", "reject - resubmit", "stop work", "needs revision",
        "pending applicant", "awaiting", "insufficient",
    )),
    (Phase.DENIED, ("denied", "denial", "disapprove", "not approved", "void")),
    (Phase.WITHDRAWN, ("withdraw", "cancel", "abandon")),
    (Phase.EXPIRED, ("expired", "expiration", "lapsed")),
    (Phase.INSPECTIONS, ("inspection", "inspect")),
    (Phase.FINALED, (
        "finaled", "finalled", "final -", "certificate of occupancy",
        "c of o", "c.o.", "co issued", "closed", "complete", "cofo",
    )),
    (Phase.ISSUED, ("issued", "active", "permit issued")),
    (Phase.APPROVED, ("approved", "ready to issue", "ready-to-issue", "approval", "passed review")),
    (Phase.IN_REVIEW, (
        "review", "routing", "in process", "in-process", "processing",
        "plan check", "plancheck", "distributed", "assigned to reviewer",
    )),
    (Phase.SUBMITTED, (
        "application received", "app received", "submitted", "received",
        "accepted", "intake", "applied", "pending", "new", "open",
    )),
]


def normalize(status: str | None) -> Phase:
    """Map a raw portal status string to a normalised :class:`Phase`."""
    if not status:
        return Phase.UNKNOWN
    text = status.strip().lower()
    if not text:
        return Phase.UNKNOWN
    for phase, keywords in _KEYWORD_RULES:
        if any(kw in text for kw in keywords):
            return phase
    return Phase.UNKNOWN


def is_terminal(phase: Phase) -> bool:
    """True if the permit has reached a done state (finaled, denied, …)."""
    return phase in _TERMINAL


def needs_attention(phase: Phase) -> bool:
    """True if the phase requires field-manager action or signals a problem."""
    return phase in _ATTENTION


def priority_for(phase: Phase) -> str:
    """Return ``"high"`` for attention phases, else ``"normal"``."""
    return "high" if phase in _ATTENTION else "normal"


def direction(old: Phase | None, new: Phase) -> str:
    """
    Classify the movement between two phases.

    Returns one of:
      "first_seen"  — no prior phase (baseline)
      "attention"   — moved into a corrections/denied/expired state
      "forward"     — advanced along the normal ladder
      "backward"    — regressed along the normal ladder
      "lateral"     — same ladder position / unknown movement
    """
    if old is None:
        return "first_seen"
    if new in _ATTENTION:
        return "attention"

    old_rank = _LADDER.index(old) if old in _LADDER else None
    new_rank = _LADDER.index(new) if new in _LADDER else None
    if old_rank is None or new_rank is None:
        return "lateral"
    if new_rank > old_rank:
        return "forward"
    if new_rank < old_rank:
        return "backward"
    return "lateral"


def describe_phase(phase: Phase) -> str:
    """Human-friendly one-liner for a phase (used in notifications)."""
    return {
        Phase.UNKNOWN: "Status unknown",
        Phase.SUBMITTED: "Application submitted / received",
        Phase.IN_REVIEW: "In plan review",
        Phase.ACTION_REQUIRED: "Action required — corrections / hold",
        Phase.APPROVED: "Approved — ready to issue",
        Phase.ISSUED: "Permit issued",
        Phase.INSPECTIONS: "Inspections in progress",
        Phase.FINALED: "Finaled / Certificate of Occupancy",
        Phase.DENIED: "Denied",
        Phase.EXPIRED: "Expired",
        Phase.WITHDRAWN: "Withdrawn / cancelled",
    }[phase]
