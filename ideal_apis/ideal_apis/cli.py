from __future__ import annotations

import json
import sys
from typing import Any

import click

from ideal_apis.config import get_settings
from ideal_apis.autonomy.runner import run_health_check, write_health_report
from ideal_apis.pipeline.approvals import ApprovalBatch
from ideal_apis.pipeline.apply import apply_jobtread, write_quo_queue
from ideal_apis.pipeline.runner import DailyLeadPipeline
from ideal_apis.registry import get_command, list_groups


def _print_json(data: Any) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


def _parse_params(params: tuple[str, ...]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    i = 0
    while i < len(params):
        token = params[i]
        if not token.startswith("--"):
            raise click.ClickException(f"Expected --flag, got {token!r}")
        key = token[2:].replace("-", "_")
        if i + 1 >= len(params) or params[i + 1].startswith("--"):
            kwargs[key] = True
            i += 1
        else:
            kwargs[key] = params[i + 1]
            i += 2
    # Common CLI aliases
    if "zip" in kwargs and "zipcode" not in kwargs:
        kwargs["zipcode"] = kwargs.pop("zip")
    if "from_" in kwargs and "from" not in kwargs:
        kwargs["from"] = kwargs.pop("from_")
    return kwargs


@click.group()
@click.version_option(package_name="ideal-apis")
def main() -> None:
    """Ideal Construction unified public API CLI."""


@main.command("list")
@click.option("--tier", type=int, default=None, help="Filter by tier (1 or 2)")
def list_commands(tier: int | None) -> None:
    """List all available API commands."""
    for group, cmds in sorted(list_groups().items()):
        filtered = [c for c in cmds if tier is None or c.tier == tier]
        if not filtered:
            continue
        click.echo(f"\n[{group}]")
        for cmd in filtered:
            key_flag = "key required" if cmd.requires_key else "free/keyless OK"
            click.echo(f"  {cmd.name:<22} tier {cmd.tier}  {key_flag}")
            click.echo(f"    {cmd.description}")
            click.echo(f"    e.g. {cmd.example}")


@main.command("keys")
def show_keys() -> None:
    """Show which API keys are configured (values hidden)."""
    s = get_settings()
    fields = [
        ("Smarty", s.smarty_auth_id and s.smarty_auth_token),
        ("Numverify", s.numverify_key),
        ("Veriphone", s.veriphone_key),
        ("Kickbox", s.kickbox_key),
        ("Yelp", s.yelp_key),
        ("Data.gov", s.datagov_key),
        ("Socrata token", s.socrata_app_token),
        ("Visual Crossing", s.visual_crossing_key),
        ("Storm Glass", s.stormglass_key),
        ("FastDOL", s.fastdol_key),
        ("Census", s.census_key),
        ("OCR.Space", s.ocr_space_key),
        ("BuildPDF", s.buildpdf_key),
        ("PandaDoc", s.pandadoc_key),
        ("Google Maps", s.google_maps_key),
        ("Mapbox", s.mapbox_key),
        ("OpenRouteService", s.openrouteservice_key),
        ("WhereParcel", s.whereparcel_key),
        ("UPS", s.ups_client_id and s.ups_client_secret),
        ("AcreLens", s.acrelens_key),
        ("OpenCorporates", s.opencorporates_key),
        ("DistrictAPI", s.districtapi_key),
        ("Clockify", s.clockify_key),
    ]
    import os
    fields.append(("JobTread grant", os.getenv("JOBTREAD_GRANT_KEY")))
    for name, configured in fields:
        status = "set" if configured else "missing"
        click.echo(f"{name:<20} {status}")



def _parse_indices(value: str) -> list[int]:
    try:
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as exc:
        raise click.ClickException(f"Invalid indices: {value!r}") from exc


def _get_pipeline(config_path: str | None) -> DailyLeadPipeline:
    from pathlib import Path

    return DailyLeadPipeline(
        config_path=Path(config_path) if config_path else None,
    )


def _open_batch(pipeline: DailyLeadPipeline, batch_id: str | None) -> ApprovalBatch:
    if batch_id:
        return ApprovalBatch.open(pipeline.approvals_dir, batch_id)
    batch = ApprovalBatch.latest(pipeline.approvals_dir)
    if not batch:
        raise click.ClickException("No approval batch found. Run: ideal-api leads collect")
    return batch


def _print_leads_table(batch: ApprovalBatch, *, stage: str | None = None, limit: int = 30) -> None:
    rows = batch.items()
    if stage:
        rows = [r for r in rows if r["stage"] == stage]
    click.echo(f"\nBatch {batch.batch_id} — showing {min(len(rows), limit)} of {len(rows)} leads\n")
    for item in rows[:limit]:
        lead = item["lead"]
        contact = lead.get("phone") or lead.get("email") or "—"
        click.echo(
            f"  [{item['index']:>3}] {item['stage']:<18} "
            f"{lead.get('priority', '?'):<6} {lead.get('name', '')[:40]:<40} {contact}"
        )


@main.group("leads")
def leads_group() -> None:
    """Approval-gated daily lead pipeline (collect → approve → apply)."""


@leads_group.command("collect")
@click.option("--skip-yelp", is_flag=True, default=False, help="Skip Yelp (no IDEAL_YELP_KEY)")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True), help="pipeline.yaml path")
def leads_collect(skip_yelp: bool, config_path: str | None) -> None:
    """Fetch leads and create an approval batch (does not push JobTread or QUO)."""
    pipeline = _get_pipeline(config_path)
    result = pipeline.collect(skip_yelp=skip_yelp)
    _print_json(result)
    batch = ApprovalBatch.open(pipeline.approvals_dir, result["batch_id"])
    _print_leads_table(batch, stage="pending", limit=25)
    click.echo(f"\n{result['next_step']}")


