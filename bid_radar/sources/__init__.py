"""
One module per Tampa source. Each exposes:

    SOURCE      the `Source` literal value it emits
    NAME        a human label for the summary
    collect(days_back) -> list[signal dict]

Signals are the §2.2 schema; `collect.py` scores and writes them.
"""
from __future__ import annotations

from . import abt, cra_grants, entitlements, permits  # noqa: F401

ALL = [permits, entitlements, abt, cra_grants]
