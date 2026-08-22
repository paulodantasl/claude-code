#!/usr/bin/env python3
"""Create a GitHub issue when a flight monitor alert fires."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    result_path = Path(sys.argv[1])
    data = json.loads(result_path.read_text())
    if not data.get("alert_triggered"):
        return 0

    best = data.get("best_this_run") or data.get("all_time_best") or {}
    monitor = data.get("monitor_name") or data.get("monitor_id", "Flight")
    price = best.get("total_price_usd", 0)

    body = f"""## {monitor} — price alert

**{data.get('alert_reason', 'Deal detected')}**

| Field | Value |
|-------|-------|
| Price | ${price:,.2f} {best.get('currency', 'USD')} |
| Route | {best.get('origin', '?')} → {best.get('destination', '?')} |
| Dates | {best.get('departure_date', '?')} – {best.get('return_date', '?')} |
| Stay | {best.get('stay_days', '?')} nights |
| Airline | {best.get('airline', '?')} |
| Stops | {best.get('stops', '?')} |

[Search on Google Flights]({best.get('booking_link', 'https://www.google.com/travel/flights')})

Notify: {', '.join(data.get('notify_emails') or [])}

_Automated flight monitor._
"""
    label = "flight-alert-europe" if data.get("monitor_id") == "europe" else "flight-alert"
    subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--title",
            f"✈️ {monitor}: ${price:,.0f}",
            "--body",
            body,
            "--label",
            label,
        ],
        check=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
