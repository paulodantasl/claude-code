from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ideal_apis.pipeline.models import LeadRecord

ApprovalStage = Literal[
    "pending",
    "approved_jobtread",
    "rejected",
    "pushed_jobtread",
    "approved_quo",
    "skipped_quo",
    "queued_quo",
]


class ApprovalBatch:
    """Sequential approval state for one daily collect run."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = self._load()

    @classmethod
    def create(
        cls,
        approvals_dir: Path,
        batch_id: str,
        contact_leads: list[LeadRecord],
        intel_leads: list[LeadRecord],
        *,
        meta: dict[str, Any] | None = None,
    ) -> ApprovalBatch:
        approvals_dir.mkdir(parents=True, exist_ok=True)
        path = approvals_dir / f"{batch_id}.json"
        items = []
        for i, lead in enumerate(contact_leads):
            items.append({
                "index": i,
                "lead_id": lead.id,
                "dedupe_key": lead.dedupe_key(),
                "stage": "pending",
                "lead": lead.to_dict(),
            })
        batch = cls(path)
        batch.data = {
            "batch_id": batch_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta": meta or {},
            "contact_leads": items,
            "intel_leads": [lead.to_dict() for lead in intel_leads],
            "history": [],
        }
        batch.save()
        return batch

    @classmethod
    def latest(cls, approvals_dir: Path) -> ApprovalBatch | None:
        if not approvals_dir.exists():
            return None
        files = sorted(approvals_dir.glob("*.json"), reverse=True)
        return cls(files[0]) if files else None

    @classmethod
    def open(cls, approvals_dir: Path, batch_id: str) -> ApprovalBatch:
        path = approvals_dir / f"{batch_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"No approval batch: {batch_id}")
        return cls(path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def _log(self, action: str, detail: str) -> None:
        self.data.setdefault("history", []).append({
            "at": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "detail": detail,
        })

    @property
    def batch_id(self) -> str:
        return self.data["batch_id"]

    def items(self) -> list[dict[str, Any]]:
        return self.data.get("contact_leads", [])

    def pending(self) -> list[dict[str, Any]]:
        return [i for i in self.items() if i["stage"] == "pending"]

    def approved_jobtread(self) -> list[dict[str, Any]]:
        return [i for i in self.items() if i["stage"] == "approved_jobtread"]

    def ready_for_quo(self) -> list[dict[str, Any]]:
        return [
            i for i in self.items()
            if i["stage"] == "pushed_jobtread" and i["lead"].get("phone")
        ]

    def approve(
        self,
        *,
        indices: list[int] | None = None,
        high_only: bool = False,
        all_pending: bool = False,
    ) -> int:
        changed = 0
        for item in self.items():
            if item["stage"] != "pending":
                continue
            lead = item["lead"]
            if all_pending:
                ok = True
            elif indices is not None:
                ok = item["index"] in indices
            elif high_only:
                ok = lead.get("priority") == "high"
            else:
                ok = False
            if ok:
                item["stage"] = "approved_jobtread"
                changed += 1
        if changed:
            self._log("approve_jobtread", f"approved {changed} leads")
            self.save()
        return changed

    def reject(self, indices: list[int]) -> int:
        changed = 0
        for item in self.items():
            if item["index"] in indices and item["stage"] == "pending":
                item["stage"] = "rejected"
                changed += 1
        if changed:
            self._log("reject", f"rejected {changed} leads")
            self.save()
        return changed

    def mark_pushed_jobtread(self, index: int, account_id: str) -> None:
        for item in self.items():
            if item["index"] == index:
                item["stage"] = "pushed_jobtread"
                item["jobtread_account_id"] = account_id
                break
        self._log("pushed_jobtread", f"index={index} account={account_id}")
        self.save()

    def mark_queued_quo(self, indices: list[int]) -> None:
        for item in self.items():
            if item["index"] in indices and item["stage"] == "approved_quo":
                item["stage"] = "queued_quo"
        self._log("queued_quo", f"queued {len(indices)} messages")
        self.save()

    def approve_quo(self, *, indices: list[int] | None = None, all_ready: bool = False) -> int:
        changed = 0
        for item in self.items():
            if item["stage"] != "pushed_jobtread" or not item["lead"].get("phone"):
                continue
            if all_ready or (indices and item["index"] in indices):
                item["stage"] = "approved_quo"
                changed += 1
        if changed:
            self._log("approve_quo", f"approved {changed} for QUO")
            self.save()
        return changed

    def summary(self) -> dict[str, Any]:
        stages: dict[str, int] = {}
        for item in self.items():
            stages[item["stage"]] = stages.get(item["stage"], 0) + 1
        return {
            "batch_id": self.batch_id,
            "path": str(self.path),
            "created_at": self.data.get("created_at"),
            "contact_total": len(self.items()),
            "intel_total": len(self.data.get("intel_leads", [])),
            "stages": stages,
            "next_step": self._next_step(),
        }

    def _next_step(self) -> str:
        if self.pending():
            return "Run: ideal-api leads approve --high-only  (or --all / --indices 0,1,2)"
        if self.approved_jobtread():
            return "Run: ideal-api leads apply jobtread --live  (or ask Cursor agent to push via JobTread MCP)"
        if self.ready_for_quo():
            return "Run: ideal-api leads approve-quo --all  then  ideal-api leads apply quo"
        return "Batch complete"

    def lead_records(self, stage: ApprovalStage | None = None) -> list[LeadRecord]:
        out: list[LeadRecord] = []
        for item in self.items():
            if stage and item["stage"] != stage:
                continue
            d = item["lead"]
            out.append(LeadRecord(**{k: v for k, v in d.items() if k in LeadRecord.__dataclass_fields__}))
        return out
