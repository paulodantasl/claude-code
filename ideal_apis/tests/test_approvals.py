from pathlib import Path

from ideal_apis.pipeline.approvals import ApprovalBatch
from ideal_apis.pipeline.apply import apply_jobtread, build_quo_queue, write_quo_queue
from ideal_apis.pipeline.ledger import LeadLedger
from ideal_apis.pipeline.models import LeadRecord


def _lead(name: str, *, priority: str = "high", phone: str = "8135551234") -> LeadRecord:
    return LeadRecord(
        id=f"id_{name}",
        source="nppes",
        brand="ideal_dental",
        name=name,
        phone=phone,
        city="Tampa",
        state="FL",
        priority=priority,  # type: ignore[arg-type]
    )


def test_approval_batch_lifecycle(tmp_path: Path):
    leads = [_lead("Alpha"), _lead("Beta", priority="medium")]
    batch = ApprovalBatch.create(tmp_path, "2026-08-28", leads, [])

    assert batch.pending()
    assert batch.approve(high_only=True) == 1
    assert len(batch.approved_jobtread()) == 1

    ledger = LeadLedger(tmp_path / "ledger.json")
    result = apply_jobtread(batch, org_id="test-org", ledger=ledger, dry_run=True)
    assert result["processed"] == 1
    assert result["dry_run"] is True

    batch.mark_pushed_jobtread(0, "acct_test")
    assert batch.approve_quo(all_ready=True) == 1

    queue = build_quo_queue(batch)
    assert queue["count"] == 1
    assert "Ideal Dental Construction" in queue["messages"][0]["body"]


def test_quo_skips_already_texted(tmp_path: Path):
    lead = _lead("Gamma", phone="8135559999")
    batch = ApprovalBatch.create(tmp_path, "2026-08-29", [lead], [])
    batch.approve(all_pending=True)
    batch.mark_pushed_jobtread(0, "acct_1")
    batch.approve_quo(all_ready=True)

    ledger = LeadLedger(tmp_path / "ledger.json")
    ledger.mark_quo_texted("8135559999")
    ledger.save()

    queue = build_quo_queue(batch, ledger=ledger)
    assert queue["count"] == 0
    assert queue["skipped"][0]["reason"] == "already texted"


def test_write_quo_queue_marks_queued(tmp_path: Path):
    lead = _lead("Delta")
    batch = ApprovalBatch.create(tmp_path, "2026-08-30", [lead], [])
    batch.approve(all_pending=True)
    batch.mark_pushed_jobtread(0, "acct_2")
    batch.approve_quo(all_ready=True)

    out_dir = tmp_path / "output"
    path, queue = write_quo_queue(batch, out_dir)
    assert path.exists()
    assert queue["count"] == 1
    assert batch.items()[0]["stage"] == "queued_quo"
