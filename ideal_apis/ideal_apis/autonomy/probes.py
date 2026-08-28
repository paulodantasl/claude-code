from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ideal_apis.config import get_settings
from ideal_apis.registry import COMMAND_REGISTRY, CommandSpec


def _load_endpoints() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "endpoints.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _settings_has_key(cmd: CommandSpec) -> bool:
    """Return True if required credentials appear configured for this command."""
    s = get_settings()
    key_map: dict[tuple[str, str], bool] = {
        ("address", "validate"): bool(s.smarty_auth_id and s.smarty_auth_token),
        ("address", "autocomplete"): bool(s.smarty_auth_id and s.smarty_auth_token),
        ("leads", "yelp"): bool(s.yelp_key),
        ("weather", "stormglass"): bool(s.stormglass_key),
        ("gov", "fastdol"): bool(s.fastdol_key),
        ("docs", "ocr-url"): bool(s.ocr_space_key),
        ("docs", "pandadoc-templates"): bool(s.pandadoc_key),
        ("docs", "buildpdf"): bool(s.buildpdf_key),
        ("geo", "google-geocode"): bool(s.google_maps_key),
        ("geo", "mapbox-geocode"): bool(s.mapbox_key),
        ("geo", "drive-time"): bool(s.google_maps_key),
        ("geo", "isochrone"): bool(s.openrouteservice_key),
        ("logistics", "track"): bool(s.whereparcel_key),
        ("logistics", "ups-track"): bool(s.ups_client_id and s.ups_client_secret),
        ("property", "opencorporates"): bool(s.opencorporates_key),
        ("property", "schools"): bool(s.districtapi_key),
        ("property", "acrelens"): bool(s.acrelens_key),
        ("productivity", "clockify-workspaces"): bool(s.clockify_key),
        ("productivity", "clockify-projects"): bool(s.clockify_key),
        ("weather", "visual-crossing"): bool(s.visual_crossing_key),
    }
    if (cmd.group, cmd.name) in key_map:
        return key_map[(cmd.group, cmd.name)]
    return not cmd.requires_key


def probe_kwargs_for(cmd: CommandSpec) -> dict[str, Any]:
    """Default arguments for an autonomous live probe of one registry command."""
    cfg = _load_endpoints()
    defaults = cfg.get("probe_defaults", {})
    lat = float(defaults.get("lat", 27.9506))
    lon = float(defaults.get("lon", -82.4572))
    socrata = (cfg.get("socrata_permits") or [{}])[0]

    mapping: dict[tuple[str, str], dict[str, Any]] = {
        ("address", "validate"): {
            "street": "401 E Jackson St",
            "city": "Tampa",
            "state": "FL",
            "zipcode": "33602",
        },
        ("address", "autocomplete"): {"search": "401 E Jackson Tampa"},
        ("validation", "phone"): {"number": defaults.get("test_phone", "8136945439")},
        ("validation", "email"): {"email": defaults.get("test_email", "office@theidealremodeling.com")},
        ("leads", "nppes"): {"state": "FL", "taxonomy": "Dentist", "limit": "2"},
        ("leads", "dentists"): {"limit": "2"},
        ("leads", "yelp"): {"term": "dental office", "location": "Tampa, FL", "limit": "2"},
        ("permits", "socrata"): {
            "endpoint": socrata.get(
                "endpoint",
                "https://data.cityoforlando.net/resource/ryhf-m453.json",
            ),
            "date_column": socrata.get("date_column", "processed_date"),
            "days": "7",
            "limit": "2",
        },
        ("permits", "datagov"): {"query": "building permits Florida", "limit": "3"},
        ("permits", "fl-datasets"): {"county": "Hillsborough"},
        ("permits", "catalog"): {"query": "building permits Florida", "limit": "3"},
        ("weather", "forecast"): {"lat": str(lat), "lon": str(lon)},
        ("weather", "nws"): {"lat": str(lat), "lon": str(lon)},
        ("weather", "alerts"): {"state": "FL", "zone": "FLZ151"},
        ("weather", "hail"): {"lat": str(lat), "lon": str(lon), "days": "14"},
        ("weather", "radar"): {},
        ("weather", "stormglass"): {"lat": "27.77", "lon": "-82.63"},
        ("weather", "visual-crossing"): {"location": "Tampa,FL"},
        ("gov", "usaspending"): {"limit": "2"},
        ("gov", "contracts"): {"state": "FL", "limit": "2"},
        ("gov", "fastdol"): {"company": defaults.get("test_company", "Ideal Construction")},
        ("gov", "census-geocode"): {"address": defaults.get("tampa_address", "401 E Jackson St, Tampa FL")},
        ("gov", "openfema"): {"states": "FL", "days_back": "90", "limit": "3"},
        ("gov", "epa"): {"table": "frs_program_facility/state/FL", "rows": "2"},
        ("web", "microlink"): {"url": defaults.get("test_url", "https://idealcgc.com")},
        ("docs", "ocr-url"): {"url": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/img/table-word.jpg"},
        ("docs", "pandadoc-templates"): {},
        ("docs", "buildpdf"): {"html": "<h1>Ideal Construction</h1><p>Test PDF</p>"},
        ("geo", "google-geocode"): {"address": "Tampa FL"},
        ("geo", "mapbox-geocode"): {"query": "Madeira Beach FL"},
        ("geo", "drive-time"): {"from": "Tampa FL", "to": "St Petersburg FL"},
        ("geo", "isochrone"): {"lat": str(lat), "lon": str(lon), "minutes": "15"},
        ("logistics", "track"): {"number": "1Z999AA10123456784"},
        ("logistics", "ups-track"): {"number": "1Z999AA10123456784"},
        ("property", "opencorporates"): {"query": "Ideal Construction Florida"},
        ("property", "schools"): {"address": "401 E Jackson St Tampa FL"},
        ("property", "acrelens"): {"lat": "27.77", "lon": "-82.63"},
        ("productivity", "clockify-workspaces"): {},
        ("productivity", "clockify-projects"): {"workspace_id": "placeholder"},
    }
    return mapping.get((cmd.group, cmd.name), {})


def all_probe_commands(*, tier: int | None = None) -> list[CommandSpec]:
    cmds = COMMAND_REGISTRY
    if tier is not None:
        cmds = [c for c in cmds if c.tier == tier]
    return list(cmds)
