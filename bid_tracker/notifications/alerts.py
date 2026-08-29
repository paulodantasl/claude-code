"""
Alert system for qualified opportunities.

Supports:
- Console (rich) output
- Email (SMTP)
- Webhook (Slack, Discord, generic HTTP)
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests
from jinja2 import Template
from rich.console import Console
from rich.panel import Panel

from ..storage.models import Opportunity

logger = logging.getLogger(__name__)
console = Console()

EMAIL_HTML_TEMPLATE = Template(
    """
<html><body>
<h2>🏗️ New qualified bid: {{ opp.title }}</h2>
<p><b>Score:</b> {{ '%.0f' % opp.qual_score }}/100</p>
<table border="1" cellpadding="6" style="border-collapse:collapse;">
  <tr><td>Agency</td><td>{{ opp.agency }}</td></tr>
  <tr><td>Solicitation #</td><td>{{ opp.solicitation_number }}</td></tr>
  <tr><td>Type</td><td>{{ opp.opportunity_type }}</td></tr>
  <tr><td>Location</td><td>{{ opp.city }} {{ opp.state }}</td></tr>
  <tr><td>Est. value</td><td>{{ '${:,.0f}'.format(opp.estimated_value) if opp.estimated_value else 'N/A' }}</td></tr>
  <tr><td>Due</td><td>{{ opp.due_date.strftime('%Y-%m-%d %H:%M') if opp.due_date else 'N/A' }}</td></tr>
</table>
<p>Package: {{ opp.package_path }}</p>
<p><a href="{{ opp.source_url }}">View solicitation</a></p>
</body></html>
"""
)

SLACK_TEMPLATE = Template(
    """*New qualified bid: {{ opp.title }}* ({{ '%.0f' % opp.qual_score }}/100)
> *Agency:* {{ opp.agency }}
> *Type:* {{ opp.opportunity_type }} | *Solicitation:* {{ opp.solicitation_number or '—' }}
> *Location:* {{ opp.city or '' }} {{ opp.state or '' }}
> *Est. value:* {{ '${:,.0f}'.format(opp.estimated_value) if opp.estimated_value else 'N/A' }}
> *Due:* {{ opp.due_date.strftime('%Y-%m-%d %H:%M') if opp.due_date else 'N/A' }}
> *Package:* {{ opp.package_path }}
> {{ opp.source_url or '' }}
"""
)


class AlertManager:
    """Dispatches alerts for qualified opportunities via configured channels."""

    def __init__(self, config: dict[str, Any]):
        self.config = config or {}
        self._channels = self.config.get("alert_channels", [])

    def send(self, opp: Opportunity) -> None:
        if not self._channels:
            self._print_console(opp)
            return
        for channel in self._channels:
            try:
                ctype = channel.get("type")
                if ctype == "console":
                    self._print_console(opp)
                elif ctype == "email":
                    self._send_email(opp, channel)
                elif ctype in ("slack", "webhook"):
                    self._send_webhook(opp, channel)
            except Exception as exc:
                logger.error("Alert channel %s failed: %s", channel.get("type"), exc)

    def _print_console(self, opp: Opportunity) -> None:
        value = f"${opp.estimated_value:,.0f}" if opp.estimated_value else "N/A"
        due = opp.due_date.strftime("%Y-%m-%d %H:%M") if opp.due_date else "N/A"
        body = (
            f"[bold]{opp.title}[/]\n"
            f"Agency: {opp.agency or '—'}\n"
            f"Type: {opp.opportunity_type or '—'}  |  Sol #: {opp.solicitation_number or '—'}\n"
            f"Location: {opp.city or ''} {opp.state or ''}  |  Est. value: {value}\n"
            f"Due: {due}\n"
            f"Package: {opp.package_path or '—'}\n"
            f"{opp.source_url or ''}"
        )
        console.print(Panel(body, title=f"🏗️ Qualified bid ({opp.qual_score:.0f}/100)", border_style="green"))

    def _send_webhook(self, opp: Opportunity, channel: dict) -> None:
        url = channel.get("url")
        if not url:
            return
        text = SLACK_TEMPLATE.render(opp=opp)
        requests.post(url, json={"text": text}, timeout=15).raise_for_status()

    def _send_email(self, opp: Opportunity, channel: dict) -> None:
        host = channel.get("host")
        to_addrs = channel.get("to", [])
        if not host or not to_addrs:
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Qualified bid: {opp.title} ({opp.qual_score:.0f}/100)"
        msg["From"] = channel.get("from", channel.get("user", ""))
        msg["To"] = ", ".join(to_addrs)
        msg.attach(MIMEText(EMAIL_HTML_TEMPLATE.render(opp=opp), "html"))

        with smtplib.SMTP(host, channel.get("port", 587)) as server:
            server.starttls()
            if channel.get("user"):
                server.login(channel["user"], channel.get("password", ""))
            server.sendmail(msg["From"], to_addrs, msg.as_string())
