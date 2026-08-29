"""
CLI entry point for the bid tracker.

Usage examples:
    # Weekly run across all configured sources (last 7 days)
    python -m bid_tracker run

    # Specific sources, last 14 days
    python -m bid_tracker run --source sam_gov fl_vbs --days 14

    # See what would qualify without writing packages or alerts
    python -m bid_tracker run --dry-run

    # Run continuously, once a week
    python -m bid_tracker watch --interval 7d

    # Send Slack alerts for new qualified bids
    python -m bid_tracker run --slack-webhook $SLACK_WEBHOOK_URL

    # List configured sources
    python -m bid_tracker sources

    # Export qualified opportunities to CSV
    python -m bid_tracker export --output qualified.csv
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

# Load environment variables from a .env file (CWD and the package dir) so
# ANTHROPIC_API_KEY, SAM_GOV_API_KEY, etc. are picked up without exporting them.
try:
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger(__name__)
console = Console()


def _make_pipeline(db_url, alert_cfg, output_dir=None):
    from .pipeline import BidPipeline
    return BidPipeline(db_url=db_url, alert_config=alert_cfg, output_dir=output_dir)


@click.group()
@click.option("--db", "db_url", default=None, envvar="DATABASE_URL", help="SQLAlchemy DB URL")
@click.option("--debug", is_flag=True, default=False)
@click.pass_context
def cli(ctx: click.Context, db_url: str | None, debug: bool) -> None:
    """Bid Tracker — public construction bidding tracker & submittal prep."""
    ctx.ensure_object(dict)
    ctx.obj["db_url"] = db_url
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--source", "-s", multiple=True, help="Source IDs to pull (default: all)")
@click.option("--days", "-d", default=7, show_default=True, help="Days to look back")
@click.option("--output-dir", "-o", default=None, help="Where to write bid packages")
@click.option("--no-packages", "build_packages", is_flag=True, default=True,
              help="Qualify only; don't build package folders")
@click.option("--dry-run", is_flag=True, default=False,
              help="Report what qualifies without writing packages or alerts")
@click.option("--slack-webhook", envvar="SLACK_WEBHOOK_URL", default=None,
              help="Slack webhook URL for qualified-bid alerts")
@click.pass_context
def run(ctx, source, days, output_dir, build_packages, dry_run, slack_webhook):
    """Pull sources, qualify opportunities, and build bid packages."""
    alert_channels = [{"type": "console"}]
    if slack_webhook:
        alert_channels.append({"type": "slack", "url": slack_webhook})

    pipeline = _make_pipeline(
        ctx.obj["db_url"], {"alert_channels": alert_channels}, output_dir
    )

    console.rule("[bold cyan]Starting bid tracker run")
    summary = pipeline.run(
        source_ids=list(source) or None,
        days_back=days,
        build_packages=build_packages,
        dry_run=dry_run,
    )

    console.rule("[bold cyan]Run complete")
    t = Table(show_header=False)
    t.add_column("Metric", style="bold")
    t.add_column("Value")
    t.add_row("Sources processed", str(summary["sources_processed"]))
    t.add_row("Opportunities found", str(summary["total_found"]))
    t.add_row("New (not in DB)", str(summary["total_new"]))
    t.add_row("[green]Qualified[/]", str(summary["total_qualified"]))
    t.add_row("Packages built", str(summary["packages_built"]))
    t.add_row("Alerts sent", str(summary["alerts_sent"]))
    if summary["errors"]:
        t.add_row("[red]Errors[/]", str(len(summary["errors"])))
    console.print(t)

    if summary["qualified"]:
        console.print("\n[bold green]Qualified opportunities:[/]")
        for title in summary["qualified"]:
            console.print(f"  • {title}")

    if summary["errors"]:
        for err in summary["errors"]:
            console.print(f"  [red]✗[/] {err['source']}: {err['error']}")
        sys.exit(1)


@cli.command()
@click.option("--interval", "-i", default="7d", show_default=True,
              help="Run interval: e.g. 24h, 7d, 1w")
@click.option("--source", "-s", multiple=True)
@click.option("--days", "-d", default=7)
@click.option("--slack-webhook", envvar="SLACK_WEBHOOK_URL", default=None)
@click.pass_context
def watch(ctx, interval, source, days, slack_webhook):
    """Run continuously on a schedule (default: weekly)."""
    hours = _parse_interval(interval)
    sleep_seconds = int(hours * 3600)
    console.print(f"[bold green]Watch mode:[/] running every {interval}")

    while True:
        ctx.invoke(run, source=source, days=days, slack_webhook=slack_webhook)
        console.print(f"Next run in {interval}. Sleeping …")
        time.sleep(sleep_seconds)


@cli.command()
@click.option("--output", "-o", default="qualified_opportunities.csv", show_default=True)
@click.option("--min-score", default=0.0, help="Minimum qualification score")
@click.option("--all", "include_all", is_flag=True, default=False,
              help="Include non-qualified opportunities too")
@click.pass_context
def export(ctx, output, min_score, include_all):
    """Export opportunities from the database to CSV."""
    import csv as _csv

    from .storage import Opportunity, get_session, init_db

    init_db(ctx.obj["db_url"])
    with get_session() as session:
        q = session.query(Opportunity).filter(Opportunity.qual_score >= min_score)
        if not include_all:
            q = q.filter(Opportunity.qualified.is_(True))
        opps = q.order_by(Opportunity.due_date.asc()).all()

        fields = [
            "solicitation_number", "title", "agency", "opportunity_type", "naics_code",
            "set_aside", "state", "city", "estimated_value", "posted_date", "due_date",
            "qual_score", "qualified", "status", "package_path", "source", "source_url",
        ]
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for o in opps:
                row = {fn: getattr(o, fn, None) for fn in fields}
                for df in ("posted_date", "due_date"):
                    if row.get(df):
                        row[df] = row[df].isoformat()
                writer.writerow(row)

        console.print(f"[green]Exported {len(opps)} opportunities to {output}[/]")


@cli.command()
@click.pass_context
def sources(ctx):
    """List all configured opportunity sources."""
    cfg_path = Path(__file__).parent / "targets" / "sources.yaml"
    data = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}

    t = Table(title="Configured Sources", show_header=True)
    t.add_column("ID", style="cyan")
    t.add_column("Name")
    t.add_column("Type", style="yellow")
    t.add_column("State")
    for s in data.get("sources", []):
        t.add_row(s["id"], s["name"], s.get("type", "rss"), s.get("state", "—"))
    console.print(t)


def _parse_interval(s: str) -> float:
    """Parse interval string like '24h', '7d', '1w' to hours."""
    s = s.lower().strip()
    if s.endswith("w"):
        return float(s[:-1]) * 24 * 7
    if s.endswith("d"):
        return float(s[:-1]) * 24
    if s.endswith("h"):
        return float(s[:-1])
    if s.endswith("m"):
        return float(s[:-1]) / 60
    return float(s)   # assume hours


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
