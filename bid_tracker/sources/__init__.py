from .base import BaseSource, RawDocument, RawOpportunity
from .portal_agent import PortalAgentSource
from .rss import RssSource
from .sam_gov import SamGovSource

SOURCE_REGISTRY = {
    "sam_gov": SamGovSource,
    "rss": RssSource,
    "ai": PortalAgentSource,
}


def get_source(source_config: dict) -> BaseSource:
    """Instantiate the correct source adapter for a sources.yaml entry."""
    source_type = source_config.get("type", "rss")
    cls = SOURCE_REGISTRY.get(source_type)
    if cls is None:
        raise ValueError(
            f"Unknown source type: {source_type!r}. Options: {list(SOURCE_REGISTRY)}"
        )
    return cls(source_config)


__all__ = [
    "BaseSource",
    "RawDocument",
    "RawOpportunity",
    "SamGovSource",
    "RssSource",
    "PortalAgentSource",
    "SOURCE_REGISTRY",
    "get_source",
]
