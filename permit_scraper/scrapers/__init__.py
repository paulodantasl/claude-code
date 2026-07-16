"""Scraper registry with lazy imports.

Importing this package is cheap. The heavy browser-based scrapers (which pull in
Playwright) are imported only when a scraper of that type is actually
instantiated. This lets lightweight consumers — the monitoring core, tests,
tooling — import ``RawPermit`` / ``BaseScraper`` without requiring Playwright to
be installed.
"""
from __future__ import annotations

import importlib

from .base import BaseScraper, RawPermit

# scraper type -> (relative module, class name), imported on demand.
_SCRAPER_SPECS: dict[str, tuple[str, str]] = {
    "accela": (".accela", "AccelaPlaywrightScraper"),
    "accela_api": (".accela", "AccelaApiScraper"),
    "arcgis": (".arcgis_api", "ArcGISPermitScraper"),
    "cityview": (".cityview", "CityViewScraper"),
    "energov": (".energov", "EnerGovScraper"),
    "opengov": (".opengov", "OpenGovScraper"),
    "socrata": (".socrata_api", "SocrataPermitScraper"),
}


def _load(spec: tuple[str, str]):
    module = importlib.import_module(spec[0], __name__)
    return getattr(module, spec[1])


def get_scraper(county_config: dict) -> BaseScraper:
    """Instantiate the correct scraper for a county config entry."""
    scraper_type = county_config.get("type", "accela")

    # Prefer open-data API when available.
    if county_config.get("open_data_type") == "socrata" and county_config.get("open_data_url"):
        return _load(_SCRAPER_SPECS["socrata"])(county_config)

    spec = _SCRAPER_SPECS.get(scraper_type)
    if spec is None:
        raise ValueError(
            f"Unknown scraper type: {scraper_type!r}. Options: {list(_SCRAPER_SPECS)}"
        )
    return _load(spec)(county_config)


def __getattr__(name: str):
    """PEP 562 lazy attribute access for scraper classes and the registry."""
    if name == "SCRAPER_REGISTRY":
        return {t: _load(spec) for t, spec in _SCRAPER_SPECS.items()}
    for spec in _SCRAPER_SPECS.values():
        if spec[1] == name:
            return _load(spec)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseScraper",
    "RawPermit",
    "AccelaPlaywrightScraper",
    "AccelaApiScraper",
    "ArcGISPermitScraper",
    "CityViewScraper",
    "EnerGovScraper",
    "OpenGovScraper",
    "SocrataPermitScraper",
    "SCRAPER_REGISTRY",
    "get_scraper",
]
