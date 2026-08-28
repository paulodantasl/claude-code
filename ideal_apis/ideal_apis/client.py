from __future__ import annotations

from ideal_apis.config import Settings, get_settings
from ideal_apis.http import HTTPClient
from ideal_apis.services import (
    AddressService,
    DocumentsService,
    GeoService,
    GovernmentService,
    LeadsService,
    LogisticsService,
    PermitsService,
    ProductivityService,
    PropertyService,
    ValidationService,
    WeatherService,
    WebService,
)


class IdealAPIs:
    """Single entry point for all Ideal Construction public API integrations.

    Usage:
        from ideal_apis import IdealAPIs

        api = IdealAPIs()
        dentists = api.leads.dentists_tampa_bay(limit=10)
        forecast = api.weather.open_meteo_forecast(27.9506, -82.4572)
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.http = HTTPClient(self.settings)
        self.address = AddressService(self.http, self.settings)
        self.validation = ValidationService(self.http, self.settings)
        self.leads = LeadsService(self.http, self.settings)
        self.permits = PermitsService(self.http, self.settings)
        self.weather = WeatherService(self.http, self.settings)
        self.government = GovernmentService(self.http, self.settings)
        self.documents = DocumentsService(self.http, self.settings)
        self.geo = GeoService(self.http, self.settings)
        self.logistics = LogisticsService(self.http, self.settings)
        self.property = PropertyService(self.http, self.settings)
        self.productivity = ProductivityService(self.http, self.settings)
        self.web = WebService(self.http)