@leads_group.command("status")
@click.option("--batch", "batch_id", default=None, help="Batch id (default: latest)")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
@click.option("--show-leads", is_flag=True, default=False, help="List leads in batch")
def leads_status(batch_id: str | None, config_path: str | None, show_leads: bool) -> None:
    """Show approval batch summary and next step."""
    pipeline = _get_pipeline(config_path)
    batch = _open_batch(pipeline, batch_id)
    summary = batch.summary()
    _print_json(summary)
    if show_leads:
        _print_leads_table(batch, limit=50)
    click.echo(f"\n{summary['next_step']}")


@leads_group.command("approve")
@click.option("--batch", "batch_id", default=None)
@click.option("--high-only", is_flag=True, default=False, help="Approve high-priority pending leads only")
@click.option("--all", "all_pending", is_flag=True, default=False, help="Approve all pending leads")
@click.option("--indices", default=None, help="Comma-separated indices, e.g. 0,1,5")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
def leads_approve(
    batch_id: str | None,
    high_only: bool,
    all_pending: bool,
    indices: str | None,
    config_path: str | None,
) -> None:
    """Approve pending leads for JobTread push."""
    if not (high_only or all_pending or indices):
        raise click.ClickException("Specify --high-only, --all, or --indices 0,1,2")
    pipeline = _get_pipeline(config_path)
    batch = _open_batch(pipeline, batch_id)
    idx_list = _parse_indices(indices) if indices else None
    changed = batch.approve(indices=idx_list, high_only=high_only, all_pending=all_pending)
    click.echo(f"Approved {changed} lead(s) for JobTread.")
    _print_json(batch.summary())
    if batch.approved_jobtread():
        click.echo("\nNext: ideal-api leads apply jobtread --live")


@leads_group.command("reject")
@click.option("--batch", "batch_id", default=None)
@click.option("--indices", required=True, help="Comma-separated indices to reject")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
def leads_reject(batch_id: str | None, indices: str, config_path: str | None) -> None:
    """Reject pending leads (will not be pushed)."""
    pipeline = _get_pipeline(config_path)
    batch = _open_batch(pipeline, batch_id)
    changed = batch.reject(_parse_indices(indices))
    click.echo(f"Rejected {changed} lead(s).")
    _print_json(batch.summary())


@leads_group.group("apply")
def leads_apply_group() -> None:
    """Apply approved actions (JobTread push or QUO queue)."""


@leads_apply_group.command("jobtread")
@click.option("--batch", "batch_id", default=None)
@click.option("--dry-run/--live", default=True, show_default=True)
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
def leads_apply_jobtread(batch_id: str | None, dry_run: bool, config_path: str | None) -> None:
    """Push approved leads to JobTread (needs JOBTREAD_GRANT_KEY for --live)."""
    pipeline = _get_pipeline(config_path)
    batch = _open_batch(pipeline, batch_id)
    org_id = pipeline.config.get("jobtread", {}).get("org_id", "22P6bRn5p6Pn")
    result = apply_jobtread(
        batch,
        org_id=org_id,
        ledger=pipeline.ledger,
        dry_run=dry_run,
    )
    _print_json(result)
    if result.get("pushed"):
        click.echo("\nNext: ideal-api leads approve-quo --all  then  ideal-api leads apply quo")


