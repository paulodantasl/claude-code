"""
Alert system for matched permits.

Supports:
- Console (rich) output
- Email (SMTP)
- Webhook (Slack, Discord, generic HTTP)
- CSV export
"""
from __future__ import annotations

import csv
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO
from typing import Any

import requests
from jinja2 import Template
from rich.console import Console
from rich.table import Table

from ..storage.models import Permit

logger = logging.getLogger(__name__)
console = Console()

# ── Email template ──────────────────────────────────────────────────────────

EMAIL_HTML_TEMPLATE = """
<html><body>
<h2>🏗️ New Permit Match: {{ company }}</h2>
<table border="1" cellpadding="6" style="border-collapse:collapse;">
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>County</td><td>{{ permit.county_name }}</td></tr>
  <tr><td>Permit #</td><td>{{ permit.permit_number }}</td></tr>
  <tr><td>Type</td><td>{{ permit.permit_type }}</td></tr>
  <tr><td>Status</td><td>{{ permit.status }}</td></tr>
  <tr><td>Address</td><td>{{ permit.address }}, {{ permit.city }} {{ permit.zip_code }}</td></tr>
  <tr><td>Applicant</td><td>{{ permit.applicant_name }}</td></tr>
  <tr><td>Owner</td><td>{{ permit.owner_name }}</td></tr>
  <tr><td>Description</td><td>{{ permit.description }}</td></tr>
  <tr><td>Est. Value</td><td>${{ '{:,.0f}'.format(permit.estimated_value) if permit.estimated_value else 'N/A' }}</td></tr>
  <tr><td>Filed Date</td><td>{{ permit.filed_date.strftime('%Y-%m-%d') if permit.filed_date else 'N/A' }}</td></tr>
  <tr><td>Match Score</td><td>{{ '%.0f' % permit.match_score }}%</td></tr>
</table>
<p><a href="{{ permit.source_url }}">View on portal</a></p>
</body></html>
"""

SLACK_TEMPLATE = """*New Permit Match: {{ company }}* ({{ '%.0f' % permit.match_score }}% confidence)
> *Address:* {{ permit.address }}, {{ permit.city }}
> *Type:* {{ permit.permit_type }} | *Status:* {{ permit.status }}
> *Applicant:* {{ permit.applicant_name }}
> *Est. Value:* ${{ '{:,.0f}'.format(permit.estimated_value) if permit.estimated_value else 'N/A' }}
> *Filed:* {{ permit.filed_date.strftime('%Y-%m-%d') if permit.filed_date else 'N/A' }}
> *County:* {{ permit.county_name }} | Permit #{{ permit.permit_number }}
"""


class AlertManager:
    """Dispatches alerts for matched permits via configured channels."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._channels = config.get("alert_channels", [])

    def send(self, permit: Permit) -> None:
        if not self._channels:
            self._print_console(permit)
            return

        for channel in self._channels:
            try:
                ctype = channel.get("type")
                if ctype == "console":
                    self._print_console(permit)
                elif ctype == "email":
                    self._send_email(permit, channel)
                elif ctype in ("slack", "webhook"):
                    self._send_webhook(permit, channel)
                elif ctype == "csv":
                    self._append_csv(permit, channel)
            except Exception as exc:
                logger.error("Alert channel %s failed: %s", channel.get("type"), exc)

    def send_batch(self, permits: list[Permit]) -> None:
        for p in permits:
            self.send(p)

    # ── Channel implementations ─────────────────────────────────────────────

    def _print_console(self, permit: Permit) -> None:
        t = Table(title=f"[bold green]MATCH: {permit.matched_company_name}[/]", show_header=True)
        t.add_column("Field", style="bold")
        t.add_column("Value")

        rows = [
            ("County", permit.county_name),
            ("Permit #", permit.permit_number or ""),
            ("Type", permit.permit_type or ""),
            ("Status", permit.status or ""),
            ("Address", f"{permit.address}, {permit.city} {permit.zip_code}"),
            ("Applicant", permit.applicant_name or ""),
            ("Owner", permit.owner_name or ""),
            ("Description", (permit.description or "")[:120]),
            ("Est. Value", f"${permit.estimated_value:,.0f}" if permit.estimated_value else "N/A"),
            ("Filed", permit.filed_date.strftime("%Y-%m-%d") if permit.filed_date else "N/A"),
            ("Match Score", f"{permit.match_score:.0f}%" if permit.match_score else ""),
            ("Source", permit.source_url or ""),
        ]
        for label, value in rows:
            t.add_row(label, str(value))

        console.print(t)

    def _send_email(self, permit: Permit, channel: dict) -> None:
        smtp_host = channel.get("smtp_host", os.environ.get("SMTP_HOST", "smtp.gmail.com"))
        smtp_port = int(channel.get("smtp_port", os.environ.get("SMTP_PORT", 587)))
        smtp_user = channel.get("smtp_user", os.environ.get("SMTP_USER", ""))
        smtp_pass = channel.get("smtp_pass", os.environ.get("SMTP_PASS", ""))
        to_addrs = channel.get("to", [])
        from_addr = channel.get("from", smtp_user)

        if not to_addrs:
            logger.warning("Email alert: no 'to' addresses configured")
            return

        html = Template(EMAIL_HTML_TEMPLATE).render(
            company=permit.matched_company_name, permit=permit
        )
        subject = f"Permit Alert: {permit.matched_company_name} in {permit.county_name}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, to_addrs, msg.as_string())

        logger.info("Email sent to %s for permit %s", to_addrs, permit.permit_number)

    def _send_webhook(self, permit: Permit, channel: dict) -> None:
        url = channel.get("url", os.environ.get("WEBHOOK_URL", ""))
        if not url:
            logger.warning("Webhook: no URL configured")
            return

        ctype = channel.get("type", "webhook")
        if ctype == "slack":
            text = Template(SLACK_TEMPLATE).render(
                company=permit.matched_company_name, permit=permit
            )
            payload = {"text": text}
        else:
            payload = {
                "event": "permit_match",
                "company": permit.matched_company_name,
                "match_score": permit.match_score,
                "permit": {
                    "id": permit.id,
                    "permit_number": permit.permit_number,
                    "county": permit.county_name,
                    "address": permit.address,
                    "city": permit.city,
                    "type": permit.permit_type,
                    "status": permit.status,
                    "applicant": permit.applicant_name,
                    "estimated_value": permit.estimated_value,
                    "filed_date": permit.filed_date.isoformat() if permit.filed_date else None,
                },
            }

        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Webhook sent for permit %s", permit.permit_number)

    def _append_csv(self, permit: Permit, channel: dict) -> None:
        path = channel.get("path", "permit_matches.csv")
        fieldnames = [
            "id", "permit_number", "county_name", "permit_type", "status",
            "address", "city", "state", "zip_code", "applicant_name",
            "owner_name", "contractor_name", "description", "estimated_value",
            "filed_date", "matched_company_name", "match_score", "source_url", "scraped_at",
        ]
        write_header = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            row = {fn: getattr(permit, fn, None) for fn in fieldnames}
            if permit.filed_date:
                row["filed_date"] = permit.filed_date.isoformat()
            if permit.scraped_at:
                row["scraped_at"] = permit.scraped_at.isoformat()
            writer.writerow(row)
