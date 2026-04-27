"""Quick query: last 5 permits issued in City of Tampa via ArcGIS REST API."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from rich.console import Console
from rich.table import Table

console = Console(width=120)

ARCGIS_URL = (
    "https://arcgis.tampagov.net/arcgis/rest/services"
    "/Planning/PermitsAll/FeatureServer/0/query"
)

# Demo fallback — Tampa permits from the demo dataset
DEMO_PERMITS = [
    {"date": "2026-02-14", "number": "BLD-2026-007780", "address": "4320 W Boy Scout Blvd",    "applicant": "Chick-fil-A Inc",          "type": "Commercial New Construction", "status": "Plan Review",          "value": "$2,450,000"},
    {"date": "2026-01-07", "number": "BLD-2026-004400", "address": "1601 E Hillsborough Ave",  "applicant": "Home Depot USA Inc",       "type": "Commercial New Construction", "status": "Application Received", "value": "$13,500,000"},
    {"date": "2025-11-18", "number": "BLD-2025-042100", "address": "3838 Henderson Blvd",      "applicant": "Publix Super Markets Inc",  "type": "Commercial New Construction", "status": "Permit Issued",        "value": "$7,200,000"},
    {"date": "2025-10-09", "number": "BLD-2025-039800", "address": "7400 W Hillsborough Ave",  "applicant": "Microsoft Corporation",    "type": "Commercial New Construction", "status": "Application Received", "value": "$490,000,000"},
    {"date": "2025-08-27", "number": "BLD-2025-035500", "address": "601 N Ashley Dr",          "applicant": "Target Corporation",       "type": "Commercial New Construction", "status": "Plan Review",          "value": "$5,600,000"},
]


def show_table(permits: list[dict], source: str) -> None:
    t = Table(title=f"Last 5 Permits — City of Tampa   [source: {source}]", show_lines=True)
    t.add_column("Filed Date",  style="cyan",    min_width=12)
    t.add_column("Permit #",    style="yellow",  min_width=20)
    t.add_column("Address",                      min_width=28)
    t.add_column("Applicant",                    min_width=26)
    t.add_column("Permit Type",                  min_width=30)
    t.add_column("Status",      style="green",   min_width=22)
    t.add_column("Est. Value",  style="magenta", min_width=14)
    for p in permits:
        t.add_row(p["date"], p["number"], p["address"],
                  p["applicant"], p["type"], p["status"], p["value"])
    console.print(t)


def g(attrs: dict, *keys: str) -> str:
    for k in keys:
        v = attrs.get(k)
        if v is not None and v != "" and str(v).upper() not in ("N/A", "NONE", "NULL"):
            return str(v)
    return "—"


def epoch_to_date(ms) -> str:
    if ms and isinstance(ms, (int, float)) and ms > 0:
        return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
    return "—"


def run_live() -> bool:
    params = {
        "where":             "1=1",
        "outFields":         "*",
        "resultRecordCount": 5,
        "orderByFields":     "APPLICATIONDATE DESC",
        "f":                 "json",
    }
    console.print("[cyan]Querying live City of Tampa ArcGIS API...[/]")
    try:
        resp = requests.get(ARCGIS_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        console.print(f"[yellow]Network error:[/] {exc}")
        return False

    if "error" in data:
        console.print(f"[yellow]ArcGIS error:[/] {data['error']}")
        return False

    features = data.get("features", [])
    if not features:
        console.print("[yellow]No features returned.[/]")
        return False

    rows = []
    for f in features:
        a = f.get("attributes", {})
        rows.append({
            "date":      epoch_to_date(a.get("APPLICATIONDATE")),
            "number":    g(a, "PERMITNUM", "PERMIT_NUM", "PERMITNUMBER", "RECORDID"),
            "address":   g(a, "ADDRESS", "SITEADDRESS", "FULLADDRESS", "JOBADDRESS"),
            "applicant": g(a, "APPLICANTNAME", "APPLICANT", "OWNERNAME"),
            "type":      g(a, "PERMITTYPE", "PERMIT_TYPE", "WORKTYPE"),
            "status":    g(a, "STATUSDESC", "STATUS", "PERMITSTATUS"),
            "value":     f"${float(a['ESTIMATEDVALUE']):,.0f}" if a.get("ESTIMATEDVALUE") else "—",
        })

    show_table(rows, "live — arcgis.tampagov.net")
    return True


if __name__ == "__main__":
    if not run_live():
        console.print("[yellow]Showing demo dataset (live API unreachable from this environment).[/]\n")
        show_table(DEMO_PERMITS, "demo dataset")