@leads_apply_group.command("quo")
@click.option("--batch", "batch_id", default=None)
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
def leads_apply_quo(batch_id: str | None, config_path: str | None) -> None:
    """Write QUO text queue JSON (does not send texts)."""
    pipeline = _get_pipeline(config_path)
    batch = _open_batch(pipeline, batch_id)
    path, queue = write_quo_queue(batch, pipeline.output_dir, ledger=pipeline.ledger)
    click.echo(f"QUO queue written: {path}")
    _print_json({"count": queue["count"], "skipped": queue.get("skipped", []), "path": str(path)})


@leads_group.command("approve-quo")
@click.option("--batch", "batch_id", default=None)
@click.option("--all", "all_ready", is_flag=True, default=False, help="Approve all JobTread-pushed leads with phone")
@click.option("--indices", default=None, help="Comma-separated indices")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
def leads_approve_quo(
    batch_id: str | None,
    all_ready: bool,
    indices: str | None,
    config_path: str | None,
) -> None:
    """Approve leads for QUO texting (after JobTread push)."""
    if not (all_ready or indices):
        raise click.ClickException("Specify --all or --indices")
    pipeline = _get_pipeline(config_path)
    batch = _open_batch(pipeline, batch_id)
    idx_list = _parse_indices(indices) if indices else None
    changed = batch.approve_quo(indices=idx_list, all_ready=all_ready)
    click.echo(f"Approved {changed} lead(s) for QUO.")
    _print_json(batch.summary())
    if changed:
        click.echo("\nNext: ideal-api leads apply quo")


@main.command("health")
@click.option("--tier", type=int, default=None, help="Probe tier 1 or 2 only")
@click.option("--fail-fast", is_flag=True, default=False, help="Stop on first failure")
@click.option("--write-report", is_flag=True, default=False, help="Save JSON report to data/output/")
@click.option("--require-all-free", is_flag=True, default=False, help="Exit 1 if any free API fails")
@click.option("--timeout", "timeout_s", default=45, show_default=True, help="Per-probe timeout (seconds)")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Print probe progress")
def health_check(
    tier: int | None,
    fail_fast: bool,
    write_report: bool,
    require_all_free: bool,
    verbose: bool,
    timeout_s: float,
) -> None:
    """Autonomous health check — probe every registered API integration."""
    report = run_health_check(tier=tier, fail_fast=fail_fast, verbose=verbose, timeout_s=timeout_s)
    if write_report:
        path = write_health_report(report)
        click.echo(f"Report: {path}")
    _print_json(report.to_dict())

    failed_free = [
        r for r in report.results
        if r.status == "failed" and not r.requires_key
    ]
    if require_all_free and failed_free:
        names = ", ".join(f"{r.group}/{r.name}" for r in failed_free)
        raise click.ClickException(f"Free API probe(s) failed: {names}")
    if report.failed and require_all_free:
        raise SystemExit(1)


@main.command("daily")
@click.option("--push-jobtread", is_flag=True, default=False, help="Push high-priority leads to JobTread (needs JOBTREAD_GRANT_KEY)")
@click.option("--dry-run/--live", default=True, show_default=True, help="JobTread push mode")
@click.option("--skip-yelp", is_flag=True, default=False, help="Skip Yelp (no IDEAL_YELP_KEY)")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True), help="pipeline.yaml path")
def daily_leads(push_jobtread: bool, dry_run: bool, skip_yelp: bool, config_path: str | None) -> None:
    """Run the full daily lead pipeline (NPPES, OpenFEMA, weather, gov → ledger + CSV)."""
    from pathlib import Path

    pipeline = DailyLeadPipeline(
        config_path=Path(config_path) if config_path else None,
    )
    result = pipeline.run(
        push_jobtread=push_jobtread,
        dry_run=dry_run,
        skip_yelp=skip_yelp,
    )
    _print_json(result)


@main.command("call", context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("group")
@click.argument("name")
def call_command(group: str, name: str) -> None:
    """Call an API: ideal-api call leads dentists --limit 5"""
    cmd = get_command(group, name)
    if not cmd:
        raise click.ClickException(
            f"Unknown command: {group} {name}. Run 'ideal-api list'."
        )
    try:
        kwargs = _parse_params(tuple(click.get_current_context().args))
        result = cmd.handler(**kwargs)
        _print_json(result)
    except click.ClickException:
        raise
    except Exception as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
