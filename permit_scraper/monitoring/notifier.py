"""
Field-manager notifications for permit status updates.

A :class:`StatusEvent` is rendered once, then delivered to every assigned field
manager over each of that manager's configured channels:

  console  — always available (plain print; uses rich if installed)
  sms      — Twilio REST API, or a generic SMS webhook (great for "instant")
  slack    — Slack incoming webhook (per-manager or a global default)
  email    — SMTP
  webhook  — generic JSON POST (Teams, Zapier, your own dispatcher)

Set ``dry_run=True`` to render and record notifications without sending — the
CLI ``--dry-run`` flag and the test-suite use this. Delivery is best-effort and
per-channel: one failing channel never blocks the others, and every attempt is
recorded on the event for the audit log.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests

from .models import FieldManager, StatusEvent
from .status import Phase, describe_phase

logger = logging.getLogger(__name__)

_PRIORITY_TAG = {"high": "⚠️ ACTION REQUIRED", "normal": "🔔 Update"}
_DIRECTION_TAG = {
    "forward": "advanced",
    "backward": "moved back",
    "attention": "needs attention",
    "lateral": "updated",
    "first_seen": "now tracked",
}


# ── Rendering ───────────────────────────────────────────────────────────────


def render_subject(event: StatusEvent) -> str:
    tag = _PRIORITY_TAG.get(event.priority, "Update")
    label = event.project_name or event.permit_number
    return f"[{tag}] {label} — {event.new_status or describe_phase(Phase(event.new_phase))}"


def render_sms(event: StatusEvent) -> str:
    """Short single-message text (<~320 chars) for SMS."""
    tag = "ACTION REQUIRED: " if event.priority == "high" else ""
    label = event.project_name or event.permit_number
    transition = (
        f"{event.old_status or '—'} -> {event.new_status or '—'}"
        if event.new_status
        else _DIRECTION_TAG.get(event.direction, "updated")
    )
    parts = [
        f"{tag}Permit {event.permit_number} ({label})",
        f"{transition}",
        f"{event.county_name or event.county}",
    ]
    if event.source_url:
        parts.append(event.source_url)
    return " | ".join(parts)


def render_text(event: StatusEvent) -> str:
    """Plain multi-line body for console / email fallback."""
    lines = [
        render_subject(event),
        "",
        f"Project : {event.project_name or '—'}",
        f"Permit  : {event.permit_number}",
        f"County  : {event.county_name or event.county}",
        f"Category: {event.category or '—'}",
        f"Change  : status {_DIRECTION_TAG.get(event.direction, 'updated')} "
        f"({event.old_phase} -> {event.new_phase})",
    ]
    for ch in event.changes:
        lines.append(f"   • {ch.field}: {ch.old!r} -> {ch.new!r}")
    if event.source_url:
        lines.append(f"Portal  : {event.source_url}")
    lines.append(f"Detected: {event.detected_at}")
    return "\n".join(lines)


def render_slack(event: StatusEvent) -> dict[str, Any]:
    tag = _PRIORITY_TAG.get(event.priority, "Update")
    label = event.project_name or event.permit_number
    change_lines = "\n".join(f"• *{c.field}*: {c.old} → {c.new}" for c in event.changes)
    text = (
        f"*{tag}: {label}*\n"
        f"> *Permit:* {event.permit_number}  |  *County:* {event.county_name or event.county}\n"
        f"> *Category:* {event.category or '—'}\n"
        f"{change_lines}\n"
        + (f"> <{event.source_url}|View on portal>" if event.source_url else "")
    )
    return {"text": text}


def render_email_html(event: StatusEvent) -> str:
    rows = "".join(
        f"<tr><td style='padding:4px 10px'>{c.field}</td>"
        f"<td style='padding:4px 10px'>{c.old}</td>"
        f"<td style='padding:4px 10px'><b>{c.new}</b></td></tr>"
        for c in event.changes
    )
    color = "#b00020" if event.priority == "high" else "#0b6b3a"
    link = f"<p><a href='{event.source_url}'>View on portal</a></p>" if event.source_url else ""
    return f"""\
<html><body style="font-family:Arial,sans-serif">
  <h2 style="color:{color}">{render_subject(event)}</h2>
  <p><b>Project:</b> {event.project_name or '—'}<br>
     <b>Permit #:</b> {event.permit_number}<br>
     <b>County:</b> {event.county_name or event.county}<br>
     <b>Category:</b> {event.category or '—'}</p>
  <table border="1" cellspacing="0" style="border-collapse:collapse">
     <tr><th style="padding:4px 10px">Field</th>
         <th style="padding:4px 10px">Was</th>
         <th style="padding:4px 10px">Now</th></tr>
     {rows}
  </table>
  {link}
  <p style="color:#888;font-size:12px">Detected {event.detected_at}</p>
