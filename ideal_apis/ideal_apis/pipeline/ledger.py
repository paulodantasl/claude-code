from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LeadLedger:
    """Persistent dedupe ledger (leads_ledger.json compatible shape)."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "version": 1,
                "updated_at": None,
                "seen_keys": [],
                "leads": [],
                "jobtread_pushed": [],
                "quo_texted": [],
            }
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def seen(self, dedupe_key: str) -> bool:
        return dedupe_key in self.data.get("seen_keys", [])

    def mark_seen(self, dedupe_key: str, lead: dict[str, Any]) -> None:
        keys = self.data.setdefault("seen_keys", [])
        if dedupe_key not in keys:
            keys.append(dedupe_key)
        leads = self.data.setdefault("leads", [])
        leads.append({**lead, "dedupe_key": dedupe_key, "recorded_at": datetime.now(timezone.utc).isoformat()})

    def mark_jobtread(self, dedupe_key: str, account_id: str) -> None:
        pushed = self.data.setdefault("jobtread_pushed", [])
        pushed.append({
            "dedupe_key": dedupe_key,
            "account_id": account_id,
            "at": datetime.now(timezone.utc).isoformat(),
        })

    def is_jobtread_pushed(self, dedupe_key: str) -> bool:
        return any(p.get("dedupe_key") == dedupe_key for p in self.data.get("jobtread_pushed", []))

    def is_quo_texted(self, phone: str) -> bool:
        digits = "".join(c for c in phone if c.isdigit())[-10:]
        return digits in self.data.get("quo_texted", [])
