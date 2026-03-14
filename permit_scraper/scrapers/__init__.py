from .accela import AccelaApiScraper, AccelaPlaywrightScraper
from .base import BaseScraper, RawPermit
from .opengov import OpenGovScraper
from .socrata_api import SocrataPermitScraper

SCRAPER_REGISTRY = {
    "accela": AccelaPlaywrightScraper,
    "accela_api": AccelaApiScraper,
    "opengov": OpenGovScraper,
    "socrata": SocrataPermitScraper,
}


def get_scraper(county_config: dict) -> BaseScraper:
    """Instantiate the correct scraper for a county config entry."""
    scraper_type = county_config.get("type", "accela")

    # Prefer open-data API when available
    if county_config.get("open_data_type") == "socrata" and county_config.get("open_data_url"):
        return SocrataPermitScraper(county_config)

    cls = SCRAPER_REGISTRY.get(scraper_type)
    if cls is None:
        raise ValueError(f"Unknown scraper type: {scraper_type!r}. Options: {list(SCRAPER_REGISTRY)}")
    return cls(county_config)


__all__ = [
    "BaseScraper",
    "RawPermit",
    "AccelaPlaywrightScraper",
    "AccelaApiScraper",
    "OpenGovScraper",
    "SocrataPermitScraper",
    "SCRAPER_REGISTRY",
    "get_scraper",
]
