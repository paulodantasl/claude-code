"""
Load and validate the monitoring configuration:

  targets/tracked_permits.yaml   — the permits/projects to watch
  targets/field_managers.yaml    — the field managers who get notified
  targets/counties.yaml          — portal configs (reused from the scraper)

The three are joined so each :class:`TrackedPermit` knows its managers and each
county reference resolves to a real portal config.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import FieldManager, TrackedPermit

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "targets"

VALID_CATEGORIES = {"residential", "commercial", "industrial", None}


@dataclass
class MonitorConfig:
    """Fully resolved monitoring configuration."""

    tracked: list[TrackedPermit]
    managers: dict[str, FieldManager]
    counties: dict[str, dict[str, Any]]
    warnings: list[str] = field(default_factory=list)

    def managers_for(self, permit: TrackedPermit) -> list[FieldManager]:
        """Resolve a tracked permit's manager ids to active FieldManager objects."""
        out: list[FieldManager] = []
        for mid in permit.manager_ids:
            mgr = self.managers.get(mid)
            if mgr and mgr.active:
                out.append(mgr)
        return out

    def county_config(self, county_id: str) -> dict[str, Any] | None:
        return self.counties.get(county_id)

    def active_tracked(self) -> list[TrackedPermit]:
        return [t for t in self.tracked if t.active]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        logger.warning("Config file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_managers(path: Path) -> dict[str, FieldManager]:
    data = _load_yaml(path)
    managers: dict[str, FieldManager] = {}
    for raw in data.get("field_managers", []):
        if "id" not in raw:
            logger.warning("Skipping field manager with no id: %r", raw)
            continue
        mgr = FieldManager(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            email=raw.get("email"),
            phone=raw.get("phone"),
            slack_webhook=raw.get("slack_webhook"),
            channels=raw.get("channels") or ["console"],
            active=raw.get("active", True),
        )
        managers[mgr.id] = mgr
    return managers


def load_tracked(path: Path) -> list[TrackedPermit]:
    data = _load_yaml(path)
    tracked: list[TrackedPermit] = []
    for raw in data.get("tracked_permits", []):
        if "permit_number" not in raw or "county" not in raw:
            logger.warning("Skipping tracked permit missing permit_number/county: %r", raw)
            continue
        managers = raw.get("managers") or raw.get("manager_ids") or []
        if isinstance(managers, str):
            managers = [managers]
        tracked.append(
            TrackedPermit(
                permit_number=str(raw["permit_number"]),
                county=str(raw["county"]),
                project_name=raw.get("project_name"),
                address=raw.get("address"),
                category=raw.get("category"),
                manager_ids=list(managers),
                watch_fields=raw.get("watch_fields") or [],
                source_url=raw.get("source_url"),
                active=raw.get("active", True),
                notes=raw.get("notes"),
            )
        )
    return tracked


def load_config(
    config_dir: Path | None = None,
    tracked_file: str | Path = "tracked_permits.yaml",
    managers_file: str | Path = "field_managers.yaml",
    counties_file: str | Path = "counties.yaml",
) -> MonitorConfig:
    """Load, join, and validate the full monitoring configuration."""
    cdir = Path(config_dir) if config_dir else CONFIG_DIR

    def _resolve(name: str | Path) -> Path:
        p = Path(name)
        return p if p.is_absolute() else cdir / p

    managers = load_managers(_resolve(managers_file))
    tracked = load_tracked(_resolve(tracked_file))
    counties_raw = _load_yaml(_resolve(counties_file))
    counties = {c["id"]: c for c in counties_raw.get("targets", []) if "id" in c}

    warnings: list[str] = []
    seen_keys: set[str] = set()
    for t in tracked:
        if t.key in seen_keys:
            warnings.append(f"Duplicate tracked permit key: {t.key}")
        seen_keys.add(t.key)

        if t.county not in counties:
            warnings.append(
                f"{t.permit_number}: county '{t.county}' not in counties.yaml — "
                f"the monitor cannot pick a portal scraper for it."
            )
        if t.category not in VALID_CATEGORIES:
            warnings.append(
                f"{t.permit_number}: unknown category '{t.category}' "
                f"(expected residential/commercial/industrial)."
            )
        if not t.manager_ids:
            warnings.append(f"{t.permit_number}: no field managers assigned — nobody will be notified.")
        for mid in t.manager_ids:
            if mid not in managers:
                warnings.append(f"{t.permit_number}: references unknown field manager '{mid}'.")

    for w in warnings:
        logger.warning("config: %s", w)

    return MonitorConfig(
        tracked=tracked,
        managers=managers,
        counties=counties,
        warnings=warnings,
    )