</body></html>"""


# ── Delivery ────────────────────────────────────────────────────────────────


class FieldManagerNotifier:
    """Renders a StatusEvent and delivers it to each assigned field manager."""

    def __init__(self, config: dict[str, Any] | None = None, dry_run: bool = False):
        self.config = config or {}
        self.dry_run = dry_run
        # Sink for captured messages in dry-run / tests: list[dict]
        self.captured: list[dict[str, Any]] = []

    def notify(self, event: StatusEvent, managers: list[FieldManager]) -> list[dict[str, Any]]:
        """Deliver ``event`` to every manager. Returns per-attempt results."""
        results: list[dict[str, Any]] = []
        if not managers:
            logger.warning("No managers to notify for permit %s", event.permit_number)
            event.notify_results = results
            return results

        for mgr in managers:
            for channel in mgr.channels or ["console"]:
                result = self._deliver(channel, event, mgr)
                results.append(result)

        event.notify_results = results
        event.notified = any(r.get("ok") for r in results)
        return results

    # ── per-channel dispatch ────────────────────────────────────────────────

    def _deliver(self, channel: str, event: StatusEvent, mgr: FieldManager) -> dict[str, Any]:
        base = {"manager": mgr.id, "channel": channel}
        try:
            if self.dry_run:
                payload = self._preview(channel, event, mgr)
                record = {**base, "ok": True, "dry_run": True, "preview": payload}
                self.captured.append(record)
                logger.info("[dry-run] %s → %s (%s)", event.permit_number, mgr.id, channel)
                return record

            if channel == "console":
                self._send_console(event, mgr)
            elif channel == "sms":
                self._send_sms(event, mgr)
            elif channel == "slack":
                self._send_slack(event, mgr)
            elif channel == "email":
                self._send_email(event, mgr)
            elif channel == "webhook":
                self._send_webhook(event, mgr)
            else:
                return {**base, "ok": False, "error": f"unknown channel '{channel}'"}
            return {**base, "ok": True}
        except Exception as exc:  # best-effort per channel
            logger.error("Notify %s via %s failed: %s", mgr.id, channel, exc)
            return {**base, "ok": False, "error": str(exc)}

    def _preview(self, channel: str, event: StatusEvent, mgr: FieldManager) -> str:
        if channel == "sms":
            return render_sms(event)
        if channel == "slack":
            return json.dumps(render_slack(event))
        if channel == "email":
            return render_subject(event)
        return render_text(event)

    # ── channels ────────────────────────────────────────────────────────────

    def _send_console(self, event: StatusEvent, mgr: FieldManager) -> None:
        header = f"── notify {mgr.name} <{mgr.id}> " + "─" * 20
        print(header)
        print(render_text(event))
        print("─" * len(header))

    def _send_sms(self, event: StatusEvent, mgr: FieldManager) -> None:
        if not mgr.phone:
            raise ValueError(f"manager {mgr.id} has no phone number for SMS")
        body = render_sms(event)

        # Preferred: generic SMS webhook (works with any SMS gateway/dispatcher)
        sms_webhook = self.config.get("sms_webhook") or os.environ.get("SMS_WEBHOOK_URL")
        if sms_webhook:
            resp = requests.post(
                sms_webhook,
                json={"to": mgr.phone, "message": body, "priority": event.priority},
                timeout=10,
            )
            resp.raise_for_status()
            return

        # Otherwise: Twilio REST API
        sid = self.config.get("twilio_sid") or os.environ.get("TWILIO_ACCOUNT_SID")
        token = self.config.get("twilio_token") or os.environ.get("TWILIO_AUTH_TOKEN")
        from_num = self.config.get("twilio_from") or os.environ.get("TWILIO_FROM_NUMBER")
        if not (sid and token and from_num):
            raise ValueError(
                "SMS not configured: set SMS_WEBHOOK_URL, or "
                "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER"
            )
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": from_num, "To": mgr.phone, "Body": body},
            auth=(sid, token),
            timeout=10,
        )
        resp.raise_for_status()

    def _send_slack(self, event: StatusEvent, mgr: FieldManager) -> None:
        url = mgr.slack_webhook or self.config.get("slack_webhook") or os.environ.get("SLACK_WEBHOOK_URL")
        if not url:
            raise ValueError("no Slack webhook (manager.slack_webhook / SLACK_WEBHOOK_URL)")
        resp = requests.post(url, json=render_slack(event), timeout=10)
        resp.raise_for_status()

    def _send_email(self, event: StatusEvent, mgr: FieldManager) -> None:
        if not mgr.email:
            raise ValueError(f"manager {mgr.id} has no email address")
        host = self.config.get("smtp_host") or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        port = int(self.config.get("smtp_port") or os.environ.get("SMTP_PORT", 587))
        user = self.config.get("smtp_user") or os.environ.get("SMTP_USER", "")
        password = self.config.get("smtp_pass") or os.environ.get("SMTP_PASS", "")
        from_addr = self.config.get("smtp_from") or user

        msg = MIMEMultipart("alternative")
        msg["Subject"] = render_subject(event)
        msg["From"] = from_addr
        msg["To"] = mgr.email
        msg.attach(MIMEText(render_text(event), "plain"))
        msg.attach(MIMEText(render_email_html(event), "html"))

        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [mgr.email], msg.as_string())

    def _send_webhook(self, event: StatusEvent, mgr: FieldManager) -> None:
        url = self.config.get("webhook_url") or os.environ.get("WEBHOOK_URL")
        if not url:
            raise ValueError("no generic webhook URL (webhook_url / WEBHOOK_URL)")
        payload = {
            "event": "permit_status_update",
            "manager": {"id": mgr.id, "name": mgr.name},
            "permit": event.to_dict(),
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
