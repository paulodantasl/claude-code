from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ideal_apis.client import IdealAPIs


@dataclass(frozen=True)
class CommandSpec:
    group: str
    name: str
    description: str
    tier: int
    requires_key: bool
    example: str
    handler: Callable


def _commands(api_factory: Callable[[], IdealAPIs]) -> list[CommandSpec]:
    def api() -> IdealAPIs:
        return api_factory()

    return [
        # Tier 1 — address & validation
        CommandSpec("address", "validate", "Validate a US street address (Smarty)", 1, True,
                    'ideal-api address validate --street "401 E Jackson" --city Tampa --state FL --zip 33602',
                    lambda **kw: api().address.validate(kw["street"], kw["city"], kw["state"], kw["zipcode"])),
        CommandSpec("address", "autocomplete", "Address autocomplete (Smarty)", 1, True,
                    'ideal-api address autocomplete --search "401 E Jackson Tampa"',
                    lambda **kw: api().address.autocomplete(kw["search"])),
        CommandSpec("validation", "phone", "Validate phone number", 1, False,
                    "ideal-api validation phone --number 8136945439",
                    lambda **kw: api().validation.validate_phone(kw["number"])),
        CommandSpec("validation", "email", "Validate email address", 1, False,
                    "ideal-api validation email --email test@example.com",
                    lambda **kw: api().validation.validate_email(kw["email"])),
        # Tier 1 — leads
        CommandSpec("leads", "nppes", "Search NPPES provider registry", 1, False,
                    "ideal-api leads nppes --state FL --taxonomy Dentist --limit 10",
                    lambda **kw: api().leads.nppes_search(
                        state=kw.get("state"), city=kw.get("city"),
                        taxonomy_description=kw.get("taxonomy"),
                        organization_name=kw.get("organization"),
                        limit=int(kw.get("limit", 25)),
                    )),
        CommandSpec("leads", "dentists", "Dental org leads in Florida", 1, False,
                    "ideal-api leads dentists --limit 10",
                    lambda **kw: api().leads.dentists_tampa_bay(limit=int(kw.get("limit", 25)))),
        CommandSpec("leads", "yelp", "Search Yelp for local businesses", 1, True,
                    'ideal-api leads yelp --term "dental office" --location "Tampa, FL"',
                    lambda **kw: api().leads.yelp_search(kw["term"], kw["location"], limit=int(kw.get("limit", 20)))),
        # Tier 1 — permits
        CommandSpec("permits", "socrata", "Query a Socrata permit dataset", 1, False,
                    "ideal-api permits socrata --endpoint URL --days 7",
                    lambda **kw: api().permits.recent_permits(
                        kw["endpoint"], date_column=kw.get("date_column", "issued_date"),
                        days_back=int(kw.get("days", 7)), limit=int(kw.get("limit", 500)),
                    )),
        CommandSpec("permits", "datagov", "Search Data.gov for permit datasets", 1, False,
                    "ideal-api permits datagov --query \"building permits Hillsborough\"",
                    lambda **kw: api().permits.datagov_search(kw["query"], limit=int(kw.get("limit", 20)))),
        CommandSpec("permits", "fl-datasets", "Find Florida permit open-data sets", 1, False,
                    "ideal-api permits fl-datasets --county Pinellas",
                    lambda **kw: api().permits.find_florida_permit_datasets(kw.get("county"))),
        # Tier 1 — weather
        CommandSpec("weather", "forecast", "Open-Meteo 7-day forecast", 1, False,
                    "ideal-api weather forecast --lat 27.9506 --lon -82.4572",
                    lambda **kw: api().weather.open_meteo_forecast(float(kw["lat"]), float(kw["lon"]))),
        CommandSpec("weather", "nws", "NWS forecast for coordinates", 1, False,
                    "ideal-api weather nws --lat 27.9506 --lon -82.4572",
                    lambda **kw: api().weather.nws_forecast(float(kw["lat"]), float(kw["lon"]))),
        CommandSpec("weather", "alerts", "Active NWS weather alerts", 1, False,
                    "ideal-api weather alerts --state FL",
                    lambda **kw: api().weather.nws_alerts(state=kw.get("state"))),
        CommandSpec("weather", "hail", "NOAA hail signatures near a point", 1, False,
                    "ideal-api weather hail --lat 27.9506 --lon -82.4572 --days 365",
                    lambda **kw: api().weather.hail_near(
                        float(kw["lat"]), float(kw["lon"]), days_back=int(kw.get("days", 365)),
                    )),
        CommandSpec("weather", "radar", "RainViewer radar map metadata", 1, False,
                    "ideal-api weather radar",
                    lambda **kw: api().weather.rainviewer_maps()),
        CommandSpec("weather", "stormglass", "Coastal marine weather", 1, True,
                    "ideal-api weather stormglass --lat 27.77 --lon -82.63",
                    lambda **kw: api().weather.stormglass_weather(float(kw["lat"]), float(kw["lon"]))),
        # Tier 1 — government
        CommandSpec("gov", "usaspending", "Search federal construction awards in FL", 1, False,
                    "ideal-api gov usaspending --limit 10",
                    lambda **kw: api().government.usaspending_florida_construction(limit=int(kw.get("limit", 25)))),
        CommandSpec("gov", "contracts", "Recent federal contracts feed", 1, False,
                    "ideal-api gov contracts --state FL --limit 10",
                    lambda **kw: api().government.federal_contracts(
                        state=kw.get("state"), limit=int(kw.get("limit", 25)),
                    )),
        CommandSpec("gov", "fastdol", "OSHA/WHD enforcement lookup", 1, True,
                    'ideal-api gov fastdol --company "Example Construction LLC"',
                    lambda **kw: api().government.fastdol_lookup(kw["company"])),
        CommandSpec("gov", "census-geocode", "Census geocoder (free)", 1, False,
                    'ideal-api gov census-geocode --address "401 E Jackson St, Tampa FL"',
                    lambda **kw: api().government.census_geocoder(kw["address"])),
        # Tier 1 — web
        CommandSpec("web", "microlink", "Extract metadata from a URL", 1, False,
                    "ideal-api web microlink --url https://idealcgc.com",
                    lambda **kw: api().web.microlink(kw["url"])),
        # Tier 2 — documents
        CommandSpec("docs", "ocr-url", "OCR a document from URL", 2, True,
                    "ideal-api docs ocr-url --url https://example.com/scan.pdf",
                    lambda **kw: api().documents.ocr_space(url=kw["url"])),
        CommandSpec("docs", "pandadoc-templates", "List PandaDoc templates", 2, True,
                    "ideal-api docs pandadoc-templates",
                    lambda **kw: api().documents.pandadoc_list_templates()),
        # Tier 2 — geo
        CommandSpec("geo", "google-geocode", "Google geocode an address", 2, True,
                    'ideal-api geo google-geocode --address "Tampa FL"',
                    lambda **kw: api().geo.google_geocode(kw["address"])),
        CommandSpec("geo", "mapbox-geocode", "Mapbox geocode a query", 2, True,
                    'ideal-api geo mapbox-geocode --query "Madeira Beach FL"',
                    lambda **kw: api().geo.mapbox_geocode(kw["query"])),
        CommandSpec("geo", "drive-time", "Google distance matrix", 2, True,
                    'ideal-api geo drive-time --from "Tampa FL" --to "St Petersburg FL"',
                    lambda **kw: api().geo.google_distance_matrix(kw["from"], kw["to"])),
        CommandSpec("geo", "isochrone", "Drive-time isochrone (OpenRouteService)", 2, True,
                    "ideal-api geo isochrone --lat 27.9506 --lon -82.4572 --minutes 15,30",
                    lambda **kw: api().geo.openrouteservice_isochrone(
                        float(kw["lat"]), float(kw["lon"]),
                        minutes=[int(x) for x in kw.get("minutes", "15,30").split(",")],
                    )),
        # Tier 2 — logistics
        CommandSpec("logistics", "track", "Track a parcel (WhereParcel)", 2, True,
                    "ideal-api logistics track --number 1Z999AA10123456784",
                    lambda **kw: api().logistics.whereparcel_track(kw["number"], carrier=kw.get("carrier"))),
        # Tier 2 — property
        CommandSpec("property", "opencorporates", "Search FL company registry", 2, True,
                    'ideal-api property opencorporates --query "Ideal Construction"',
                    lambda **kw: api().property.opencorporates_search(kw["query"])),
        CommandSpec("property", "schools", "School district by address", 2, True,
                    'ideal-api property schools --address "123 Main St Tampa FL"',
                    lambda **kw: api().property.district_by_address(kw["address"])),
        CommandSpec("property", "acrelens", "Land suitability score", 2, True,
                    "ideal-api property acrelens --lat 27.77 --lon -82.63",
                    lambda **kw: api().property.acrelens_score(float(kw["lat"]), float(kw["lon"]))),
        # Tier 2 — productivity
        CommandSpec("productivity", "clockify-workspaces", "List Clockify workspaces", 2, True,
                    "ideal-api productivity clockify-workspaces",
                    lambda **kw: api().productivity.clockify_workspaces()),
        # Tier 1 — market escalation (FRED)
        CommandSpec("market", "escalation", "Trailing price move for a cost series", 1, True,
                    "ideal-api call market escalation --series construction_materials --months 12",
                    lambda **kw: api().market.escalation(
                        kw.get("series", "construction_materials"),
                        months=int(kw.get("months", 12)),
                    )),
        CommandSpec("market", "exposure", "Escalation across every curated cost series", 1, True,
                    "ideal-api call market exposure --months 12",
                    lambda **kw: api().market.bid_exposure(months=int(kw.get("months", 12)))),
        CommandSpec("market", "series", "Raw observations for a FRED series", 1, True,
                    "ideal-api call market series --series lumber_wood --limit 12",
                    lambda **kw: api().market.observations(
                        kw.get("series", "construction_materials"),
                        start_date=kw.get("start"), end_date=kw.get("end"),
                        limit=int(kw["limit"]) if kw.get("limit") else None,
                    )),
        CommandSpec("market", "search", "Find a FRED series id by keyword", 1, True,
                    'ideal-api call market search --text "ready-mix concrete"',
                    lambda **kw: api().market.search(kw["text"], limit=int(kw.get("limit", 20)))),
        # Tier 1 — parcel screening
        CommandSpec("site", "screen", "Full parcel screen for one point", 1, False,
                    "ideal-api call site screen --lat 27.9506 --lon -82.4572 --zip 33602",
                    lambda **kw: api().site.screen(
                        float(kw["lat"]), float(kw["lon"]),
                        zipcode=kw.get("zipcode"), state=kw.get("state", "FL"),
                    )),
        CommandSpec("site", "flood", "FEMA flood zone and BFE at a point", 1, False,
                    "ideal-api call site flood --lat 27.9506 --lon -82.4572",
                    lambda **kw: api().site.flood_summary(float(kw["lat"]), float(kw["lon"]))),
        CommandSpec("site", "elevation", "Ground elevation in feet", 1, False,
                    "ideal-api call site elevation --lat 27.9506 --lon -82.4572",
                    lambda **kw: {"elevation_ft": api().site.elevation_ft(
                        float(kw["lat"]), float(kw["lon"]))}),
        CommandSpec("site", "groundwater", "USGS water levels near a point", 1, False,
                    "ideal-api call site groundwater --lat 27.9506 --lon -82.4572",
                    lambda **kw: api().site.water_levels(float(kw["lat"]), float(kw["lon"]))),
        CommandSpec("site", "epa", "EPA-regulated facilities by ZIP or city", 1, False,
                    "ideal-api call site epa --zip 33602",
                    lambda **kw: api().site.epa_facilities(
                        zipcode=kw.get("zipcode"), city=kw.get("city"),
                        state=kw.get("state", "FL"), rows=int(kw.get("rows", 20)),
                    )),
        # Tier 1 — compliance screening
        CommandSpec("compliance", "vendor", "Sanctions/watchlist screen for a sub", 1, False,
                    'ideal-api call compliance vendor --name "Example Construction LLC"',
                    lambda **kw: api().compliance.screen_vendor(kw["name"])),
        CommandSpec("compliance", "rules", "Federal Register sweep of watched topics", 1, False,
                    "ideal-api call compliance rules --days 30",
                    lambda **kw: api().compliance.rule_watch(days_back=int(kw.get("days", 30)))),
        CommandSpec("compliance", "register", "Search the Federal Register", 1, False,
                    'ideal-api call compliance register --term "Davis-Bacon" --days 90',
                    lambda **kw: api().compliance.federal_register_search(
                        kw["term"], days_back=int(kw.get("days", 30)),
                    )),
        # Tier 1 — schedule math
        CommandSpec("schedule", "working-days", "Count working days between two dates", 1, False,
                    "ideal-api call schedule working-days --start 2026-09-01 --end 2026-12-31",
                    lambda **kw: api().schedule.working_days(kw["start"], kw["end"])),
        CommandSpec("schedule", "add-days", "Project a date N working days out", 1, False,
                    "ideal-api call schedule add-days --start 2026-09-01 --days 120",
                    lambda **kw: api().schedule.add_working_days(kw["start"], int(kw["days"]))),
        CommandSpec("schedule", "holidays", "Public holidays for a year", 1, False,
                    "ideal-api call schedule holidays --year 2026",
                    lambda **kw: api().schedule.holidays(int(kw["year"]))),
        # Tier 1 — commercially licensed weather + air quality
        CommandSpec("weather", "job", "Job-site forecast (NWS, commercial-safe)", 1, False,
                    "ideal-api call weather job --lat 27.9506 --lon -82.4572",
                    lambda **kw: api().weather.job_forecast(float(kw["lat"]), float(kw["lon"]))),
        CommandSpec("weather", "air", "Air quality near a job site", 1, True,
                    "ideal-api call weather air --lat 27.9506 --lon -82.4572",
                    lambda **kw: api().weather.air_quality(float(kw["lat"]), float(kw["lon"]))),
        # Tier 1 — free bulk geocoding + address extraction
        # Single-address Census geocoding stays at `gov census-geocode`; this group
        # adds only the batch path, which is what replaces the metered providers.
        CommandSpec("geo", "batch-geocode", "Geocode many addresses via Census (free)", 1, False,
                    'ideal-api call geo batch-geocode --addresses "401 E Jackson St Tampa FL;100 2nd Ave St Petersburg FL"',
                    lambda **kw: api().geo.batch_geocode(
                        [a.strip() for a in kw["addresses"].split(";") if a.strip()])),
        CommandSpec("address", "extract", "Pull addresses out of text or an email", 1, True,
                    'ideal-api call address extract --text "Bid walk at 401 E Jackson St, Tampa FL 33602"',
                    lambda **kw: api().address.extract_addresses(kw["text"])),
        # Tier 2 — bid package assembly
        CommandSpec("bidpackage", "assemble", "Merge + paginate a bid package", 2, True,
                    "ideal-api call bidpackage assemble --files a.pdf;b.pdf --out package.pdf",
                    lambda **kw: api().bidpackage.assemble(
                        [f.strip() for f in kw["files"].split(";") if f.strip()],
                        kw["out"], starting_number=int(kw.get("start", 1)),
                    )),
        CommandSpec("bidpackage", "merge", "Merge PDFs in the given order", 2, True,
                    "ideal-api call bidpackage merge --files a.pdf;b.pdf --out merged.pdf",
                    lambda **kw: api().bidpackage.merge(
                        [f.strip() for f in kw["files"].split(";") if f.strip()], kw["out"])),
        CommandSpec("bidpackage", "number", "Add page numbers to a PDF", 2, True,
                    "ideal-api call bidpackage number --file package.pdf --out numbered.pdf",
                    lambda **kw: api().bidpackage.add_page_numbers(
                        kw["file"], kw["out"], starting_number=int(kw.get("start", 1)))),
        CommandSpec("bidpackage", "split", "Extract page ranges from a PDF", 2, True,
                    'ideal-api call bidpackage split --file plans.pdf --out sheets.zip --ranges "1-12,40-52"',
                    lambda **kw: api().bidpackage.split(kw["file"], kw["out"], ranges=kw["ranges"])),
    ]


COMMAND_REGISTRY: list[CommandSpec] = _commands(IdealAPIs)


def get_command(group: str, name: str) -> CommandSpec | None:
    for cmd in COMMAND_REGISTRY:
        if cmd.group == group and cmd.name == name:
            return cmd
    return None


def list_groups() -> dict[str, list[CommandSpec]]:
    groups: dict[str, list[CommandSpec]] = {}
    for cmd in COMMAND_REGISTRY:
        groups.setdefault(cmd.group, []).append(cmd)
    return groups
