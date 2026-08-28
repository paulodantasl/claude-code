from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class GeoService:
    """Geocoding, routing, and drive-time for jobsites."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def google_geocode(self, address: str) -> dict[str, Any]:
        if not self.settings.google_maps_key:
            raise MissingAPIKeyError("Google Maps", "IDEAL_GOOGLE_MAPS_KEY")
        return self.http.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            service="Google Maps",
            params={"address": address, "key": self.settings.google_maps_key},
        )

    def google_distance_matrix(
        self,
        origins: str,
        destinations: str,
        *,
        mode: str = "driving",
    ) -> dict[str, Any]:
        if not self.settings.google_maps_key:
            raise MissingAPIKeyError("Google Maps", "IDEAL_GOOGLE_MAPS_KEY")
        return self.http.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            service="Google Maps",
            params={
                "origins": origins,
                "destinations": destinations,
                "mode": mode,
                "key": self.settings.google_maps_key,
            },
        )

    def mapbox_geocode(self, query: str, *, limit: int = 1) -> dict[str, Any]:
        if not self.settings.mapbox_key:
            raise MissingAPIKeyError("Mapbox", "IDEAL_MAPBOX_KEY")
        return self.http.get(
            f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json",
            service="Mapbox",
            params={"access_token": self.settings.mapbox_key, "limit": limit},
        )

    def mapbox_directions(
        self,
        profile: str,
        coordinates: list[tuple[float, float]],
    ) -> dict[str, Any]:
        if not self.settings.mapbox_key:
            raise MissingAPIKeyError("Mapbox", "IDEAL_MAPBOX_KEY")
        coord_str = ";".join(f"{lon},{lat}" for lat, lon in coordinates)
        return self.http.get(
            f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{coord_str}",
            service="Mapbox",
            params={
                "access_token": self.settings.mapbox_key,
                "geometries": "geojson",
                "overview": "full",
            },
        )

    def openrouteservice_directions(
        self,
        coordinates: list[tuple[float, float]],
        *,
        profile: str = "driving-car",
    ) -> dict[str, Any]:
        if not self.settings.openrouteservice_key:
            raise MissingAPIKeyError("OpenRouteService", "IDEAL_OPENROUTESERVICE_KEY")
        return self.http.post(
            f"https://api.openrouteservice.org/v2/directions/{profile}",
            service="OpenRouteService",
            json={"coordinates": [[lon, lat] for lat, lon in coordinates]},
            headers={"Authorization": self.settings.openrouteservice_key},
        )

    def openrouteservice_isochrone(
        self,
        lat: float,
        lon: float,
        *,
        minutes: list[int] | None = None,
        profile: str = "driving-car",
    ) -> dict[str, Any]:
        if not self.settings.openrouteservice_key:
            raise MissingAPIKeyError("OpenRouteService", "IDEAL_OPENROUTESERVICE_KEY")
        return self.http.post(
            f"https://api.openrouteservice.org/v2/isochrones/{profile}",
            service="OpenRouteService",
            json={
                "locations": [[lon, lat]],
                "range": minutes or [15, 30, 45],
                "range_type": "time",
            },
            headers={"Authorization": self.settings.openrouteservice_key},
        )
