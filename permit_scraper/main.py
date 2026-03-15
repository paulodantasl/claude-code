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
@click.pass_context
def export(ctx: click.Context, output: str, company: str | None, county: str | None, min_score: float) -> None:
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
