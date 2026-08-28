from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.pipeline.models import LeadRecord


class JobTreadClient:
    """Push leads to JobTread Pave API (account + contact + location)."""

    PAVE_URL = "https://api.jobtread.com/pave"

    def __init__(self, grant_key: str | None, org_id: str):
        self.grant_key = grant_key
        self.org_id = org_id

    @classmethod
    def from_env(cls, org_id: str) -> JobTreadClient:
        return cls(os.getenv("JOBTREAD_GRANT_KEY"), org_id)

    def available(self) -> bool:
        return bool(self.grant_key and self.org_id)

    def _query(self, query: dict[str, Any]) -> dict[str, Any]:
        if not self.grant_key:
            raise MissingAPIKeyError("JobTread", "JOBTREAD_GRANT_KEY")
        payload = {"query": {"$": {"grantKey": self.grant_key}, **query}}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(self.PAVE_URL, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"JobTread HTTP {resp.status_code}: {resp.text[:400]}")
        body = resp.json()
        if "errors" in body and body["errors"]:
            raise RuntimeError(f"JobTread errors: {body['errors']}")
        return body

    def account_exists(self, name: str) -> str | None:
        result = self._query({
            "organization": {
                "$": {"id": self.org_id},
                "accounts": {
                    "$": {
                        "where": {"and": [["type", "customer"], ["name", "like", f"%{name[:40]}%"]]},
                        "size": 1,
                    },
                    "nodes": {"id": {}, "name": {}},
                },
            }
        })
        nodes = (
            result.get("organization", {})
            .get("accounts", {})
            .get("nodes", [])
        )
        return nodes[0]["id"] if nodes else None

    def push_lead(self, lead: LeadRecord, *, dry_run: bool = True) -> dict[str, Any]:
        if not lead.has_contact_channel():
            return {"skipped": True, "reason": "no phone or email"}

        if dry_run:
            return {
                "dry_run": True,
                "would_create": {
                    "account": lead.name,
                    "contact": lead.contact_name(),
                    "address": lead.full_address(),
                    "brand": lead.brand,
                },
            }

        existing = self.account_exists(lead.name)
        if existing:
            return {"skipped": True, "reason": "account exists", "account_id": existing}

        created = self._query({
            "createAccount": {
                "$": {
                    "organizationId": self.org_id,
                    "type": "customer",
                    "name": lead.name[:120],
                },
                "createdAccount": {"id": {}, "name": {}},
            }
        })
        account_id = created["createAccount"]["createdAccount"]["id"]

        self._query({
            "createContact": {
                "$": {
                    "accountId": account_id,
                    "name": lead.contact_name()[:120],
                },
                "createdContact": {"id": {}},
            }
        })

        if lead.full_address():
            self._query({
                "createLocation": {
                    "$": {
                        "accountId": account_id,
                        "address": lead.full_address(),
                    },
                    "createdLocation": {"id": {}},
                }
            })

        return {"account_id": account_id, "contact": lead.contact_name()}


def write_jobtread_csv(leads: list[LeadRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "brand", "name", "contact_name", "phone", "email",
                "street", "city", "state", "zip", "source", "priority", "notes", "npi",
            ],
        )
        writer.writeheader()
        for lead in leads:
            if not lead.has_contact_channel():
                continue
            writer.writerow({
                "brand": lead.brand,
                "name": lead.name,
                "contact_name": lead.contact_name(),
                "phone": lead.phone or "",
                "email": lead.email or "",
                "street": lead.street or "",
                "city": lead.city or "",
                "state": lead.state or "",
                "zip": lead.zip_code or "",
                "source": lead.source,
                "priority": lead.priority,
                "notes": lead.notes or "",
                "npi": lead.npi or "",
            })


def write_summary_md(
    path: Path,
    *,
    new_leads: list[LeadRecord],
    intel_leads: list[LeadRecord],
    skipped: int,
    jobtread_results: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Daily leads — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"- **New contactable leads:** {len(new_leads)}",
        f"- **Intel / storm / gov rows:** {len(intel_leads)}",
        f"- **Skipped (dedupe):** {skipped}",
        "",
    ]
    if new_leads:
        lines.append("## New leads (JobTread-ready)")
        for lead in new_leads[:25]:
            contact = lead.phone or lead.email or "—"
            lines.append(f"- **{lead.name}** ({lead.brand}, {lead.source}) — {contact}")
        if len(new_leads) > 25:
            lines.append(f"- … and {len(new_leads) - 25} more in CSV")
        lines.append("")

    if intel_leads:
        lines.append("## Intel")
        for lead in intel_leads[:15]:
            lines.append(f"- {lead.name}: {lead.notes or ''}")
        lines.append("")

    if jobtread_results:
        pushed = [r for r in jobtread_results if r.get("account_id")]
        dry = [r for r in jobtread_results if r.get("dry_run")]
        lines.append("## JobTread")
        lines.append(f"- Pushed: {len(pushed)} | Dry-run: {len(dry)}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_leads_json(path: Path, leads: list[LeadRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([lead.to_dict() for lead in leads], f, indent=2)
