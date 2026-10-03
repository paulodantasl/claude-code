"""
One module per Tampa source. Each exposes:

    SOURCE      the `Source` literal value it emits
    NAME        a human label for the summary
    collect(days_back) -> list[signal dict]

Signals are the §2.2 schema; `collect.py` scores and writes them.
"""
from __future__ import annotations

from . import (abt, cra_grants, dbpr_hr, entitlements, hcaa_ppo,  # noqa: F401
               permits, sunbiz)

#: The four Tampa ArcGIS layers first — they serve point geometry, so every row
#: lands in a submarket without a geocoder. The state and federal files follow:
#: they carry a street address and nothing else, and `sunbiz` is dormant until
#: credentials exist (see its module docstring).
ALL = [permits, entitlements, abt, cra_grants, dbpr_hr, hcaa_ppo, sunbiz]
