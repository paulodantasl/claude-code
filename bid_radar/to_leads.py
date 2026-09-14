"""
Bridge: Bid Radar signals -> ideal_apis LeadRecord -> ApprovalBatch.

Reuses the existing approve -> JobTread -> QUO flow unchanged. The only change
made to `ideal_apis` is the `Source` literal.

Where a signal lands in the batch:

  * `contacts` populated  -> **contact lead**. Eligible for a JobTread push,
    because `LeadRecord.has_contact_channel()` gates that push and
    `JobTreadClient.push_lead` skips anything without a phone or email.
  * `contacts` empty      -> **intel lead**. Every permit-sourced signal is
    here today: the Tampa permit layer has no contact field. They still carry
    the address, the source link and the score, so they are workable by hand
    and they are the queue Phase 2 enriches from the alcoholic-beverage layer.

Dry run by default: prints what it would create and writes nothing.

    python bid_radar/to_leads.py --signals bid_radar/data/signals.jsonl
    python bid_radar/to_leads.py --signals ... --write
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geo  # noqa: E402

# Every Bid Radar signal is commercial GC work, medical fitouts included —
# `ideal_dental` and `ideal_remodeling` are the other two brands' lead streams
# and this feed does not produce either.
BRAND = "ideal_cgc"

# Score band -> the pipeline's own priority vocabulary.
def _priority(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _ensure_ideal_apis() -> None:
    """Make `import ideal_apis` reach the package, not the directory.

    The repo root holds a directory named `ideal_apis/` whose contents are the
    project (`ideal_apis/ideal_apis/`) plus a YAML directory `ideal_apis/config/`.
    Importing from the repo root therefore resolves `ideal_apis` as a namespace
    package and `ideal_apis.config` as that YAML directory, so
    `from ideal_apis.config import Settings` fails with "unknown location".
    Detect that shadow by the absent `__file__` and put the real package dir on
    the path instead.
    """
    import importlib  # noqa: PLC0415
    try:
        mod = importlib.import_module("ideal_apis")
        if getattr(mod, "__file__", None):
            return
        for name in [n for n in sys.modules if n == "ideal_apis"
                     or n.startswith("ideal_apis.")]:
            del sys.modules[name]
    except ImportError:
        pass
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ideal_apis"))
    importlib.invalidate_caches()


def _import_lead_record():
    """Imported lazily so this module is importable without ideal_apis."""
    _ensure_ideal_apis()  # noqa: F821
    from ideal_apis.pipeline.models import LeadRecord  # noqa: PLC0415
    return LeadRecord


def signal_to_lead(signal: dict, LeadRecord):  # noqa: N803
    """One signal -> one LeadRecord. Nothing is invented: a field the source
    did not supply stays None."""
    phone = next((c["value"] for c in signal.get("contacts") or []
                  if c.get("kind") == "phone"), None)
    email = next((c["value"] for c in signal.get("contacts") or []
                  if c.get("kind") == "email"), None)

    name = signal.get("entity") or signal.get("scope") or signal.get("source_id")
    hood = signal.get("hood")
    notes = " · ".join(filter(None, [
        f"{geo.hood_label(hood)}" if hood else None,
        f"{signal.get('trade')}",
        f"stage {signal.get('stage_hint')}",
        f"score {signal.get('score')}",
        f"filed {signal.get('filed_at')}" if signal.get("filed_at") else None,
        f"bid window {signal.get('bid_window', {}).get('open')}"
        f"–{signal.get('bid_window', {}).get('close')}"
        if signal.get("bid_window") else None,
        f"occupancy {signal.get('occupancy_category')}"
        if signal.get("occupancy_category") else None,
        (signal.get("description") or "")[:160] or None,
        signal.get("source_url"),
    ]))

    return LeadRecord(
        id=signal["id"],
        source=signal["source"],
        brand=BRAND,
        name=name,
        phone=phone,
        email=email,
        street=signal.get("address"),
        city="Tampa",
        state="FL",
        zip_code=signal.get("zip"),
        priority=_priority(signal.get("score") or 0),
        notes=notes,
        raw={k: signal.get(k) for k in (
            "source_id", "source_url", "retrieved_at", "hood", "trade",
            "stage_hint", "score", "score_components", "bid_window", "qualified",
            "blockers", "warnings", "lat", "lon", "occupancy_category",
            "record_type", "project_name", "value_est", "sqft")},
    )


def build(signals: list[dict], *, qualified_only: bool = True):
    LeadRecord = _import_lead_record()
    rows = [s for s in signals if s.get("qualified")] if qualified_only else signals
    leads = [signal_to_lead(s, LeadRecord) for s in rows]
    contact = [lead for lead in leads if lead.has_contact_channel()]
    intel = [lead for lead in leads if not lead.has_contact_channel()]
    return contact, intel


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signals", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "signals.jsonl"))
    ap.add_argument("--approvals-dir", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "ideal_apis", "data", "approvals"))
    ap.add_argument("--all", action="store_true",
                    help="include signals that did not qualify")
    ap.add_argument("--write", action="store_true",
                    help="actually create the approval batch (default: dry run)")
    args = ap.parse_args(argv)

    with open(args.signals) as fh:
        signals = [json.loads(line) for line in fh if line.strip()]

    contact, intel = build(signals, qualified_only=not args.all)

    print(f"{len(signals)} signals read from {args.signals}")
    print(f"  {len(contact)} contactable -> JobTread-eligible")
    print(f"  {len(intel)} intel (no public contact channel in the source)")
    print(f"  priorities: {dict(Counter(l.priority for l in contact + intel))}")
    print()
    for lead in sorted(contact + intel, key=lambda l: l.name)[:40]:
        channel = lead.phone or lead.email or "—"
        print(f"  [{lead.priority:<6}] {lead.name[:42]:<42} {channel:<16} "
              f"{(lead.street or '')[:34]}")

    if not args.write:
        print("\nDRY RUN — nothing written. Re-run with --write to create the batch.")
        return 0

    _ensure_ideal_apis()
    from ideal_apis.pipeline.approvals import ApprovalBatch  # noqa: PLC0415
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-bidradar")
    batch = ApprovalBatch.create(
        Path(args.approvals_dir), stamp, contact, intel,
        meta={"source": "bid_radar", "signals_file": args.signals,
              "qualified_only": not args.all},
    )
    print(f"\nwrote {batch.path}")
    print("Next: ideal-api leads status --show-leads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
