from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.http import HTTPClient


class SiteService:
    """Screen a parcel before pricing site work — elevation, flood, water, environmental.

    Every source here is free and keyless. The composite :meth:`screen` runs all of
    them for one point so a lot can be checked in a single call, which is the whole
    reason to look before committing a site package.
    """

    ELEVATION = "https://api.opentopodata.org/v1"
    FEMA_NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
    USGS_IV = "https://waterservices.usgs.gov/nwis/iv/"
    USGS_SITE = "https://waterservices.usgs.gov/nwis/site/"
    EPA_EF = "https://data.epa.gov/efservice"

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    # ---------- elevation ----------

    def elevation(self, lat: float, lon: float, *, dataset: str = "ned10m") -> dict[str, Any]:
        """Ground elevation in meters. ned10m is the US 10-meter national elevation dataset."""
        return self.http.get(
            f"{self.ELEVATION}/{dataset}",
            service="Open Topo Data",
            params={"locations": f"{lat},{lon}"},
        )

    def elevation_ft(self, lat: float, lon: float) -> float | None:
        """Elevation in feet — the unit every FL grading and FFE conversation uses."""
        data = self.elevation(lat, lon)
        results = data.get("results") or []
        if not results or results[0].get("elevation") is None:
            return None
        return round(float(results[0]["elevation"]) * 3.28084, 2)

    # ---------- flood ----------

    def flood_zone(self, lat: float, lon: float, *, layer: int = 28) -> dict[str, Any]:
        """FEMA National Flood Hazard Layer at a point.

        Layer 28 is the flood hazard area polygon layer (S_FLD_HAZ_AR), which carries
        the zone designation and base flood elevation. Pass a different ``layer`` to
        query another NFHL layer.
        """
        return self.http.get(
            f"{self.FEMA_NFHL}/{layer}/query",
            service="FEMA NFHL",
            params={
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "FLD_ZONE,ZONE_SUBTY,STATIC_BFE,DEPTH,SFHA_TF,DFIRM_ID",
                "returnGeometry": "false",
                "f": "json",
            },
        )

    def flood_summary(self, lat: float, lon: float) -> dict[str, Any]:
        """Flatten the NFHL response to the fields that actually drive cost."""
        raw = self.flood_zone(lat, lon)
        features = raw.get("features") or []
        if not features:
            return {"in_mapped_zone": False, "note": "no NFHL polygon at this point"}
        attrs = features[0].get("attributes", {})
        bfe = attrs.get("STATIC_BFE")
        if bfe in (-9999, "-9999"):
            bfe = None
        return {
            "in_mapped_zone": True,
            "flood_zone": attrs.get("FLD_ZONE"),
            "zone_subtype": attrs.get("ZONE_SUBTY"),
            "static_bfe_ft": bfe,
            "special_flood_hazard_area": attrs.get("SFHA_TF") == "T",
            "firm_id": attrs.get("DFIRM_ID"),
        }

    # ---------- groundwater / surface water ----------

    def water_sites(
        self,
        lat: float,
        lon: float,
        *,
        radius_deg: float = 0.15,
        site_type: str = "GW",
    ) -> Any:
        """USGS monitoring sites in a bounding box. site_type GW = groundwater, ST = stream."""
        west, south = lon - radius_deg, lat - radius_deg
        east, north = lon + radius_deg, lat + radius_deg
        return self.http.get(
            self.USGS_SITE,
            service="USGS Water Services",
            params={
                "format": "rdb",
                "bBox": f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}",
                "siteType": site_type,
                "siteStatus": "active",
            },
        )

    def water_levels(
        self,
        lat: float,
        lon: float,
        *,
        radius_deg: float = 0.15,
        parameter: str = "72019",
    ) -> dict[str, Any]:
        """Current readings near a point. 72019 = depth to water level below land surface.

        This is the dewatering question: how far down is the water table right now,
        and which way has it been moving.
        """
        west, south = lon - radius_deg, lat - radius_deg
        east, north = lon + radius_deg, lat + radius_deg
        return self.http.get(
            self.USGS_IV,
            service="USGS Water Services",
            params={
                "format": "json",
                "bBox": f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}",
                "parameterCd": parameter,
                "siteStatus": "active",
            },
        )

    # ---------- environmental ----------

    def epa_facilities(
        self,
        *,
        zipcode: str | None = None,
        city: str | None = None,
        state: str = "FL",
        rows: int = 20,
    ) -> Any:
        """EPA-regulated facilities from the Facility Registry Service.

        Envirofacts filters on attributes rather than a radius, so screen by ZIP or
        city. A hit is not automatically a problem — it is the prompt to look at what
        the facility is before pricing excavation or committing to the parcel.
        """
        path = f"{self.EPA_EF}/frs.frs_facility_site"
        if zipcode:
            path += f"/postal_code/BEGINNING/{zipcode}"
        elif city:
            path += f"/city_name/{city.upper()}"
        if state:
            path += f"/state_code/{state.upper()}"
        return self.http.get(f"{path}/rows/0:{max(rows - 1, 0)}/JSON", service="EPA Envirofacts")

    # ---------- composite ----------

    def screen(
        self,
        lat: float,
        lon: float,
        *,
        zipcode: str | None = None,
        state: str = "FL",
    ) -> dict[str, Any]:
        """Run every screen for one point and collect what comes back.

        Each source is captured independently: a source that errors records its error
        instead of sinking the whole screen, because a partial answer before a land
        decision still beats no answer.
        """
        report: dict[str, Any] = {"lat": lat, "lon": lon}
        checks: dict[str, Any] = {
            "elevation_ft": lambda: self.elevation_ft(lat, lon),
            "flood": lambda: self.flood_summary(lat, lon),
            "groundwater": lambda: self.water_levels(lat, lon),
        }
        if zipcode:
            checks["epa_facilities"] = lambda: self.epa_facilities(zipcode=zipcode, state=state)
        for name, run in checks.items():
            try:
                report[name] = run()
            except Exception as exc:
                report[name] = {"error": str(exc)}
        return report
