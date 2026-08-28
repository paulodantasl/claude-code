from __future__ import annotations

import json
import sys
from typing import Any

import click

from ideal_apis.config import get_settings
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
    for name, configured in fields:
        status = "set" if configured else "missing"
        click.echo(f"{name:<20} {status}")


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
