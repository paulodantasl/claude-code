import pytest

from ideal_apis import IdealAPIs
from ideal_apis.autonomy.runner import probe_command
from ideal_apis.registry import get_command


def test_basic_phone_validation_no_key():
    api = IdealAPIs()
    result = api.validation.validate_phone("8136945439")
    assert result["valid"] is True
    assert result["provider"] == "basic"


def test_federal_contracts_uses_usaspending():
    api = IdealAPIs()
    result = api.government.federal_contracts(state="FL", limit=2)
    assert "results" in result
    assert isinstance(result["results"], list)


def test_socrata_catalog_search():
    api = IdealAPIs()
    result = api.permits.socrata_catalog_search("building permits Florida", limit=2)
    assert "results" in result
    assert len(result["results"]) >= 1


def test_datagov_falls_back_to_socrata_without_key():
    api = IdealAPIs()
    result = api.permits.datagov_search("building permits Florida", limit=2)
    assert "results" in result


@pytest.mark.integration
def test_epa_envirofacts_limits_rows():
    api = IdealAPIs()
    result = api.government.epa_envirofacts("frs_program_facility/state/FL", rows=2)
    assert isinstance(result, list)
    assert len(result) <= 2


@pytest.mark.integration
def test_health_check_sample_free_apis():
    """Fast subset of free APIs — full sweep via `ideal-api health --tier 1`."""
    samples = [
        ("leads", "dentists"),
        ("weather", "forecast"),
        ("gov", "openfema"),
        ("gov", "contracts"),
        ("gov", "epa"),
        ("validation", "phone"),
        ("web", "microlink"),
        ("permits", "catalog"),
    ]
    for group, name in samples:
        cmd = get_command(group, name)
        assert cmd is not None
        result = probe_command(cmd)
        assert result.status == "ok", f"{group}/{name}: {result.message}"


@pytest.mark.integration
def test_probe_openfema_command():
    cmd = get_command("gov", "openfema")
    assert cmd is not None
    result = probe_command(cmd)
    assert result.status == "ok"
