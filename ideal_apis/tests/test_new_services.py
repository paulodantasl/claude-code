"""Contract and logic tests for the services added for construction workflows.

These pin two things upstream drift would otherwise break silently: the request we
send (URL, params, auth header) and how we reshape the response into the fields a
bid actually uses. HTTP is mocked, so they run offline and in CI without keys.
"""

from __future__ import annotations

import httpx
import pytest

from ideal_apis import IdealAPIs
from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError


@pytest.fixture
def api() -> IdealAPIs:
    """A client with every key populated, so keyed paths are exercised."""
    return IdealAPIs(
        Settings(
            fred_key="test-fred",
            aqicn_key="test-aqicn",
            ilovepdf_public_key="test-ilovepdf",
            smarty_auth_id="test-id",
            smarty_auth_token="test-token",
        )
    )


@pytest.fixture
def bare_api() -> IdealAPIs:
    """A client with no keys, for asserting the missing-key errors."""
    return IdealAPIs(Settings())


# --------------------------- schedule (working-day math) ---------------------------

HOLIDAYS_2026 = [
    {"date": "2026-01-01", "name": "New Year's Day"},
    {"date": "2026-09-07", "name": "Labour Day"},
    {"date": "2026-11-26", "name": "Thanksgiving Day"},
    {"date": "2026-12-25", "name": "Christmas Day"},
]


def _mock_holidays(httpx_mock, years=(2026,)):
    for year in years:
        httpx_mock.add_response(
            url=f"https://date.nager.at/api/v3/PublicHolidays/{year}/US",
            json=HOLIDAYS_2026 if year == 2026 else [],
            is_reusable=True,
        )


def test_working_days_excludes_weekends_and_holidays(api, httpx_mock):
    _mock_holidays(httpx_mock)
    # Mon 2026-09-07 (Labor Day) through Fri 2026-09-11: 5 weekdays, 1 holiday.
    result = api.schedule.working_days("2026-09-07", "2026-09-11")
    assert result["calendar_days"] == 5
    assert result["working_days"] == 4
    assert result["holidays_observed"] == ["2026-09-07"]


def test_working_days_counts_weekend_days(api, httpx_mock):
    _mock_holidays(httpx_mock)
    # Tue 2026-09-01 through Mon 2026-09-14: 14 calendar days, 4 weekend days,
    # 10 weekdays, less Labor Day = 9 working days.
    result = api.schedule.working_days("2026-09-01", "2026-09-14")
    assert result["calendar_days"] == 14
    assert result["weekend_days"] == 4
    assert result["working_days"] == 9


def test_working_days_handles_reversed_range(api, httpx_mock):
    _mock_holidays(httpx_mock)
    forward = api.schedule.working_days("2026-09-01", "2026-09-14")
    backward = api.schedule.working_days("2026-09-14", "2026-09-01")
    assert forward == backward


def test_add_working_days_skips_holiday(api, httpx_mock):
    _mock_holidays(httpx_mock)
    # From Fri 2026-09-04, one working day lands on Tue 2026-09-08 because
    # the weekend and Labor Day are both skipped.
    result = api.schedule.add_working_days("2026-09-04", 1)
    assert result["end"] == "2026-09-08"
    assert result["holidays_skipped"] == ["2026-09-07"]


def test_is_working_day(api, httpx_mock):
    _mock_holidays(httpx_mock)
    assert api.schedule.is_working_day("2026-09-08") is True
    assert api.schedule.is_working_day("2026-09-07") is False  # Labor Day
    assert api.schedule.is_working_day("2026-09-05") is False  # Saturday


def test_holidays_are_fetched_once_per_year(api, httpx_mock):
    """The year's holidays are cached, so a long date range is one request."""
    httpx_mock.add_response(
        url="https://date.nager.at/api/v3/PublicHolidays/2026/US",
        json=HOLIDAYS_2026,
    )
    api.schedule.working_days("2026-01-01", "2026-12-31")
    api.schedule.working_days("2026-03-01", "2026-06-30")
    assert len(httpx_mock.get_requests()) == 1


