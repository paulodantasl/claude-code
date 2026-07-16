"""
Permit-update monitoring.

Tracks a watch-list of *pending* residential and commercial permits on municipal
portals (Accela, Socrata, ArcGIS, …), detects status changes run-over-run, and
sends instant notifications to the assigned field managers.

Public API::

    from permit_scraper.monitoring import PermitMonitor, build_monitor, load_config

    monitor = build_monitor()          # reads targets/*.yaml + env
    summary = monitor.run_once()       # one pass
    monitor.watch(interval_seconds=1800)   # or run continuously
"""
from .config import MonitorConfig, load_config
from .fetchers import DictFetcher, PermitRef, ScraperFetcher
from .models import FieldChange, FieldManager, Snapshot, StatusEvent, TrackedPermit
from .monitor import PermitMonitor, build_monitor
from .notifier import FieldManagerNotifier
from .state_store import JsonStateStore
from .status import Phase, normalize

__all__ = [
    "PermitMonitor",
    "build_monitor",
    "MonitorConfig",
    "load_config",
    "FieldManagerNotifier",
    "JsonStateStore",
    "DictFetcher",
    "ScraperFetcher",
    "PermitRef",
    "TrackedPermit",
    "FieldManager",
    "Snapshot",
    "StatusEvent",
    "FieldChange",
    "Phase",
    "normalize",
]
