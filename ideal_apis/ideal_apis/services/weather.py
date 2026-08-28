from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class WeatherService:
    """Field scheduling, storm intel, and restoration prospecting."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def nws_points(self, lat: float, lon: float) -> dict[str, Any]:
        return self.http.get(
            f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}",
            service="US Weather",
        )

    def nws_forecast(self, lat: float, lon: float) -> dict[str, Any]:
        points = self.nws_points(lat, lon)
        forecast_url = points["properties"]["forecast"]
        return self.http.get(forecast_url, service="US Weather")

    def job_forecast(self, lat: float, lon: float) -> dict[str, Any]:
        """Forecast for a live job — the commercially licensed default.

        Use this, not :meth:`open_meteo_forecast`, for anything that touches a job.
        NWS is US government work product in the public domain, so it carries no
        licence restriction on commercial use; Open-Meteo's free tier does.
        """
        return self.nws_forecast(lat, lon)

    def nws_alerts(self, *, state: str | None = None, zone: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"status": "actual"}
        if state:
            params["area"] = state
        if zone:
            params["zone"] = zone
        return self.http.get(
            "https://api.weather.gov/alerts/active",
            service="US Weather",
            params=params,
        )

    def open_meteo_forecast(
        self,
        lat: float,
        lon: float,
        *,
        hourly: list[str] | None = None,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        """Open-Meteo forecast — internal and experimental use only.

        Open-Meteo's free tier is licensed for non-commercial use. For scheduling
        real work call :meth:`job_forecast`, which uses NWS, or move this call to an
        Open-Meteo commercial plan.
        """
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "forecast_days": forecast_days,
            "timezone": "America/New_York",
        }
        if hourly:
            params["hourly"] = ",".join(hourly)
        else:
            params["hourly"] = "precipitation_probability,precipitation,weather_code"
            params["daily"] = "precipitation_sum,rain_sum,weather_code"
        return self.http.get(
            "https://api.open-meteo.com/v1/forecast",
            service="Open-Meteo",
            params=params,
        )

    def open_meteo_history(
        self,
        lat: float,
        lon: float,
        start_date: str,
        end_date: str,
        *,
        daily: str = "precipitation_sum,rain_sum,weather_code",
    ) -> dict[str, Any]:
        return self.http.get(
            "https://archive-api.open-meteo.com/v1/archive",
            service="Open-Meteo",
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": daily,
                "timezone": "America/New_York",
            },
        )

    def rainviewer_maps(self) -> dict[str, Any]:
        return self.http.get("https://api.rainviewer.com/public/weather-maps.json", service="RainViewer")

    def noaa_hail(
        self,
        *,
        start: str,
        end: str,
        bbox: tuple[float, float, float, float] | None = None,
        limit: int = 100,
    ) -> Any:
        """NOAA SWDI NEXRAD Level-3 hail signatures (free, keyless)."""
        params: dict[str, Any] = {"limit": limit}
        if bbox:
            west, south, east, north = bbox
            params["bbox"] = f"{west},{south},{east},{north}"
        url = f"https://www.ncei.noaa.gov/swdiws/json/nx3hail/{start}:{end}"
        return self.http.get(url, service="NOAA Hail", params=params)

    def hail_near(
        self,
        lat: float,
        lon: float,
        *,
        days_back: int = 365,
        radius_deg: float = 0.25,
    ) -> Any:
        end = datetime.utcnow()
        start = end - timedelta(days=days_back)
        bbox = (
            lon - radius_deg,
            lat - radius_deg,
            lon + radius_deg,
            lat + radius_deg,
        )
        return self.noaa_hail(
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
            bbox=bbox,
        )

    def air_quality(self, lat: float, lon: float) -> dict[str, Any]:
        """Nearest air quality reading (AQICN).

        Drives dust-control compliance on demolition and site work, and the crew-safety
        call on wildfire-smoke days.
        """
        if not self.settings.aqicn_key:
            raise MissingAPIKeyError("AQICN", "IDEAL_AQICN_KEY")
        return self.http.get(
            f"https://api.waqi.info/feed/geo:{lat};{lon}/",
            service="AQICN",
            params={"token": self.settings.aqicn_key},
        )

    def openaq_nearby(
        self,
        lat: float,
        lon: float,
        *,
        radius_m: int = 25000,
        limit: int = 10,
    ) -> dict[str, Any]:
        """OpenAQ monitoring locations near a job site."""
        if not self.settings.openaq_key:
            raise MissingAPIKeyError("OpenAQ", "IDEAL_OPENAQ_KEY")
        return self.http.get(
            "https://api.openaq.org/v3/locations",
            service="OpenAQ",
            params={"coordinates": f"{lat},{lon}", "radius": radius_m, "limit": limit},
            headers={"X-API-Key": self.settings.openaq_key},
        )

    def visual_crossing_timeline(
        self,
        location: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        include_events: bool = True,
    ) -> dict[str, Any]:
        if not self.settings.visual_crossing_key:
            raise MissingAPIKeyError("Visual Crossing", "IDEAL_VISUAL_CROSSING_KEY")
        params: dict[str, Any] = {
            "unitGroup": "us",
            "key": self.settings.visual_crossing_key,
            "contentType": "json",
        }
        if include_events:
            params["include"] = "events"
        if start_date:
            params["startDateTime"] = start_date
        if end_date:
            params["endDateTime"] = end_date
        return self.http.get(
            f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}",
            service="Visual Crossing",
            params=params,
        )

    def stormglass_weather(
        self,
        lat: float,
        lon: float,
        *,
        params_list: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.stormglass_key:
            raise MissingAPIKeyError("Storm Glass", "IDEAL_STORMGLASS_KEY")
        params: dict[str, Any] = {"lat": lat, "lng": lon}
        if params_list:
            params["params"] = ",".join(params_list)
        else:
            params["params"] = "waveHeight,windSpeed,gust,airTemperature,precipitation"
        return self.http.get(
            "https://api.stormglass.io/v2/weather/point",
            service="Storm Glass",
            params=params,
            headers={"Authorization": self.settings.stormglass_key},
        )