# --------------------------- site (parcel screening) ---------------------------

def test_elevation_ft_converts_meters(api, httpx_mock):
    httpx_mock.add_response(
        json={"results": [{"elevation": 12.0, "location": {"lat": 27.95, "lng": -82.45}}]},
    )
    assert api.site.elevation_ft(27.95, -82.45) == pytest.approx(39.37, abs=0.01)


def test_elevation_ft_returns_none_when_unavailable(api, httpx_mock):
    httpx_mock.add_response(json={"results": [{"elevation": None}]})
    assert api.site.elevation_ft(27.95, -82.45) is None


def test_flood_summary_extracts_zone_and_bfe(api, httpx_mock):
    httpx_mock.add_response(
        json={
            "features": [
                {
                    "attributes": {
                        "FLD_ZONE": "AE",
                        "ZONE_SUBTY": None,
                        "STATIC_BFE": 11.0,
                        "SFHA_TF": "T",
                        "DFIRM_ID": "12057C",
                    }
                }
            ]
        }
    )
    summary = api.site.flood_summary(27.95, -82.45)
    assert summary["flood_zone"] == "AE"
    assert summary["static_bfe_ft"] == 11.0
    assert summary["special_flood_hazard_area"] is True


def test_flood_summary_normalizes_sentinel_bfe(api, httpx_mock):
    """FEMA encodes 'no BFE published' as -9999; that must not reach an estimate."""
    httpx_mock.add_response(
        json={"features": [{"attributes": {"FLD_ZONE": "X", "STATIC_BFE": -9999, "SFHA_TF": "F"}}]}
    )
    summary = api.site.flood_summary(27.95, -82.45)
    assert summary["static_bfe_ft"] is None
    assert summary["special_flood_hazard_area"] is False


def test_flood_summary_when_point_is_unmapped(api, httpx_mock):
    httpx_mock.add_response(json={"features": []})
    assert api.site.flood_summary(27.95, -82.45)["in_mapped_zone"] is False


def test_flood_zone_queries_point_in_wgs84(api, httpx_mock):
    httpx_mock.add_response(json={"features": []})
    api.site.flood_zone(27.95, -82.45)
    request = httpx_mock.get_requests()[0]
    assert "hazards.fema.gov" in str(request.url)
    assert request.url.params["geometry"] == "-82.45,27.95"  # lon,lat order
    assert request.url.params["inSR"] == "4326"


