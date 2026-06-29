"""
CLI for the job-application review system.

Usage examples:
    # 1. One-time: drop resume.pdf + linkedin.pdf into job_reviewer/profile/
    #    then verify the agency slugs load:
    python -m job_reviewer agencies

    # 2. Scrape + score + tailor + flag (all three counties):
    python -m job_reviewer run

    # Limit to one county / agency, lower the flag bar:
    python -m job_reviewer run --county pinellas --flag-threshold 50

    # Skip the AI (lexical-only, no API cost):
    python -m job_reviewer run --no-ai

    # 3. See what's flagged for your review:
    python -m job_reviewer queue --min-score 60

    # 4. Export the review queue:
    python -m job_reviewer export --csv queue.csv --markdown queue.md

    # 5. Optional browser pre-fill (logs in, fills, STOPS before submit):
    python -m job_reviewer prefill --job-id <id>

    # Mark an item submitted/dismissed after you act on it:
    python -m job_reviewer mark <job-id> submitted
"""
from __future__ import annotations

import logging
import os

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger("job_reviewer")
console = Console()


@click.group()
@click.option("--db", "db_url", default=None, envvar="DATABASE_URL", help="SQLAlchemy DB URL")
@click.option("--debug", is_flag=True, default=False)
@click.pass_context
def cli(ctx: click.Context, db_url: str | None, debug: bool) -> None:
    """Review government job postings against your resume and flag the best fits."""
    ctx.ensure_object(dict)
    ctx.obj["db_url"] = db_url
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--county", "-c", multiple=True,
              type=click.Choice(["pasco", "hillsborough", "pinellas"]),
              help="Limit to these counties (default: all three)")
@click.option("--agency", "-a", multiple=True, help="Limit to these agency IDs")
@click.option("--keyword", "-k", multiple=True, help="Extra keyword filters (OR-matched)")
@click.option("--flag-threshold", default=60.0, show_default=True,
              help="Minimum fit score (0–100) to flag a job for review")
@click.option("--max-jobs", default=None, type=int, help="Cap jobs scraped per agency")
@click.option("--no-ai", is_flag=True, default=False,
              help="Disable Claude scoring/tailoring (lexical only, no API cost)")
@click.option("--no-packets", is_flag=True, default=False,
              help="Don't auto-draft application packets")
@click.pass_context
def run(ctx, county, agency, keyword, flag_threshold, max_jobs, no_ai, no_packets):
    """Scrape → score → tailor → flag jobs for your review."""
    from .pipeline import JobReviewPipeline

    if not no_ai and not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[yellow]No ANTHROPIC_API_KEY — falling back to lexical scoring.[/]")
        no_ai = True

    pipeline = JobReviewPipeline(db_url=ctx.obj["db_url"], use_ai=not no_ai)
    summary = pipeline.run(
        agency_ids=list(agency) or None,
        counties=list(county) or None,
        keywords=list(keyword) or None,
        flag_threshold=flag_threshold,
        max_jobs_per_agency=max_jobs,
        make_packets=not no_packets,
    )

    table = Table(title="Run summary", show_header=False)
    for key, val in summary.items():
        if key == "errors":
            continue
        table.add_row(key.replace("_", " ").title(), str(val))
    console.print(table)
    if summary["errors"]:
        console.print("[red]Errors:[/]")
        for e in summary["errors"]:
            console.print(f"  • {e['agency']}: {e['error']}")
    console.print(
        f"\n[green]{summary['jobs_flagged']} job(s) flagged.[/] "
        "Run [bold]python -m job_reviewer queue[/] to review them. "
        "Nothing was submitted."
    )


@cli.command()
@click.option("--min-score", default=0.0, help="Only show jobs at/above this fit score")
@click.option("--county", default=None, help="Filter by county")
@click.option("--status", "statuses", multiple=True, help="Filter by review status")
@click.option("--limit", default=50, show_default=True)
@click.pass_context
def queue(ctx, min_score, county, statuses, limit):
    """Show the review queue, ranked by fit score."""
    from .review import ReviewQueue

    from .storage import init_db

    init_db(ctx.obj["db_url"])
    jobs = ReviewQueue().list(
        min_score=min_score, statuses=list(statuses) or None, county=county, limit=limit
    )
    if not jobs:
        console.print("[yellow]Nothing in the queue yet. Run `job_reviewer run` first.[/]")
        return

    table = Table(title=f"Review queue ({len(jobs)})")
    table.add_column("Fit", justify="right")
    table.add_column("Rec")
    table.add_column("Title")
    table.add_column("Agency")
    table.add_column("Salary")
    table.add_column("Closes")
    table.add_column("Status")
    table.add_column("Job ID", overflow="fold")
    for j in jobs:
        table.add_row(
            f"{j.fit_score:.0f}" if j.fit_score is not None else "—",
            j.recommendation or "—",
            (j.title or "")[:40],
            (j.agency_name or "")[:24],
            (j.salary_raw or "")[:22],
            j.closing_date.strftime("%Y-%m-%d") if j.closing_date else "—",
            j.review_status,
            j.id,
        )
    console.print(table)
    console.print("\nDraft packets (if generated) are in [bold]job_reviewer/packets/[/].")


