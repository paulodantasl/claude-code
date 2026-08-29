"""Local dedupe store.

Tracks processed email Message-IDs and claim numbers in a JSON file so
restarts, IMAP flag glitches, forwarded copies, or carrier re-sends never
create duplicate JobTread leads.
"""

import json
import os
from typing import Optional


class State:
    def __init__(self, path: str):
        self.path = path
        self._data = {"message_ids": [], "claims": {}}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def seen_message(self, message_id: str) -> bool:
        return bool(message_id) and message_id in self._data["message_ids"]

    def seen_claim(self, claim_number: Optional[str]) -> bool:
        return bool(claim_number) and claim_number in self._data["claims"]

    def record(self, message_id: str, claim_number: Optional[str], job_id: Optional[str]) -> None:
        if message_id and message_id not in self._data["message_ids"]:
            self._data["message_ids"].append(message_id)
        if claim_number:
            self._data["claims"][claim_number] = job_id or ""
        self._save()

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.path)
