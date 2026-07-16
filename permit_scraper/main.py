"""
CLI entry point for the permit scraper.

Usage examples:
    # Scrape all configured counties, last 7 days
    python -m permit_scraper run

    # Scrape specific counties, last 30 days
    python -m permit_scraper run --county miami_dade broward --days 30

    # Force AI agent for complex portals
    python -m permit_scraper run --county palm_beach --ai-agent

    # Watch for specific companies only
    python -m permit_scraper run --days 14 --company amazon publix

    # Continuous mode: run every 24 hours
    python -m permit_scraper watch --interval 24h

    # Export all matched permits to CSV
    python -m permit_scraper export --output matches.csv

    # List all known counties
    python -m permit_scraper counties
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger(__name__)
console = Console()


def _make_pipeline(db_url: str | None, alert_cfg: dict | None):
    from .pipeline import PermitPipeline
    return PermitPipeline(db_url=db_url, alert_config=alert_cfg)


@click.group()
@click.option("--db", "db_url", default=None, envvar="DATABASE_URL", help="SQLAlchemy DB URL")
@click.option("--debug", is_flag=True, default=False)
@click.pass_context
def cli(ctx: click.Context, db_url: str | None, debug: bool) -> None:
    """Permit Scraper — early intelligence on commercial construction permits."""
    ctx.ensure_object(dict)
    ctx.obj["db_url"] = db_url
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--county", "-c", multiple=True, help="County IDs to scrape (default: all)")
@click.option("--days", "-d", default=7, show_default=True, help="Days to look back")
@click.option("--permit-type", "-t", multiple=True, help="Filter by permit type keyword")
@click.option("--company", multiple=True, help="Company IDs to watch (default: watch_list)")
@click.option("--ai-agent", "use_ai_agent", is_flag=True, default=False,
              help="Force AI agent (Claude) for portal navigation")
@click.option("--min-score", default=85.0, show_default=True,
              help="Minimum fuzzy match score (0–100) to record a company hit")
@click.option("--slack-webhook", envvar="SLACK_WEBHOOK_URL", default=None,
              help="Slack webhook URL for match alerts")
@click.option("--csv-output", default=None, help="Append matched permits to this CSV file")
@click.option("--google-sheet", "google_sheet", is_flag=True, default=False,
              help="Export results to Google Sheets/Drive (requires GOOGLE_SERVICE_ACCOUNT_FILE "
                   "or GOOGLE_OAUTH_CLIENT_FILE env var)")
@click.pass_context
def run(
    ctx: click.Context,
    county: tuple[str, ...],
    days: int,
    permit_type: tuple[str, ...],
    company: tuple[str, ...],
    use_ai_agent: bool,
    min_score: float,
    slack_webhook: str | None,
    csv_output: str | None,
    google_sheet: bool,
) -> None:
    """Scrape permit portals and match against the company watch list."""
    alert_channels: list[dict] = [{"type": "console"}]
    if slack_webhook:
        alert_channels.append({"type": "slack", "url": slack_webhook})
    if csv_output:
        alert_channels.append({"type": "csv", "path": csv_output})

    pipeline = _make_pipeline(ctx.obj["db_url"], {"alert_channels": alert_channels})

    console.rule("[bold cyan]Starting permit scrape")
    summary = pipeline.run(
        county_ids=list(county) or None,
        days_back=days,
        permit_types=list(permit_type) or None,
        use_ai_agent=use_ai_agent,
        min_match_score=min_score,
        export_to_google=google_sheet,
    )

    console.rule("[bold cyan]Run complete")
    t = Table(show_header=False)
    t.add_column("Metric", style="bold")
    t.add_column("Value")
    t.add_row("Counties processed", str(summary["counties_processed"]))
    t.add_row("Permits found", str(summary["total_permits_found"]))
    t.add_row("New (not in DB)", str(summary["total_new"]))
    t.add_row("Company matches", str(summary["total_matched"]))
    t.add_row("Alerts sent", str(summary["alerts_sent"]))
    if summary.get("google_sheet_url"):
        t.add_row("[green]Google Sheet[/]", summary["google_sheet_url"])
    if summary["errors"]:
        t.add_row("[red]Errors[/]", str(len(summary["errors"])))
    console.print(t)

    if summary["errors"]:
        for err in summary["errors"]:
            console.print(f"  [red]✗[/] {err['county']}: {err['error']}")
        sys.exit(1)


@cli.command()
@click.option("--interval", "-i", default="24h", show_default=True,
              help="Run interval: e.g. 6h, 12h, 24h")
@click.option("--county", "-c", multiple=True)
@click.option("--days", "-d", default=2)
@click.option("--slack-webhook", envvar="SLACK_WEBHOOK_URL", default=None)
@click.pass_context
def watch(ctx: click.Context, interval: str, county: tuple, days: int, slack_webhook: str | None) -> None:
    """Run continuously on a schedule."""
    hours = _parse_interval(interval)
    sleep_seconds = int(hours * 3600)

    console.print(f"[bold green]Watch mode:[/] running every {interval}")

    while True:
        ctx.invoke(run, county=county, days=days, slack_webhook=slack_webhook)
        console.print(f"Next run in {interval}. Sleeping …")
        time.sleep(sleep_seconds)


@cli.command()
@click.option("--output", "-o", default="permit_matches.csv", show_default=True)
@click.option("--company", "-c", default=None, help="Filter by company ID")
@click.option("--county", default=None)
@click.option("--min-score", default=85.0)
@click.option("--google-sheet", "google_sheet", is_flag=True, default=False,
              help="Also export to Google Sheets/Drive")
@click.pass_context
def export(ctx: click.Context, output: str, company: str | None, county: str | None,
           min_score: float, google_sheet: bool) -> None:
    """Export matched permits from the database to a CSV file."""
    from .storage import Permit, get_session

    with get_session() as session:
        q = session.query(Permit).filter(Permit.match_score >= min_score)
        if company:
            q = q.filter(Permit.matched_company_id == company)
        if county:
            q = q.filter(Permit.county_id == county)
        permits = q.order_by(Permit.filed_date.desc()).all()

    import csv as _csv
    fields = [
        "permit_number", "county_name", "permit_type", "status",
        "address", "city", "state", "zip_code",
        "applicant_name", "owner_name", "contractor_name",
        "description", "estimated_value", "filed_date",
        "matched_company_name", "match_score", "source_url", "scraped_at",
    ]
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for p in permits:
            row = {fn: getattr(p, fn, None) for fn in fields}
            for date_field in ("filed_date", "scraped_at"):
                v = row[date_field]
                if v:
                    row[date_field] = v.isoformat()
            writer.writerow(row)

    console.print(f"[green]Exported {len(permits)} records to {output}[/]")

    if google_sheet:
        try:
            from .notifications.google_drive import GoogleDriveExporter
            # Build display rows for the sheet
            sheet_rows = []
            for p in permits:
                sheet_rows.append({
                    "filed_date":      p.filed_date.strftime("%Y-%m-%d") if p.filed_date else "",
                    "permit_number":   p.permit_number or "",
                    "county":          p.county_name or "",
                    "city":            p.city or "",
                    "address":         p.address or "",
                    "zip_code":        p.zip_code or "",
                    "permit_type":     p.permit_type or "",
                    "status":          p.status or "",
                    "applicant_name":  p.applicant_name or "",
                    "owner_name":      p.owner_name or "",
                    "contractor_name": p.contractor_name or "",
                    "description":     p.description or "",
                    "est_value":       f"${p.estimated_value:,.0f}" if p.estimated_value else "",
                    "sqft":            f"{int(p.total_sqft):,}" if p.total_sqft else "",
                    "parcel_number":   p.parcel_number or "",
                    "matched_company": p.matched_company_name or "—",
                    "match_score":     f"{p.match_score:.0f}%" if p.match_score else "—",
                })
            exporter = GoogleDriveExporter.from_env()
            url = exporter.export_matches(matched_rows=sheet_rows)
            console.print(f"[green]Google Sheet created:[/] {url}")
        except Exception as exc:
            console.print(f"[red]Google Drive export failed:[/] {exc}")


@cli.command("property-appraisers")
@click.option("--county", "-c", multiple=True, help="County IDs (default: all supported)")
@click.option("--days", "-d", default=90, show_default=True, help="Days back for recent sales")
@click.option("--no-cross-ref", "cross_reference", is_flag=True, default=True,
              help="Skip cross-referencing sales against permit DB")
@click.pass_context
def property_appraisers(ctx: click.Context, county: tuple, days: int, cross_reference: bool) -> None:
    """Scrape property appraiser data and cross-reference with permits."""
    pipeline = _make_pipeline(ctx.obj["db_url"], None)
    console.rule("[bold cyan]Scraping property appraisers")
    summary = pipeline.run_property_appraisers(
        county_ids=list(county) or None,
        days_back=days,
        cross_reference=cross_reference,
    )
    console.rule("[bold cyan]Complete")
    t = Table(show_header=False)
    t.add_column("Metric", style="bold")
    t.add_column("Value")
    t.add_row("Properties found", str(summary["properties_found"]))
    t.add_row("Permit cross-references updated", str(summary["cross_references"]))
    if summary["errors"]:
        t.add_row("[red]Errors[/]", str(len(summary["errors"])))
    console.print(t)


@cli.command()
@click.pass_context
def counties(ctx: click.Context) -> None:
    """List all configured counties and their scraper types."""
    cfg_path = Path(__file__).parent / "targets" / "counties.yaml"
    data = yaml.safe_load(cfg_path.read_text())

    t = Table(title="Configured Counties", show_header=True)
    t.add_column("ID", style="cyan")
    t.add_column("Name")
    t.add_column("State")
    t.add_column("Type", style="yellow")
    t.add_column("Open Data?", style="green")

    for c in data.get("targets", []):
        t.add_row(
            c["id"],
            c["name"],
            c.get("state", ""),
            c.get("type", "accela"),
            "✓" if c.get("open_data_url") else "",
        )
    console.print(t)


@cli.command()
@click.option("--config-dir", default=None,
              help="Dir with tracked_permits.yaml / field_managers.yaml / counties.yaml")
@click.option("--state-file", default="permit_monitor_state.json", show_default=True,
              help="JSON file holding last-known permit snapshots + event log")
@click.option("--interval", "-i", default=None,
              help="Run continuously every e.g. 30m, 6h (omit for a single pass)")
@click.option("--dry-run", is_flag=True, default=False,
              help="Render notifications without actually sending them")
@click.option("--notify-first-seen", is_flag=True, default=False,
              help="Also notify the first time a permit is seen (default: silent baseline)")
@click.option("--lookback-days", default=180, show_default=True,
              help="Bulk-scrape lookback for portals without direct record lookup")
def monitor(
    config_dir: str | None,
    state_file: str,
    interval: str | None,
    dry_run: bool,
    notify_first_seen: bool,
    lookback_days: int,
) -> None:
    """Monitor tracked pending permits for status updates and notify field managers."""
    from .monitoring import build_monitor

    mon = build_monitor(
        config_dir=config_dir,
        state_file=state_file,
        dry_run=dry_run,
        notify_on_first_seen=notify_first_seen,
        lookback_days=lookback_days,
    )

    n_tracked = len(mon.config.active_tracked())
    console.print(
        f"[bold cyan]Monitoring {n_tracked} tracked permit(s)[/]"
        + (" [yellow](dry-run)[/]" if dry_run else "")
    )
    for w in mon.config.warnings:
        console.print(f"  [yellow]![/] {w}")
    if n_tracked == 0:
        console.print("[yellow]No active tracked permits — edit targets/tracked_permits.yaml[/]")
        return

    def _print_summary(summary: dict) -> None:
        t = Table(show_header=False)
        t.add_column("Metric", style="bold")
        t.add_column("Value")
        t.add_row("Checked", str(summary["checked"]))
        t.add_row("Found on portal", str(summary["found"]))
        t.add_row("Not found this run", str(summary["missing"]))
        t.add_row("New baselines", str(summary["baselined"]))
        t.add_row("[green]Updates detected[/]", str(summary["updates"]))
        t.add_row("Notifications sent", str(summary["notifications_sent"]))
        if summary["notification_failures"]:
            t.add_row("[red]Notify failures[/]", str(summary["notification_failures"]))
        if summary["errors"]:
            t.add_row("[red]Errors[/]", str(len(summary["errors"])))
        console.print(t)
        for err in summary["errors"]:
            console.print(f"  [red]✗[/] {err}")

    if interval:
        hours = _parse_interval(interval)
        seconds = int(hours * 3600)
        console.print(f"[bold green]Watch mode:[/] checking every {interval}. Ctrl-C to stop.")
        try:
            while True:
                summary = mon.run_once()
                console.rule(f"[cyan]Pass complete — next check in {interval}")
                _print_summary(summary)
                time.sleep(seconds)
        except KeyboardInterrupt:
            console.print("\n[bold]Stopped.[/]")
    else:
        summary = mon.run_once()
        console.rule("[bold cyan]Monitor pass complete")
        _print_summary(summary)


@cli.command()
@click.option("--config-dir", default=None)
@click.option("--state-file", default="permit_monitor_state.json", show_default=True)
def tracked(config_dir: str | None, state_file: str) -> None:
    """List tracked permits and their last-known status."""
    from pathlib import Path as _Path

    from .monitoring import JsonStateStore, load_config

    cfg = load_config(config_dir=_Path(config_dir) if config_dir else None)
    store = JsonStateStore(state_file)
    store.load()

    t = Table(title="Tracked Permits", show_header=True)
    t.add_column("Permit #", style="cyan")
    t.add_column("Project")
    t.add_column("County")
    t.add_column("Cat.", style="yellow")
    t.add_column("Managers")
    t.add_column("Last Status", style="green")
    t.add_column("Phase")

    for p in cfg.tracked:
        snap = store.get(p.key)
        managers = ", ".join(m.name for m in cfg.managers_for(p)) or "[red]none[/]"
        t.add_row(
            p.permit_number,
            (p.project_name or "")[:32],
            p.county,
            (p.category or "")[:4],
            managers,
            (snap.status if snap else "—") or "—",
            (snap.phase if snap else "—"),
        )
    console.print(t)


@cli.command()
@click.option("--county", "-c", multiple=True, help="County IDs to scan (default: all)")
@click.option("--days", "-d", default=30, show_default=True, help="Days of permits to scan")
@click.option("--config-dir", default=None,
              help="Dir with leads.yaml / counties.yaml")
@click.option("--state-file", default="permit_leads_state.json", show_default=True,
              help="JSON dedupe store so each permit becomes a lead only once")
@click.option("--output", "-o", default="permit_leads.csv", show_default=True,
              help="CSV call-list path (new leads are appended)")
@click.option("--google-sheet", is_flag=True, default=False,
              help="Also push new leads to Google Sheets (needs Drive creds)")
@click.option("--enrich", is_flag=True, default=False,
              help="Enrich GC/owner contacts via DBPR + property appraiser "
                   "(also honoured if enabled in leads.yaml)")
@click.option("--interval", "-i", default=None,
              help="Run continuously every e.g. 6h, 24h (omit for a single pass)")
def leads(
    county: tuple[str, ...],
    days: int,
    config_dir: str | None,
    state_file: str,
    output: str,
    google_sheet: bool,
    enrich: bool,
    interval: str | None,
) -> None:
    """Scan portals for newly ISSUED permits and export GC/owner sales leads."""
    from .leads import build_pipeline

    pipe = build_pipeline(config_dir=config_dir, state_file=state_file, enrich=enrich)
    if pipe.enricher is not None:
        console.print("[cyan]Contact enrichment enabled[/] (DBPR / property appraiser)")
    if not pipe.counties:
        console.print("[yellow]No counties configured in targets/counties.yaml[/]")
        return

    def _do_pass() -> dict:
        summary = pipe.run(
            county_ids=list(county) or None,
            days_back=days,
            csv_path=output,
            google_sheet=google_sheet,
        )
        t = Table(show_header=False)
        t.add_column("Metric", style="bold")
        t.add_column("Value")
        t.add_row("Counties scanned", str(summary["counties_processed"]))
        t.add_row("Permits scanned", str(summary["permits_scanned"]))
        t.add_row("Qualified (issued + in scope)", str(summary["qualified"]))
        t.add_row("[green]New leads[/]", str(summary["new_leads"]))
        t.add_row("Duplicates skipped", str(summary["duplicates"]))
        if summary.get("enriched"):
            t.add_row("Contacts enriched", str(summary["enriched"]))
        if summary["csv_path"]:
            t.add_row("CSV", summary["csv_path"])
        if summary["google_sheet_url"]:
            t.add_row("[green]Google Sheet[/]", summary["google_sheet_url"])
        if summary["errors"]:
            t.add_row("[red]Errors[/]", str(len(summary["errors"])))
        console.print(t)
        for row in summary["new_lead_rows"][:15]:
            console.print(
                f"  [green]•[/] {row['issued_date'] or '—'} {row['permit_number']} "
                f"[{row['category']}] {row['project_address'] or ''} "
                f"— GC: {row['gc_name'] or '—'} | Owner: {row['owner_name'] or '—'}"
            )
        for err in summary["errors"]:
            console.print(f"  [red]✗[/] {err['county']}: {err['error']}")
        return summary

    if interval:
        hours = _parse_interval(interval)
        seconds = int(hours * 3600)
        console.print(f"[bold green]Lead watch:[/] scanning every {interval}. Ctrl-C to stop.")
        try:
            while True:
                _do_pass()
                console.rule(f"[cyan]Next scan in {interval}")
                time.sleep(seconds)
        except KeyboardInterrupt:
            console.print("\n[bold]Stopped.[/]")
    else:
        console.rule("[bold cyan]Scanning for newly issued permits")
        _do_pass()


def _parse_interval(s: str) -> float:
    """Parse interval string like '6h', '30m' to hours."""
    s = s.lower().strip()
    if s.endswith("h"):
        return float(s[:-1])
    if s.endswith("m"):
        return float(s[:-1]) / 60
    return float(s)   # assume hours


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
