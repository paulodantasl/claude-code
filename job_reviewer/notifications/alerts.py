"""
Flag matched jobs for human review.

Channels (all optional, configured via env / CLI):
  • console — always on; prints a Rich panel
  • slack   — SLACK_WEBHOOK_URL
  • email   — SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / ALERT_EMAIL_TO

The message always says these are DRAFTS awaiting your review — the system
never submits an application on its own.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from typing import Any

import requests

logger = logging.getLogger(__name__)


class AlertManager:
    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        self.slack_webhook = config.get("slack_webhook") or os.environ.get("SLACK_WEBHOOK_URL")
        self.smtp_host = config.get("smtp_host") or os.environ.get("SMTP_HOST")
        self.smtp_port = int(config.get("smtp_port") or os.environ.get("SMTP_PORT", 587))
        self.smtp_user = config.get("smtp_user") or os.environ.get("SMTP_USER")
        self.smtp_pass = config.get("smtp_pass") or os.environ.get("SMTP_PASS")
        self.email_to = config.get("email_to") or os.environ.get("ALERT_EMAIL_TO") or self.smtp_user

    def send(self, job) -> None:
        """Send a 'flagged for review' alert for a single job."""
        subject = f"[Job match {job.fit_score:.0f}%] {job.title} — {job.agency_name}"
        body = self._format_body(job)
        if self.slack_webhook:
            self._send_slack(subject, body, job)
        if self.smtp_host and self.smtp_user and self.smtp_pass:
            self._send_email(subject, body)

    # ── Formatting ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_body(job) -> str:
        lines = [
            f"*{job.title}* — {job.agency_name}",
            f"Fit: {job.fit_score:.0f}/100   Recommendation: {job.recommendation or 'n/a'}",
        ]
        if job.salary_raw:
            lines.append(f"Salary: {job.salary_raw}")
        if job.closing_date:
            lines.append(f"Closes: {job.closing_date:%Y-%m-%d}")
        if job.fit_reasons:
            lines.append(f"\n{job.fit_reasons}")
        if job.apply_url:
            lines.append(f"\nApply: {job.apply_url}")
        if job.packet_path:
            lines.append(f"Draft packet: {job.packet_path}")
        lines.append("\n⚠️ Draft only — review and submit it yourself.")
        return "\n".join(lines)

    # ── Channels ────────────────────────────────────────────────────────────

    def _send_slack(self, subject: str, body: str, job) -> None:
        try:
            requests.post(
                self.slack_webhook,
                json={
                    "text": f":briefcase: {subject}",
                    "blocks": [
                        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
                    ],
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.error("Slack alert failed: %s", exc)

    def _send_email(self, subject: str, body: str) -> None:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = self.email_to
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
        except Exception as exc:
            logger.error("Email alert failed: %s", exc)
