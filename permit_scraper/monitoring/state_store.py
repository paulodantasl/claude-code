"""
Persistent state for the monitor.

Intentionally dependency-free (stdlib JSON only) so the monitor can be dropped
onto any box — a laptop, a cron host, a Raspberry Pi in the trailer — without a
database server. Two artefacts are written next to each other:

  <state_file>            — JSON map of permit_key → last-known Snapshot
  <state_file>.events.jsonl — append-only log of every StatusEvent detected

The snapshot map is what the differ compares against run-over-run. The event log
is an audit trail of every change and every notification attempt.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Iterable

from .models import Snapshot, StatusEvent

logger = logging.getLogger(__name__)


class JsonStateStore:
    """File-backed snapshot store + JSONL event log."""

    def __init__(self, path: str | Path = "permit_monitor_state.json"):
        self.path = Path(path)
        self.events_path = Path(str(self.path) + ".events.jsonl")
        self._snapshots: dict[str, Snapshot] = {}
        self._loaded = False

    # ── Snapshots ───────────────────────────────────────────────────────────

    def load(self) -> None:
        self._snapshots = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for key, snap in data.get("snapshots", {}).items():
                    self._snapshots[key] = Snapshot.from_dict(snap)
            except (json.JSONDecodeError, OSError, KeyError) as exc:
                logger.error("Could not read state file %s: %s", self.path, exc)
        self._loaded = True

    def get(self, permit_key: str) -> Snapshot | None:
        if not self._loaded:
            self.load()
        return self._snapshots.get(permit_key)

    def put(self, snapshot: Snapshot) -> None:
        if not self._loaded:
            self.load()
        self._snapshots[snapshot.permit_key] = snapshot

    def all_snapshots(self) -> dict[str, Snapshot]:
        if not self._loaded:
            self.load()
        return dict(self._snapshots)

    def save(self) -> None:
        """Atomically persist snapshots (write-temp-then-rename)."""
        payload = {
            "version": 1,
            "snapshots": {k: s.to_dict() for k, s in self._snapshots.items()},
        }
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

    # ── Event log ───────────────────────────────────────────────────────────

    def append_event(self, event: StatusEvent) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def read_events(self) -> Iterable[dict]:
        if not self.events_path.exists():
            return []
        out = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out
