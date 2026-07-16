"""
PermitMonitor — the orchestration loop for permit-update monitoring.

For every active tracked permit:

  1. Fetch its current state from the county portal (grouped per county so each
     portal is hit once per run).
  2. Diff against the last-known snapshot on disk.
  3. If a watched field changed, build a StatusEvent, append it to the event
     log, and notify every assigned field manager instantly.
  4. Persist the new snapshot.

Designed to be run on a schedule (cron / systemd timer / launchd / the built-in
``--watch`` loop). Idempotent: a change is notified exactly once because the
snapshot advances after each detection.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .config import MonitorConfig, load_config
from .differ import build_event, diff_snapshots, snapshot_from_permit
from .fetchers import Fetcher, PermitRef, ScraperFetcher
from .models import TrackedPermit, utcnow_iso
from .notifier import FieldManagerNotifier
from .state_store import JsonStateStore

logger = logging.getLogger(__name__)


class PermitMonitor:
    """Detect and notify status updates on a watch-list of pending permits."""

    def __init__(
        self,
        config: MonitorConfig | None = None,
        store: JsonStateStore | None = None,
        notifier: FieldManagerNotifier | None = None,
        fetcher: Fetcher | None = None,
        notify_on_first_seen: bool = False,
        advance_snapshot_on_notify_failure: bool = True,
    ):
        self.config = config or load_config()
        self.store = store or JsonStateStore()
        self.notifier = notifier or FieldManagerNotifier()
        self.fetcher = fetcher or ScraperFetcher()
        self.notify_on_first_seen = notify_on_first_seen
        self.advance_snapshot_on_notify_failure = advance_snapshot_on_notify_failure

    # ── One pass ────────────────────────────────────────────────────────────

    def run_once(self) -> dict[str, Any]:
        """Run a single monitoring pass over all active tracked permits."""
        self.store.load()
        tracked = self.config.active_tracked()

        summary: dict[str, Any] = {
            "checked": 0,
            "found": 0,
            "missing": 0,
            "baselined": 0,
            "updates": 0,
            "notifications_sent": 0,
            "notification_failures": 0,
            "events": [],
            "errors": [],
        }

        # Group by county so each portal is fetched once.
        by_county: dict[str, list[TrackedPermit]] = defaultdict(list)
        for t in tracked:
            by_county[t.county].append(t)

        for county_id, permits in by_county.items():
            county_cfg = self.config.county_config(county_id)
            county_name = (county_cfg or {}).get("name", county_id)
            if county_cfg is None:
                msg = f"county '{county_id}' not configured — skipping {len(permits)} permit(s)"
                logger.error(msg)
                summary["errors"].append(msg)
                continue

            refs = [PermitRef(p.permit_number, p.address) for p in permits]
            try:
                current_states = self.fetcher.fetch(county_cfg, refs)
            except Exception as exc:
                msg = f"fetch failed for county {county_id}: {exc}"
                logger.error(msg)
                summary["errors"].append(msg)
                current_states = {r.permit_number: None for r in refs}

            for permit in permits:
                summary["checked"] += 1
                raw = current_states.get(permit.permit_number)
                if raw is None:
                    summary["missing"] += 1
                    logger.info("No current record for %s (%s)", permit.permit_number, county_id)
                    continue
                summary["found"] += 1
                self._process_one(permit, county_name, raw, summary)

        self.store.save()
        return summary

    def _process_one(
        self,
        permit: TrackedPermit,
        county_name: str | None,
        raw: Any,
        summary: dict[str, Any],
    ) -> None:
        previous = self.store.get(permit.key)
        current = snapshot_from_permit(permit.key, raw, permit.watch_fields)

        changes = diff_snapshots(previous, current, permit.watch_fields)
        now = utcnow_iso()
        is_first_seen = previous is None

        if not changes:
            # No change — just refresh the last-seen timestamp on the snapshot.
            current.last_seen_at = now
            current.last_changed_at = previous.last_changed_at if previous else now
            self.store.put(current)
            return

        # A watched field changed. Decide whether it's a notifiable update or a
        # silent first-seen baseline.
        should_notify = not is_first_seen or self.notify_on_first_seen
        event = build_event(permit, county_name, previous, current, changes)

        if should_notify:
            summary["updates"] += 1
            managers = self.config.managers_for(permit)
            results = self.notifier.notify(event, managers)
            summary["notifications_sent"] += sum(1 for r in results if r.get("ok"))
            summary["notification_failures"] += sum(1 for r in results if not r.get("ok"))
        else:
            summary["baselined"] += 1
            logger.info("Baseline established for %s (no alert)", permit.permit_number)

        self.store.append_event(event)
        summary["events"].append(event.to_dict())

        # If every channel failed and we're configured to retry, hold the
        # snapshot back so the next pass re-detects and re-notifies.
        notify_failed = should_notify and bool(event.notify_results) and not event.notified
        if notify_failed and not self.advance_snapshot_on_notify_failure:
            logger.warning(
                "Holding snapshot for %s — all channels failed, will retry next pass",
                permit.permit_number,
            )
            if previous is not None:
                previous.last_seen_at = now
                self.store.put(previous)
            return

        current.last_seen_at = now
        current.last_changed_at = now
        self.store.put(current)

    # ── Continuous watch ────────────────────────────────────────────────────

    def watch(self, interval_seconds: int, max_iterations: int | None = None) -> None:
        """Run ``run_once`` forever on an interval (Ctrl-C to stop)."""
        iteration = 0
        while True:
            iteration += 1
            logger.info("── monitor pass %d ──", iteration)
            try:
                summary = self.run_once()
                logger.info(
                    "pass %d: checked=%d updates=%d sent=%d failed=%d missing=%d",
                    iteration,
                    summary["checked"], summary["updates"],
                    summary["notifications_sent"], summary["notification_failures"],
                    summary["missing"],
                )
            except Exception as exc:  # never let the loop die on one bad pass
                logger.error("monitor pass %d crashed: %s", iteration, exc, exc_info=True)

            if max_iterations is not None and iteration >= max_iterations:
                return
            time.sleep(interval_seconds)


def build_monitor(
    config_dir: str | Path | None = None,
    state_file: str | Path = "permit_monitor_state.json",
    dry_run: bool = False,
    notify_on_first_seen: bool = False,
    notifier_config: dict[str, Any] | None = None,
    fetcher: Fetcher | None = None,
    lookback_days: int = 180,
) -> PermitMonitor:
    """Convenience factory wiring config + store + notifier from disk/env."""
    # Best-effort: load .env so cron / systemd runs pick up notification creds.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # python-dotenv optional / absent
        pass

    config = load_config(config_dir=Path(config_dir) if config_dir else None)
    store = JsonStateStore(state_file)
    notifier = FieldManagerNotifier(config=notifier_config or {}, dry_run=dry_run)
    return PermitMonitor(
        config=config,
        store=store,
        notifier=notifier,
        fetcher=fetcher or ScraperFetcher(lookback_days=lookback_days),
        notify_on_first_seen=notify_on_first_seen,
    )