def test_screen_survives_one_failing_source(api, httpx_mock):
    """A partial screen still beats no screen before a land decision."""

    def by_host(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "api.opentopodata.org":
            return httpx.Response(200, json={"results": [{"elevation": 12.0}]})
        if host == "hazards.fema.gov":
            return httpx.Response(500, text="upstream down")
        return httpx.Response(200, json={"value": {}})

    httpx_mock.add_callback(by_host, is_reusable=True)
    report = api.site.screen(27.95, -82.45)
    assert report["elevation_ft"] == pytest.approx(39.37, abs=0.01)
    assert "error" in report["flood"]
    assert "groundwater" in report


# --------------------------- compliance ---------------------------

def test_screen_vendor_flags_hits_above_threshold(api, httpx_mock):
    httpx_mock.add_response(
        json={
            "results": [
                {"caption": "Acme Construction LLC", "score": 0.94, "schema": "Company",
                 "datasets": ["us_ofac_sdn"], "properties": {"topics": ["sanction"]}},
                {"caption": "Acme Cement", "score": 0.31, "schema": "Company", "datasets": []},
            ]
        }
    )
    result = api.compliance.screen_vendor("Acme Construction LLC")
    assert result["clear"] is False
    assert len(result["hits"]) == 1
    assert result["hits"][0]["datasets"] == ["us_ofac_sdn"]
    assert result["total_candidates"] == 2


def test_screen_vendor_clear_when_only_weak_matches(api, httpx_mock):
    httpx_mock.add_response(json={"results": [{"caption": "Unrelated Co", "score": 0.2}]})
    result = api.compliance.screen_vendor("Ideal Construction LLC")
    assert result["clear"] is True
    assert result["hits"] == []


def test_sanctions_search_sends_key_when_configured(httpx_mock):
    api = IdealAPIs(Settings(opensanctions_key="secret"))
    httpx_mock.add_response(json={"results": []})
    api.compliance.sanctions_search("Acme")
    assert httpx_mock.get_requests()[0].headers["Authorization"] == "ApiKey secret"


def test_sanctions_search_works_without_key(bare_api, httpx_mock):
    """The open dataset is keyless; no key must not mean no screen."""
    httpx_mock.add_response(json={"results": []})
    bare_api.compliance.sanctions_search("Acme")
    assert "Authorization" not in httpx_mock.get_requests()[0].headers


def test_rule_watch_covers_every_watch_term(api, httpx_mock):
    httpx_mock.add_response(json={"count": 0, "results": []}, is_reusable=True)
    report = api.compliance.rule_watch(days_back=30)
    assert set(report["topics"]) == set(api.compliance.WATCH_TERMS)


# --------------------------- market (FRED escalation) ---------------------------

def test_escalation_computes_trailing_move(api, httpx_mock):
    httpx_mock.add_response(
        json={
            "observations": [
                {"date": "2025-08-01", "value": "100.0"},
                {"date": "2026-02-01", "value": "104.0"},
                {"date": "2026-08-01", "value": "108.0"},
            ]
        }
    )
    result = api.market.escalation("construction_materials", months=12)
    assert result["series"] == "WPUSI012011"
    assert result["pct_change"] == 8.0
    assert result["start"]["value"] == 100.0
    assert result["end"]["value"] == 108.0


def test_escalation_ignores_missing_observations(api, httpx_mock):
    """FRED marks a missing period with '.', which would crash a float() cast."""
    httpx_mock.add_response(
        json={
            "observations": [
                {"date": "2025-08-01", "value": "."},
                {"date": "2025-09-01", "value": "200.0"},
                {"date": "2026-08-01", "value": "210.0"},
            ]
        }
    )
    result = api.market.escalation("lumber_wood", months=12)
    assert result["observations"] == 2
    assert result["pct_change"] == 5.0


def test_escalation_reports_insufficient_data(api, httpx_mock):
    httpx_mock.add_response(json={"observations": [{"date": "2026-08-01", "value": "100.0"}]})
    assert "error" in api.market.escalation("lumber_wood")


def test_series_accepts_friendly_name_or_raw_id(api, httpx_mock):
    httpx_mock.add_response(json={"observations": []}, is_reusable=True)
    api.market.observations("lumber_wood")
    api.market.observations("CUSR0000SA0")
    ids = [r.url.params["series_id"] for r in httpx_mock.get_requests()]
    assert ids == ["WPU081", "CUSR0000SA0"]


def test_bid_exposure_isolates_a_failing_series(api, httpx_mock):
    httpx_mock.add_response(status_code=400, is_reusable=True)
    report = api.market.bid_exposure(months=6)
    assert set(report["series"]) == set(api.market.SERIES)
    assert all("error" in v for v in report["series"].values())


def test_market_requires_key(bare_api):
    with pytest.raises(MissingAPIKeyError) as excinfo:
        bare_api.market.escalation()
    assert "IDEAL_FRED_KEY" in str(excinfo.value)


# --------------------------- weather licensing + geo ---------------------------

def test_job_forecast_uses_nws_not_open_meteo(api, httpx_mock):
    """The commercial default must not touch Open-Meteo's non-commercial tier."""
    httpx_mock.add_response(
        url="https://api.weather.gov/points/27.9500,-82.4500",
        json={"properties": {"forecast": "https://api.weather.gov/gridpoints/TBW/1,1/forecast"}},
    )
    httpx_mock.add_response(
        url="https://api.weather.gov/gridpoints/TBW/1,1/forecast",
        json={"properties": {"periods": [{"shortForecast": "Sunny"}]}},
    )
    api.weather.job_forecast(27.95, -82.45)
    assert all("weather.gov" in str(r.url) for r in httpx_mock.get_requests())


def test_air_quality_requires_key(bare_api):
    with pytest.raises(MissingAPIKeyError) as excinfo:
        bare_api.weather.air_quality(27.95, -82.45)
    assert "IDEAL_AQICN_KEY" in str(excinfo.value)


def test_batch_geocode_uses_free_census_endpoint(api, httpx_mock):
    httpx_mock.add_response(
        json={
            "result": {
                "addressMatches": [
                    {
                        "matchedAddress": "401 E JACKSON ST, TAMPA, FL, 33602",
                        "coordinates": {"x": -82.4572, "y": 27.9506},
                    }
                ]
            }
        }
    )
    results = api.geo.batch_geocode(["401 E Jackson St, Tampa, FL 33602"])
    assert results[0]["matched"] is True
    assert results[0]["lat"] == 27.9506
    assert "geocoding.geo.census.gov" in str(httpx_mock.get_requests()[0].url)


def test_batch_geocode_continues_past_a_failure(api, httpx_mock):
    """One unmatched row must not cost the rest of the batch."""
    calls = {"n": 0}

    def fail_then_match(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if "bad+address" in str(request.url) or "bad%20address" in str(request.url):
            return httpx.Response(500, text="upstream down")
        return httpx.Response(200, json={"result": {"addressMatches": [
            {"matchedAddress": "TAMPA, FL", "coordinates": {"x": -82.4, "y": 27.9}}
        ]}})

    httpx_mock.add_callback(fail_then_match, is_reusable=True)
    results = api.geo.batch_geocode(["bad address", "401 E Jackson St, Tampa FL"])
    assert results[0]["matched"] is False and "error" in results[0]
    assert results[1]["matched"] is True


# --------------------------- bid package ---------------------------

def test_bidpackage_requires_key(bare_api, tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    a.write_bytes(b"%PDF-1.4 a")
    b.write_bytes(b"%PDF-1.4 b")
    with pytest.raises(MissingAPIKeyError) as excinfo:
        bare_api.bidpackage.merge([a, b], tmp_path / "out.pdf")
    assert "IDEAL_ILOVEPDF_PUBLIC_KEY" in str(excinfo.value)


def test_merge_rejects_a_single_input(api):
    with pytest.raises(ValueError):
        api.bidpackage.merge(["only.pdf"], "out.pdf")


def test_merge_reports_missing_input_before_uploading(api, tmp_path, httpx_mock):
    real = tmp_path / "a.pdf"
    real.write_bytes(b"%PDF-1.4")
    with pytest.raises(FileNotFoundError) as excinfo:
        api.bidpackage.merge([real, tmp_path / "missing.pdf"], tmp_path / "out.pdf")
    assert "missing.pdf" in str(excinfo.value)
    assert httpx_mock.get_requests() == []


def test_merge_runs_the_full_task_flow(api, tmp_path, httpx_mock):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    a.write_bytes(b"%PDF-1.4 a")
    b.write_bytes(b"%PDF-1.4 b")

    httpx_mock.add_response(url="https://api.ilovepdf.com/v1/auth", json={"token": "jwt"})
    httpx_mock.add_response(
        url="https://api.ilovepdf.com/v1/start/merge",
        json={"server": "api8g.ilovepdf.com", "task": "task123"},
    )
    httpx_mock.add_response(
        url="https://api8g.ilovepdf.com/v1/upload",
        json={"server_filename": "uploaded.pdf"},
        is_reusable=True,
    )
    httpx_mock.add_response(
        url="https://api8g.ilovepdf.com/v1/process",
        json={"download_filename": "merged.pdf"},
    )
    httpx_mock.add_response(
        url="https://api8g.ilovepdf.com/v1/download/task123",
        content=b"%PDF-1.4 merged",
    )

    out = tmp_path / "package.pdf"
    result = api.bidpackage.merge([a, b], out)

    assert out.read_bytes() == b"%PDF-1.4 merged"
    assert result["bytes"] == len(b"%PDF-1.4 merged")
    # Both inputs uploaded, and the task id threaded through every step.
    uploads = [r for r in httpx_mock.get_requests() if r.url.path == "/v1/upload"]
    assert len(uploads) == 2
