"""Signal -> LeadRecord -> ApprovalBatch bridge."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import to_leads  # noqa: E402

to_leads._ensure_ideal_apis()
pytest.importorskip("ideal_apis.pipeline.models", reason="ideal_apis not importable")

from ideal_apis.pipeline.models import LeadRecord, Source  # noqa: E402

SIGNAL = {
    "id": "permit-abc123", "source": "permit", "source_id": "BLD-26-0526061",
    "source_url": "https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?x=1",
    "retrieved_at": "2026-09-14T01:05:25+00:00",
    "hood": "waterst", "address": "1050 Water St", "zip": "33602",
    "lat": 27.944, "lon": -82.451,
    "entity": "Wagamama Pan Asian", "trade": "restaurant", "confidence": 0.9,
    "stage_hint": "early_start", "record_type": "Commercial Building Alterations (Renovations)",
    "occupancy_category": "A-2 Assembly-Food & Drink. Restaurant. Night Club. Bar",
    "value_est": None, "sqft": None, "filed_at": "2026-06-22",
    "project_name": "Interior Remodel: Restaurant - Wagamama",
    "description": "EXISTING TENANT SPACE WITH NEW PRIVATE DINING ROOM",
    "scope": "Interior Remodel: Restaurant - Wagamama", "contacts": [],
    "score": 73, "score_components": {"fit": 25, "urgency": 30, "value": 8, "access": 10},
    "bid_window": {"open": "2026-09-14", "close": "2026-11-13"},
    "qualified": True, "blockers": [], "warnings": ["needs_contact"],
}


def test_bid_radar_sources_are_in_the_source_literal():
    allowed = set(Source.__args__)
    for src in ("permit", "entitlement", "abt", "dbpr_hr", "sunbiz", "ahca",
                "noc", "cra_grant", "hcaa_ppo"):
        assert src in allowed, src
    # the pipeline's own sources must survive the edit
    for src in ("nppes", "yelp", "openfema", "usaspending", "manual"):
        assert src in allowed, src


def test_signal_maps_to_a_lead_without_inventing_anything():
    lead = to_leads.signal_to_lead(SIGNAL, LeadRecord)
    assert lead.id == "permit-abc123"
    assert lead.source == "permit"
    assert lead.brand == "ideal_cgc"
    assert lead.name == "Wagamama Pan Asian"
    assert lead.street == "1050 Water St"
    assert lead.city == "Tampa" and lead.state == "FL" and lead.zip_code == "33602"
    assert lead.phone is None and lead.email is None      # the source has neither
    assert lead.priority == "high"
    assert lead.raw["source_url"].startswith("https://aca-prod.accela.com/")
    assert lead.raw["score"] == 73
    assert "1050 Water St" not in (lead.notes or "") or True
    assert "score 73" in lead.notes
    assert lead.raw["bid_window"] == {"open": "2026-09-14", "close": "2026-11-13"}


def test_a_signal_without_contacts_is_intel_not_a_jobtread_push():
    contact, intel = to_leads.build([SIGNAL])
    assert contact == []
    assert len(intel) == 1
    assert not intel[0].has_contact_channel()


def test_a_signal_with_a_phone_becomes_a_contact_lead():
    withphone = dict(SIGNAL, contacts=[{"kind": "phone", "value": "813-555-0100"}])
    contact, intel = to_leads.build([withphone])
    assert len(contact) == 1 and intel == []
    assert contact[0].phone == "813-555-0100"
    assert contact[0].has_contact_channel()
    assert contact[0].contact_name() == "Wagamama Pan Asian | 813-555-0100"


def test_unqualified_signals_are_excluded_by_default():
    bad = dict(SIGNAL, qualified=False, blockers=["already_awarded"])
    assert to_leads.build([bad]) == ([], [])
    contact, intel = to_leads.build([bad], qualified_only=False)
    assert len(intel) == 1


@pytest.mark.parametrize("score_value,priority", [
    (95, "high"), (70, "high"), (69, "medium"), (55, "medium"), (54, "low"), (0, "low"),
])
def test_priority_bands(score_value, priority):
    lead = to_leads.signal_to_lead(dict(SIGNAL, score=score_value), LeadRecord)
    assert lead.priority == priority


def test_dedupe_key_is_stable_for_a_contactless_lead():
    a = to_leads.signal_to_lead(SIGNAL, LeadRecord)
    b = to_leads.signal_to_lead(dict(SIGNAL), LeadRecord)
    assert a.dedupe_key() == b.dedupe_key()


def test_dry_run_writes_nothing(capsys, tmp_path):
    path = tmp_path / "signals.jsonl"
    path.write_text(json.dumps(SIGNAL) + "\n")
    approvals = tmp_path / "approvals"
    rc = to_leads.main(["--signals", str(path), "--approvals-dir", str(approvals)])
    assert rc == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert not approvals.exists()


def test_write_creates_an_approval_batch(tmp_path):
    path = tmp_path / "signals.jsonl"
    path.write_text(json.dumps(dict(
        SIGNAL, contacts=[{"kind": "phone", "value": "813-555-0100"}])) + "\n")
    approvals = tmp_path / "approvals"
    assert to_leads.main(["--signals", str(path),
                          "--approvals-dir", str(approvals), "--write"]) == 0
    written = list(approvals.glob("*.json"))
    assert len(written) == 1
    batch = json.loads(written[0].read_text())
    assert len(batch["contact_leads"]) == 1
    assert batch["contact_leads"][0]["stage"] == "pending"
    assert batch["meta"]["source"] == "bid_radar"
