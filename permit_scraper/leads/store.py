"""
Dedupe store for issued-permit leads.

Remembers which permits have already been surfaced as leads so each run only
emits *new* ones. Dependency-free JSON (+ a JSONL history log), same philosophy
as the monitoring state store — no database required.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path

from .models import Lead

logger = logging.getLogger(__name__)


class LeadStore:
    """File-backed set of already-seen lead ids + a JSONL lead history."""

    def __init__(self, path: str | Path = "permit_leads_state.json"):
        self.path = Path(path)
        self.history_path = Path(str(self.path) + ".leads.jsonl")
        self._seen: dict[str, str] = {}   # lead_id -> first_seen iso
        self._loaded = False

    def load(self) -> None:
        self._seen = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._seen = dict(data.get("seen", {}))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Could not read lead store %s: %s", self.path, exc)
        self._loaded = True

    def is_new(self, lead_id: str) -> bool:
        if not self._loaded:
            self.load()
        return lead_id not in self._seen

    def add(self, lead: Lead) -> None:
        if not self._loaded:
            self.load()
        self._seen[lead.lead_id] = lead.first_seen
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(lead.to_dict()) + "\n")

    def save(self) -> None:
        payload = {"version": 1, "seen": self._seen}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    def count(self) -> int:
        if not self._loaded:
            self.load()
        return len(self._seen)
