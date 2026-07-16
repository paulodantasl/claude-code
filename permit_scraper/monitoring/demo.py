"""
End-to-end demo / self-test for the permit-monitoring feature.

Runs the full monitor loop against canned portal responses (no browser, no
network, no database) so it works anywhere:

    python -m permit_scraper.monitoring.demo

It proves four things:
  1. First pass establishes a silent baseline (no false alerts on day one).
  2. Second pass detects real status changes and notifies the right managers.
  3. Multi-channel routing (SMS / email / Slack) targets the correct manager.
  4. The shipped example YAML configs load and validate.

Exit code 0 = all assertions passed.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Allow running as a plain script (python permit_scraper/monitoring/demo.py) too.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from permit_scraper.scrapers.base import RawPermit  # noqa: E402
from permit_scraper.monitoring import (  # noqa: E402
    DictFetcher,
    FieldManager,
    FieldManagerNotifier,
    JsonStateStore,
    MonitorConfig,
    PermitMonitor,
    TrackedPermit,
    load_config,
    normalize,
)
from permit_scraper.monitoring.status import Phase  # noqa: E402


COUNTIES = {
    "pasco_county": {"id": "pasco_county", "name": "Pasco County, FL", "type": "accela"},
    "city_orlando": {"id": "city_orlando", "name": "City of Orlando", "type": "cityview"},
}


def _permit(permit_number, county, status, **kw) -> RawPermit:
    cfg = COUNTIES[county]
    return RawPermit(
        source_id=permit_number,
        county_id=county,
        county_name=cfg["name"],
        permit_number=permit_number,
        status=status,
        source_url=f"https://portal.example.gov/permit/{permit_number}",
        **kw,
    )


def _build_config() -> MonitorConfig:
    managers = {
        "msmith": FieldManager(id="msmith", name="Marcus Smith", phone="+18135550122",
                               email="marcus@example.com", channels=["console"]),
        "rlee": FieldManager(id="rlee", name="Rosa Lee", email="rosa@example.com",
                             channels=["console"]),
    }
    tracked = [
        TrackedPermit(
            permit_number="BD-2025-028100", county="pasco_county",
            project_name="Publix — Angeline Town Center",
            address="3400 Angeline Blvd", category="commercial",
            manager_ids=["msmith"],
        ),
        TrackedPermit(
            permit_number="RES-2026-001452", county="city_orlando",
            project_name="Baldwin Park Custom Home — Lot 14",
            address="1420 Meeting Pl", category="residential",
            manager_ids=["rlee"],
        ),
    ]
    return MonitorConfig(tracked=tracked, managers=managers, counties=COUNTIES)


def _run(msg: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    if not ok:
        raise AssertionError(msg)


def scenario_lifecycle() -> None:
    print("\n=== Scenario 1: baseline then detect updates (console delivery) ===")
    config = _build_config()
    state_file = Path(tempfile.mkdtemp()) / "state.json"
    store = JsonStateStore(state_file)
    notifier = FieldManagerNotifier()  # real console delivery

    # ── Pass 1: both permits freshly in review — should baseline silently ──
    fetch1 = DictFetcher({
        "BD-2025-028100": _permit("BD-2025-028100", "pasco_county", "Application Received"),
        "RES-2026-001452": _permit("RES-2026-001452", "city_orlando", "Submitted - Intake"),
    })
    mon1 = PermitMonitor(config=config, store=store, notifier=notifier, fetcher=fetch1)
    s1 = mon1.run_once()
    _run("pass 1 checked both permits", s1["checked"] == 2)
    _run("pass 1 established 2 baselines", s1["baselined"] == 2)
    _run("pass 1 sent no notifications (no false alarms)", s1["notifications_sent"] == 0)

    # ── Pass 2: commercial advances to Plan Review, residential hits corrections ──
    fetch2 = DictFetcher({
        "BD-2025-028100": _permit("BD-2025-028100", "pasco_county", "Plan Review"),
        "RES-2026-001452": _permit("RES-2026-001452", "city_orlando", "Corrections Required"),
    })
    mon2 = PermitMonitor(config=config, store=store, notifier=notifier, fetcher=fetch2)
    s2 = mon2.run_once()
    _run("pass 2 detected 2 updates", s2["updates"] == 2)
    _run("pass 2 sent 2 notifications", s2["notifications_sent"] == 2)

    events = {e["permit_number"]: e for e in s2["events"]}
    _run("commercial permit moved forward (in_review)",
         events["BD-2025-028100"]["new_phase"] == Phase.IN_REVIEW.value
         and events["BD-2025-028100"]["direction"] == "forward")
    _run("residential corrections flagged HIGH priority",
         events["RES-2026-001452"]["priority"] == "high"
         and events["RES-2026-001452"]["new_phase"] == Phase.ACTION_REQUIRED.value)

    # ── Pass 3: no change — must be quiet ──
    mon3 = PermitMonitor(config=config, store=store, notifier=notifier, fetcher=fetch2)
    s3 = mon3.run_once()
    _run("pass 3 with identical data is silent", s3["updates"] == 0 and s3["notifications_sent"] == 0)

    # ── Pass 4: commercial issued — good-news milestone ──
    fetch4 = DictFetcher({
        "BD-2025-028100": _permit("BD-2025-028100", "pasco_county", "Permit Issued",
                                  issued_date="2026-07-16"),
        "RES-2026-001452": _permit("RES-2026-001452", "city_orlando", "Corrections Required"),
    })
    mon4 = PermitMonitor(config=config, store=store, notifier=notifier, fetcher=fetch4)
    s4 = mon4.run_once()
    _run("pass 4 detected the issuance (1 update)", s4["updates"] == 1)
    issued = [e for e in s4["events"] if e["permit_number"] == "BD-2025-028100"][0]
    _run("issuance normalised to 'issued' phase", issued["new_phase"] == Phase.ISSUED.value)
    _run("issued_date change captured",
         any(c["field"] == "issued_date" for c in issued["changes"]))

    # Event log persisted to disk
    logged = list(store.read_events())
    _run("event log persisted every update+baseline", len(logged) >= 5)


def scenario_multichannel_routing() -> None:
    print("\n=== Scenario 2: multi-channel routing to the right manager (dry-run) ===")
    managers = {
        "field1": FieldManager(id="field1", name="Field One", phone="+13055550111",
                               email="f1@example.com", channels=["sms", "email"]),
        "field2": FieldManager(id="field2", name="Field Two",
                               slack_webhook="https://hooks.slack.com/services/X/Y/Z",
                               channels=["slack"]),
    }
    tracked = [
        TrackedPermit(permit_number="BC-2026-004810", county="pasco_county",
                      project_name="Amazon DTA5", category="commercial",
                      manager_ids=["field1", "field2"]),
    ]
    config = MonitorConfig(tracked=tracked, managers=managers, counties=COUNTIES)
    store = JsonStateStore(Path(tempfile.mkdtemp()) / "state.json")
    notifier = FieldManagerNotifier(dry_run=True)  # capture, don't send

    base = DictFetcher({"BC-2026-004810": _permit("BC-2026-004810", "pasco_county", "Plan Review")})
    PermitMonitor(config=config, store=store, notifier=notifier, fetcher=base).run_once()

    changed = DictFetcher({"BC-2026-004810": _permit("BC-2026-004810", "pasco_county", "Denied")})
    PermitMonitor(config=config, store=store, notifier=notifier, fetcher=changed).run_once()

    caps = notifier.captured
    channels = {(c["manager"], c["channel"]) for c in caps}
    _run("field1 got SMS", ("field1", "sms") in channels)
    _run("field1 got email", ("field1", "email") in channels)
    _run("field2 got Slack", ("field2", "slack") in channels)
    _run("field2 was NOT texted (channel routing respected)", ("field2", "sms") not in channels)
    sms_preview = next(c["preview"] for c in caps if c["channel"] == "sms")
    _run("SMS body marks ACTION REQUIRED for denial", "ACTION REQUIRED" in sms_preview)
    _run("SMS body names the permit", "BC-2026-004810" in sms_preview)


def scenario_normalization() -> None:
    print("\n=== Scenario 3: status normalisation across portal dialects ===")
    cases = {
        "Application Received": Phase.SUBMITTED,
        "In Plan Review": Phase.IN_REVIEW,
        "Corrections Required": Phase.ACTION_REQUIRED,
        "On Hold - Awaiting Applicant": Phase.ACTION_REQUIRED,
        "Ready to Issue": Phase.APPROVED,
        "Permit Issued": Phase.ISSUED,
        "Final Inspection Scheduled": Phase.INSPECTIONS,
        "Certificate of Occupancy Issued": Phase.FINALED,
        "Application Denied": Phase.DENIED,
        "Permit Expired": Phase.EXPIRED,
        "Withdrawn by Applicant": Phase.WITHDRAWN,
    }
    for raw, expected in cases.items():
        _run(f"'{raw}' → {expected.value}", normalize(raw) == expected)


def scenario_shipped_config() -> None:
    print("\n=== Scenario 4: shipped example YAML configs load & validate ===")
    cfg = load_config()  # reads permit_scraper/targets/*.yaml
    _run("tracked_permits.yaml loaded", len(cfg.tracked) >= 1)
    _run("field_managers.yaml loaded", len(cfg.managers) >= 1)
    _run("every tracked permit resolves its county",
         all(cfg.county_config(t.county) is not None for t in cfg.tracked))
    _run("every tracked permit has at least one resolvable manager",
         all(cfg.managers_for(t) for t in cfg.tracked))


def main() -> int:
    print("Permit-monitoring end-to-end demo (no browser / network / DB)")
    try:
        scenario_lifecycle()
        scenario_multichannel_routing()
        scenario_normalization()
        scenario_shipped_config()
    except AssertionError as exc:
        print(f"\n✗ DEMO FAILED: {exc}")
        return 1
    print("\n✓ All monitoring scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
