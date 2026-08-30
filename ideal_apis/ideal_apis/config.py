from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def _load_env() -> None:
    """Load .env from repo root or ideal_apis package directory."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        Path.home() / ".ideal_apis.env",
    ]
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return
    load_dotenv(override=False)


class Settings(BaseModel):
    user_agent: str = Field(
        default="IdealConstruction/1.0 (ideal-apis; tampa@idealcgc.com)"
    )

    # Address / validation
    smarty_auth_id: str | None = None
    smarty_auth_token: str | None = None
    numverify_key: str | None = None
    veriphone_key: str | None = None
    kickbox_key: str | None = None

    # Leads
    yelp_key: str | None = None
    datagov_key: str | None = None
    socrata_app_token: str | None = None

    # Weather
    visual_crossing_key: str | None = None
    stormglass_key: str | None = None

    # Government
    fastdol_key: str | None = None
    census_key: str | None = None

    # Documents
    ocr_space_key: str | None = None
    buildpdf_key: str | None = None
    pandadoc_key: str | None = None

    # Geo / logistics
    google_maps_key: str | None = None
    mapbox_key: str | None = None
    openrouteservice_key: str | None = None
    whereparcel_key: str | None = None
    ups_client_id: str | None = None
    ups_client_secret: str | None = None

    # Market / escalation
    fred_key: str | None = None

    # Bid package assembly
    ilovepdf_public_key: str | None = None
    ilovepdf_secret_key: str | None = None

    # Compliance
    opensanctions_key: str | None = None

    # Environment
    aqicn_key: str | None = None
    openaq_key: str | None = None

    # Property / productivity
    acrelens_key: str | None = None
    opencorporates_key: str | None = None
    districtapi_key: str | None = None
    clockify_key: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        _load_env()
        return cls(
            user_agent=os.getenv("IDEAL_USER_AGENT", cls.model_fields["user_agent"].default),
            smarty_auth_id=os.getenv("IDEAL_SMARTY_AUTH_ID"),
            smarty_auth_token=os.getenv("IDEAL_SMARTY_AUTH_TOKEN"),
            numverify_key=os.getenv("IDEAL_NUMVERIFY_KEY"),
            veriphone_key=os.getenv("IDEAL_VERIPHONE_KEY"),
            kickbox_key=os.getenv("IDEAL_KICKBOX_KEY"),
            yelp_key=os.getenv("IDEAL_YELP_KEY"),
            datagov_key=os.getenv("IDEAL_DATAGOV_KEY"),
            socrata_app_token=os.getenv("IDEAL_SOCRATA_APP_TOKEN"),
            visual_crossing_key=os.getenv("IDEAL_VISUAL_CROSSING_KEY"),
            stormglass_key=os.getenv("IDEAL_STORMGLASS_KEY"),
            fastdol_key=os.getenv("IDEAL_FASTDOL_KEY"),
            census_key=os.getenv("IDEAL_CENSUS_KEY"),
            ocr_space_key=os.getenv("IDEAL_OCR_SPACE_KEY"),
            buildpdf_key=os.getenv("IDEAL_BUILDPDF_KEY"),
            pandadoc_key=os.getenv("IDEAL_PANDADOC_KEY"),
            google_maps_key=os.getenv("IDEAL_GOOGLE_MAPS_KEY"),
            mapbox_key=os.getenv("IDEAL_MAPBOX_KEY"),
            openrouteservice_key=os.getenv("IDEAL_OPENROUTESERVICE_KEY"),
            whereparcel_key=os.getenv("IDEAL_WHEREPARCEL_KEY"),
            ups_client_id=os.getenv("IDEAL_UPS_CLIENT_ID"),
            ups_client_secret=os.getenv("IDEAL_UPS_CLIENT_SECRET"),
            fred_key=os.getenv("IDEAL_FRED_KEY"),
            ilovepdf_public_key=os.getenv("IDEAL_ILOVEPDF_PUBLIC_KEY"),
            ilovepdf_secret_key=os.getenv("IDEAL_ILOVEPDF_SECRET_KEY"),
            opensanctions_key=os.getenv("IDEAL_OPENSANCTIONS_KEY"),
            aqicn_key=os.getenv("IDEAL_AQICN_KEY"),
            openaq_key=os.getenv("IDEAL_OPENAQ_KEY"),
            acrelens_key=os.getenv("IDEAL_ACRELENS_KEY"),
            opencorporates_key=os.getenv("IDEAL_OPENCORPORATES_KEY"),
            districtapi_key=os.getenv("IDEAL_DISTRICTAPI_KEY"),
            clockify_key=os.getenv("IDEAL_CLOCKIFY_KEY"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
