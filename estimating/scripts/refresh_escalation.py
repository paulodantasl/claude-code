#!/usr/bin/env python3
"""Refresh the committed material-escalation snapshot from FRED.

Usage:
    python3 estimating/scripts/refresh_escalation.py [--months 12] [--out PATH]
                                                     [--json] [--alert-pct 6.0]

The estimate validator reads the snapshot this writes, so a bid gets checked
against a current, cited index without anyone remembering a flag, holding a FRED
key, or being online at validation time. That is the whole point of separating
the fetch from the check: the fetch runs on a schedule where a key and network
exist, the check runs anywhere.

Writes JSON to estimating/data/escalation.json by default. Exits 0 on success
(including "nothing moved"), 1 only when no series could be read at all — a
partial read still writes a usable snapshot.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "escalation.json"

# Annualized percent move that is worth waking someone up for. Materials moving
# faster than this outrun a typical carried contingency over a normal bid hold.
DEFAULT_ALERT_PCT = 6.0

# Series that actually drive a GC's cost exposure. The rest of the curated set is
# still captured in the snapshot; these are the ones an alert fires on.
ALERT_SERIES = {"construction_materials", "lumber_wood", "iron_steel"}


def build_snapshot(months: int) -> dict:
    """Read every curated series and shape the snapshot the validator consumes."""
    from ideal_apis import IdealAPIs

    api = IdealAPIs()
    exposure = api.market.bid_exposure(months=months)
    series = exposure.get("series", {})
    ok = {k: v for k, v in series.items() if not v.get("error")}
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "FRED (Federal Reserve Bank of St. Louis)",
        "months": months,
        "series_read": len(ok),
        "series_total": len(series),
        "series": series,
    }


def alerts(snapshot: dict, alert_pct: float) -> list[dict]:
    """Series moving fast enough to warrant a look at carried contingency."""
    found = []
    for name, esc in snapshot.get("series", {}).items():
        if name not in ALERT_SERIES or esc.get("error"):
            continue
        annualized = esc.get("annualized_pct")
        if annualized is not None and annualized >= alert_pct:
            found.append({
                "name": name,
                "series": esc.get("series"),
                "annualized_pct": annualized,
                "pct_change": esc.get("pct_change"),
                "start": esc.get("start"),
                "end": esc.get("end"),
            })
    return sorted(found, key=lambda a: a["annualized_pct"], reverse=True)


def render_report(snapshot: dict, fired: list[dict], alert_pct: float) -> str:
    lines = [
        "## Material escalation snapshot",
        "",
        f"Read {snapshot['series_read']} of {snapshot['series_total']} series "
        f"over a {snapshot['months']}-month window at {snapshot['generated_at']}.",
        "",
        "| Series | ID | Window move | Annualized | Latest |",
        "|---|---|---|---|---|",
    ]
    for name, esc in sorted(snapshot.get("series", {}).items()):
        pct, annualized = esc.get("pct_change"), esc.get("annualized_pct")
        if esc.get("error") or pct is None or annualized is None:
            reason = esc.get("error", "no usable observations")
            lines.append(f"| {name} | {esc.get('series', '?')} | — | — | {reason[:60]} |")
            continue
        end = esc.get("end") or {}
        lines.append(
            f"| {name} | {esc.get('series')} | {pct:+.1f}% | "
            f"{annualized:+.1f}%/yr | {end.get('date')} {end.get('value')} |"
        )
    lines.append("")
    if fired:
        lines.append(f"**{len(fired)} series above the {alert_pct:.1f}%/yr alert threshold.** "
                     "Re-check the contingency carried on open bids, or shorten bid validity.")
    else:
        lines.append(f"No series above the {alert_pct:.1f}%/yr alert threshold.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12,
                    help="trailing window for each series (default 12)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="snapshot path")
    ap.add_argument("--alert-pct", type=float, default=DEFAULT_ALERT_PCT,
                    help="annualized %% move that fires an alert (default 6.0)")
    ap.add_argument("--json", action="store_true",
                    help="print the machine-readable result to stdout instead of a report")
    args = ap.parse_args()

    try:
        snapshot = build_snapshot(args.months)
    except ImportError:
        print("ideal_apis not installed — run 'pip install -e ideal_apis'", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"could not read FRED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if not snapshot["series_read"]:
        errors = {k: v.get("error") for k, v in snapshot["series"].items()}
        print(f"no series could be read — snapshot not written: {errors}", file=sys.stderr)
        return 1

    fired = alerts(snapshot, args.alert_pct)
    snapshot["alert_pct"] = args.alert_pct
    snapshot["alerts"] = fired

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")

    if args.json:
        print(json.dumps({
            "path": str(out),
            "generated_at": snapshot["generated_at"],
            "series_read": snapshot["series_read"],
            "series_total": snapshot["series_total"],
            "alert_triggered": bool(fired),
            "alerts": fired,
        }, indent=2))
    else:
        print(render_report(snapshot, fired, args.alert_pct))
    return 0


if __name__ == "__main__":
    sys.exit(main())
