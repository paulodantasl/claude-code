"""
Diff engine: turn (previous snapshot, freshly-scraped permit) into a
:class:`StatusEvent` when something a field manager would care about changed.

Watched by default:
  * status            (normalised to a phase — the primary signal)
  * issued_date       (permit just got issued)
  * expiry_date       (deadline set / moved)
Plus any per-permit ``watch_fields`` that live inside the portal's raw_data
(e.g. "next_inspection", "assigned_reviewer", "plan_check_round").
"""
from __future__ import annotations

import logging
from typing import Any

from .models import FieldChange, Snapshot, StatusEvent, TrackedPermit, utcnow_iso
from .status import Phase, direction, normalize, priority_for

logger = logging.getLogger(__name__)


def _iso(value: Any) -> str | None:
    """Normalise a date-ish value to an ISO string for stable comparison."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def snapshot_from_permit(permit_key: str, raw: Any, watch_fields: list[str]) -> Snapshot:
    """Build a Snapshot from a freshly-scraped RawPermit-like object."""
    raw_data = getattr(raw, "raw_data", None) or {}
    extra = {f: raw_data.get(f) for f in watch_fields if f in raw_data}
    return Snapshot(
        permit_key=permit_key,
        status=getattr(raw, "status", None),
        phase=normalize(getattr(raw, "status", None)).value,
        issued_date=_iso(getattr(raw, "issued_date", None)),
        expiry_date=_iso(getattr(raw, "expiry_date", None)),
        description=getattr(raw, "description", None),
        extra=extra,
        source_url=getattr(raw, "source_url", None),
    )


def diff_snapshots(
    previous: Snapshot | None,
    current: Snapshot,
    watch_fields: list[str],
) -> list[FieldChange]:
    """Return the list of watched fields that changed. Empty = no update."""
    changes: list[FieldChange] = []

    # Status: report when the human-visible text changes (ignoring surrounding
    # whitespace so pure formatting churn on the portal doesn't page anyone).
    prev_status = previous.status if previous else None
    if (prev_status or "").strip() != (current.status or "").strip():
        changes.append(FieldChange("status", prev_status, current.status))

    prev_issued = previous.issued_date if previous else None
    if prev_issued != current.issued_date:
        changes.append(FieldChange("issued_date", prev_issued, current.issued_date))

    prev_expiry = previous.expiry_date if previous else None
    if prev_expiry != current.expiry_date:
        changes.append(FieldChange("expiry_date", prev_expiry, current.expiry_date))

    prev_extra = (previous.extra if previous else {}) or {}
    for f in watch_fields:
        old = prev_extra.get(f)
        new = current.extra.get(f)
        if old != new:
            changes.append(FieldChange(f, old, new))

    return changes


def build_event(
    tracked: TrackedPermit,
    county_name: str | None,
    previous: Snapshot | None,
    current: Snapshot,
    changes: list[FieldChange],
) -> StatusEvent:
    """Assemble a StatusEvent from a detected set of changes."""
    old_phase = Phase(previous.phase) if previous else None
    new_phase = normalize(current.status)
    dir_ = direction(old_phase, new_phase)
    priority = priority_for(new_phase)

    return StatusEvent(
        permit_key=tracked.key,
        permit_number=tracked.permit_number,
        county=tracked.county,
        county_name=county_name,
        project_name=tracked.project_name,
        category=tracked.category,
        changes=changes,
        old_status=previous.status if previous else None,
        new_status=current.status,
        old_phase=old_phase.value if old_phase else Phase.UNKNOWN.value,
        new_phase=new_phase.value,
        direction=dir_,
        priority=priority,
        detected_at=utcnow_iso(),
        source_url=current.source_url or tracked.source_url,
        manager_ids=list(tracked.manager_ids),
    )