@cli.command()
@click.option("--csv", "csv_path", default=None, help="Write ranked CSV here")
@click.option("--markdown", "md_path", default=None, help="Write a Markdown digest here")
@click.option("--min-score", default=0.0)
@click.pass_context
def export(ctx, csv_path, md_path, min_score):
    """Export the review queue to CSV and/or Markdown."""
    from .review import ReviewQueue
    from .storage import init_db

    init_db(ctx.obj["db_url"])
    rq = ReviewQueue()
    if csv_path:
        console.print(f"[green]CSV:[/] {rq.export_csv(csv_path, min_score)}")
    if md_path:
        console.print(f"[green]Markdown:[/] {rq.export_markdown(md_path, min_score)}")
    if not csv_path and not md_path:
        console.print("Pass --csv and/or --markdown.")


@cli.command()
@click.argument("job_id")
@click.argument("status", type=click.Choice(
    ["new", "flagged", "prefilled", "reviewed", "submitted", "dismissed"]))
@click.pass_context
def mark(ctx, job_id, status):
    """Update a job's review status after you act on it."""
    from .review import ReviewQueue
    from .storage import init_db

    init_db(ctx.obj["db_url"])
    ok = ReviewQueue().set_status(job_id, status)
    console.print(f"[green]Marked {job_id} → {status}[/]" if ok else "[red]Job id not found.[/]")


@cli.command()
@click.option("--job-id", required=True, help="Job id from the queue")
@click.option("--headless", is_flag=True, default=False,
              help="Run the browser headless (default: visible so you can watch)")
@click.pass_context
def prefill(ctx, job_id, headless):
    """Open governmentjobs.com, log in, pre-fill the application — STOP before submit."""
    from pathlib import Path

    from .agents import ApplicationAgent
    from .profile_loader import ProfileLoader
    from .storage import Job, get_session, init_db
    from .tailor import ApplicationPacket

    init_db(ctx.obj["db_url"])
    with get_session() as session:
        job = session.get(Job, job_id)
        if not job:
            console.print("[red]Job id not found.[/]")
            return
        apply_url, packet_path, title = job.apply_url, job.packet_path, job.title

    if not apply_url:
        console.print("[red]This job has no apply URL on record.[/]")
        return

    console.print(f"[bold]Pre-filling:[/] {title}")
    console.print("[yellow]The agent NEVER submits. It stops at the review screen for you.[/]")

    profile = ProfileLoader(Path(__file__).parent / "profile").load()
    packet = None
    if packet_path and Path(packet_path).exists():
        packet = ApplicationPacket(
            job_source_id=job_id, job_title=title or "", agency_name="",
            cover_letter=_extract_cover_letter(Path(packet_path)),
        )

    agent = ApplicationAgent(profile, headless=headless)
    result = agent.prefill(apply_url, packet)
    color = "green" if result.ok else "red"
    console.print(f"[{color}]Stopped at: {result.stopped_at}[/] — {result.message}")
    if result.screenshot_path:
        console.print(f"Screenshot: {result.screenshot_path}")
    if result.ok:
        ReviewQueue_set(ctx.obj["db_url"], job_id, "prefilled")


def _extract_cover_letter(path) -> str:
    text = path.read_text(encoding="utf-8")
    if "## Cover letter" in text:
        return text.split("## Cover letter", 1)[1].split("##", 1)[0].strip()
    return ""


def ReviewQueue_set(db_url, job_id, status):
    from .review import ReviewQueue
    ReviewQueue().set_status(job_id, status)


@cli.command()
@click.pass_context
def agencies(ctx):
    """List configured agencies and their career-portal URLs to verify."""
    from .pipeline import CONFIG_DIR
    import yaml

    data = yaml.safe_load((CONFIG_DIR / "agencies.yaml").read_text())
    table = Table(title="Configured agencies")
    table.add_column("County")
    table.add_column("Agency")
    table.add_column("Career portal (verify this loads)")
    for a in data.get("agencies", []):
        url = a.get("base_url") or f"https://www.governmentjobs.com/careers/{a['slug']}"
        table.add_row(a.get("county", ""), a["name"], url)
    console.print(table)
    console.print("\n[yellow]Open each URL once and confirm it shows that employer's jobs. "
                  "Fix any slug in targets/agencies.yaml that 404s.[/]")


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
