"""Load and resolve monitor configurations."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

MONITORS_DIR = Path(__file__).parent / "monitors"


def list_monitors() -> list[str]:
    return sorted(p.stem for p in MONITORS_DIR.glob("*.yaml"))


def load_monitor(monitor_id: str) -> dict:
    path = MONITORS_DIR / f"{monitor_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Monitor '{monitor_id}' not found. Available: {', '.join(list_monitors())}"
        )
    with open(path) as f:
        config = yaml.safe_load(f)
    config = _normalize_route(config)
    config["season"] = resolve_season(config["season"])
    return config


def _normalize_route(config: dict) -> dict:
    route = config.get("route", {})
    if "destination" in route and "destinations" not in route:
        dest = route.pop("destination")
        route["destinations"] = [dest]
    config["route"] = route
    return config


def resolve_season(season: dict) -> dict:
    if season.get("mode") != "rolling":
        return season
    today = date.today()
    dep_start = today + timedelta(days=int(season.get("days_ahead_min", 45)))
    latest_return = today + timedelta(days=int(season.get("days_ahead_max", 270)))
    return {
        **season,
        "departure_start": dep_start.isoformat(),
        "latest_return": latest_return.isoformat(),
        "min_stay_days": season.get("min_stay_days", 7),
    }
