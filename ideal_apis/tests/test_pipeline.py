import json
from pathlib import Path

import pytest

from ideal_apis.pipeline.enrich import enrich_leads
from ideal_apis.pipeline.ledger import LeadLedger
from ideal_apis.pipeline.models import LeadRecord
from ideal_apis.pipeline.runner import DailyLeadPipeline
from ideal_apis.pipeline.sources import nppes_to_leads


def test_nppes_to_leads_parses_org():
    sample = {
        "results": [{
            "number": "1234567890",
            "basic": {"organization_name": "Smile Dental PA"},
            "addresses": [{
                "address_purpose": "LOCATION",
                "address_1": "100 Main St",
                "city": "Tampa",
                "state": "FL",
                "postal_code": "336021234",
                "telephone_number": "8135551234",
            }],
        }]
    }
    leads = nppes_to_leads(sample, brand="ideal_dental", taxonomy="Dentist")
    assert len(leads) == 1
    assert leads[0].npi == "1234567890"
    assert leads[0].phone == "8135551234"
    assert "813-555-1234" in leads[0].contact_name()


def test_ledger_dedupe(tmp_path: Path):
    path = tmp_path / "ledger.json"
    ledger = LeadLedger(path)
    lead = LeadRecord(id="x", source="nppes", brand="ideal_dental", name="Test", phone="8135551234")
    key = lead.dedupe_key()
    assert not ledger.seen(key)
    ledger.mark_seen(key, lead.to_dict())
    ledger.save()
    ledger2 = LeadLedger(path)
    assert ledger2.seen(key)


@pytest.mark.integration
def test_daily_pipeline_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config = {
        "ledger_path": str(tmp_path / "ledger.json"),
        "output_dir": str(tmp_path / "output"),
        "nppes_searches": [{
            "brand": "ideal_dental",
            "taxonomy": "Dentist",
            "state": "FL",
            "cities": ["Tampa"],
            "limit": 3,
        }],
        "yelp_searches": [],
        "openfema": {"states": ["FL"], "days_back": 30, "incident_types": ["Hurricane", "Flood"]},
        "weather": {"alert_state": "FL", "hail_points": [{"name": "Tampa", "lat": 27.95, "lon": -82.46}], "hail_days_back": 30},
        "government": {"usaspending_limit": 2, "federal_contracts_limit": 2},
        "jobtread": {"org_id": "22P6bRn5p6Pn", "dry_run": True},
    }
    cfg_path = tmp_path / "pipeline.yaml"
    import yaml
    cfg_path.write_text(yaml.dump(config))

    pipeline = DailyLeadPipeline(config_path=cfg_path)
    result = pipeline.run(skip_yelp=True, dry_run=True, push_jobtread=False)

    assert result["fetched"] > 0
    assert Path(result["outputs"]["csv"]).exists()
    assert Path(result["outputs"]["summary"]).exists()
    data = json.loads(Path(result["outputs"]["json"]).read_text())
    assert isinstance(data, list)
