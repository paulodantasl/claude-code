from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ideal_apis.pipeline.approvals import ApprovalBatch
from ideal_apis.pipeline.jobtread_export import JobTreadClient
from ideal_apis.pipeline.ledger import LeadLedger
from ideal_apis.pipeline.models import LeadRecord


def apply_jobtread(
    batch: ApprovalBatch,
    *,
    org_id: str,
    ledger: LeadLedger,
    dry_run: bool = True,
) -> dict[str, Any]:
    client = JobTreadClient.from_env(org_id)
    results: list[dict[str, Any]] = []

    for item in batch.approved_jobtread():
        lead = LeadRecord(**{
            k: v for k, v in item["lead"].items()
            if k in LeadRecord.__dataclass_fields__
        })
        idx = item["index"]

        if ledger.is_jobtread_pushed(lead.dedupe_key()):
            results.append({"index": idx, "skipped": True, "reason": "already in ledger"})
            batch.mark_pushed_jobtread(idx, item.get("jobtread_account_id", "existing"))
            continue

        if dry_run or not client.available():
            results.append({
                "index": idx,
                "dry_run": True,
                "name": lead.name,
                "contact": lead.contact_name(),
                "address": lead.full_address(),
            })
            continue

        result = client.push_lead(lead, dry_run=False)
        result["index"] = idx
        results.append(result)
        if result.get("account_id"):
            ledger.mark_jobtread(lead.dedupe_key(), result["account_id"])
            batch.mark_pushed_jobtread(idx, result["account_id"])

    if not dry_run:
        ledger.save()

    return {
        "batch_id": batch.batch_id,
        "dry_run": dry_run,
        "jobtread_available": client.available(),
        "processed": len(results),
        "pushed": sum(1 for r in results if r.get("account_id")),
        "results": results,
    }


def build_quo_queue(
    batch: ApprovalBatch,
    *,
    from_number: str = "(813) 694-5439",
    ledger: LeadLedger | None = None,
) -> dict[str, Any]:
    """Build QUO text queue — does NOT send; Paulo approves and sends manually or via OpenPhone."""
    messages = []
    skipped: list[dict[str, Any]] = []
    for item in batch.items():
        if item["stage"] != "approved_quo":
            continue
        lead = item["lead"]
        phone = lead.get("phone")
        if not phone:
            continue
        if ledger and ledger.is_quo_texted(phone):
            skipped.append({"index": item["index"], "phone": phone, "reason": "already texted"})
            continue
        brand = lead.get("brand", "ideal_dental")
        if brand == "ideal_dental":
            intro = "Ideal Dental Construction"
        elif brand == "ideal_remodeling":
            intro = "The Ideal Remodeling"
        else:
            intro = "Ideal CGC"
        messages.append({
            "index": item["index"],
            "to": phone,
            "from": from_number,
            "lead_name": lead.get("name"),
            "body": (
                f"Hi, this is {intro}. We specialize in dental office buildouts in Tampa Bay. "
                f"Are you planning any construction or expansion this year? Reply STOP to opt out."
            ),
        })
    return {
        "batch_id": batch.batch_id,
        "count": len(messages),
        "skipped": skipped,
        "messages": messages,
    }


def write_quo_queue(
    batch: ApprovalBatch,
    output_dir: Path,
    *,
    ledger: LeadLedger | None = None,
) -> tuple[Path, dict[str, Any]]:
    queue = build_quo_queue(batch, ledger=ledger)
    path = output_dir / f"quo_queue_{batch.batch_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    if queue["messages"]:
        batch.mark_queued_quo([m["index"] for m in queue["messages"]])
    return path, queue
