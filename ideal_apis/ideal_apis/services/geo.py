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

    def census_geocode(self, address: str) -> dict[str, Any]:
        """Free, keyless, unlimited US geocoding — the default for bulk work.

        Google, Mapbox, and Smarty all bill per lookup, so geocoding a scraped
        PlanHub list or a county permit dump through them scales the bill with row
        count. The Census geocoder is authoritative for US street addresses and free.
        Reserve the paid providers for single-address paths where deliverability and
        suite-level accuracy actually matter.
        """
        params: dict[str, Any] = {
            "address": address,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }
        if self.settings.census_key:
            params["key"] = self.settings.census_key
        return self.http.get(
            "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
            service="Census.gov",
            params=params,
        )

    def batch_geocode(self, addresses: list[str]) -> list[dict[str, Any]]:
        """Geocode a list of addresses through the free Census geocoder.

        One address that fails to match does not stop the batch — it comes back with
        ``matched: False`` so the rest of the list stays usable.
        """
        results: list[dict[str, Any]] = []
        for address in addresses:
            entry: dict[str, Any] = {"input": address, "matched": False}
            try:
                payload = self.census_geocode(address)
                matches = (payload.get("result") or {}).get("addressMatches") or []
                if matches:
                    best = matches[0]
                    coords = best.get("coordinates") or {}
                    entry.update(
                        matched=True,
                        matched_address=best.get("matchedAddress"),
                        lat=coords.get("y"),
                        lon=coords.get("x"),
                    )
            except Exception as exc:
                entry["error"] = str(exc)
            results.append(entry)
        return results

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
