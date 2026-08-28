import pytest

from ideal_apis import IdealAPIs
from ideal_apis.registry import COMMAND_REGISTRY, get_command, list_groups


def test_registry_has_tier1_and_tier2_commands():
    tiers = {cmd.tier for cmd in COMMAND_REGISTRY}
    assert 1 in tiers
    assert 2 in tiers
    assert len(COMMAND_REGISTRY) >= 25


def test_get_command_lookup():
    cmd = get_command("leads", "dentists")
    assert cmd is not None
    assert cmd.group == "leads"
    assert cmd.name == "dentists"


def test_list_groups_non_empty():
    groups = list_groups()
    assert "leads" in groups
    assert "weather" in groups
    assert len(groups["weather"]) >= 4


@pytest.mark.integration
def test_nppes_dentists_live():
    api = IdealAPIs()
    result = api.leads.dentists_tampa_bay(limit=3)
    assert "results" in result
    assert isinstance(result["results"], list)


@pytest.mark.integration
def test_open_meteo_forecast_live():
    api = IdealAPIs()
    result = api.weather.open_meteo_forecast(27.9506, -82.4572, forecast_days=2)
    assert "daily" in result or "hourly" in result


@pytest.mark.integration
def test_usaspending_live():
    api = IdealAPIs()
    result = api.government.usaspending_florida_construction(limit=3)
    assert "results" in result


@pytest.mark.integration
def test_email_validation_live():
    api = IdealAPIs()
    result = api.validation.validate_email("office@theidealremodeling.com")
    assert result is not None
    assert "disposable" in result or "data" in result or "status" in str(result).lower()


@pytest.mark.integration
def test_microlink_live():
    api = IdealAPIs()
    result = api.web.microlink("https://idealcgc.com")
    assert "data" in result or "status" in result
