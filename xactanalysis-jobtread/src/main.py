"""XactAnalysis → JobTread bridge entry point.

Polls the company's claims mailbox for XactAnalysis assignment-notification
emails and creates a JobTread lead (customer + location + job) for each new
claim. Never contacts any Verisk system.

Usage:
  python -m src.main --once --dry-run   # parse pending mail, print, create nothing
  python -m src.main --once             # process pending mail once
  python -m src.main                    # poll forever (POLL_SECONDS interval)
"""

import argparse
import logging
import os
import re
import time

from .config import Config
from .email_client import MailboxClient, extract_text
from .jobtread import JobTreadClient, JobTreadError
from .parser import parse_assignment_email
from .state import State

log = logging.getLogger("bridge")


def _sender_allowed(message, allowed_substrings) -> bool:
    if not allowed_substrings:
        return True
    sender = (message.get("From") or "").lower()
    return any(s in sender for s in allowed_substrings)


def _archive(archive_dir: str, message_id: str, body: str) -> None:
    os.makedirs(archive_dir, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", message_id or "no-message-id")[:120]
    path = os.path.join(archive_dir, f"{safe_name}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def process_mailbox(config: Config, dry_run: bool = False) -> int:
    """Process all unseen messages. Returns the number of leads created."""
    state = State(config.state_file)
    jobtread = JobTreadClient(
        config.jobtread_grant_key, config.jobtread_org_id, config.jobtread_api_url
    )
    created = 0

    with MailboxClient(
        config.imap_host,
        config.imap_port,
        config.imap_user,
        config.imap_password,
        config.imap_folder,
    ) as mailbox:
        for uid, message in mailbox.unseen_messages():
            subject = message.get("Subject", "")
            message_id = message.get("Message-ID", "").strip()

            if not _sender_allowed(message, config.sender_filter):
                log.info("Skipping non-XactAnalysis sender: %r", message.get("From"))
                mailbox.mark_seen(uid)
                continue

            if state.seen_message(message_id):
                log.info("Already processed message %s, skipping", message_id)
                mailbox.mark_seen(uid)
                continue

            body = extract_text(message)
            lead = parse_assignment_email(body, subject=subject, message_id=message_id)

            if not lead.is_assignment:
                log.info("Not an assignment notification (subject=%r), skipping", subject)
                mailbox.mark_seen(uid)
                continue

            if state.seen_claim(lead.claim_number):
                log.info("Claim %s already has a lead, skipping duplicate", lead.claim_number)
                state.record(message_id, lead.claim_number, None)
                mailbox.mark_seen(uid)
                continue

            if dry_run:
                log.info("[dry-run] Would create lead: %s", lead.job_name())
                print("-" * 60)
                print(lead.description())
                continue

            try:
                result = jobtread.create_lead(lead, account_type=config.jobtread_account_type)
            except JobTreadError:
                log.exception(
                    "JobTread create failed for claim %s; leaving email unseen for retry",
                    lead.claim_number,
                )
                continue

            state.record(message_id, lead.claim_number, result["job_id"])
            _archive(config.archive_dir, message_id, body)
            mailbox.mark_seen(uid)
            created += 1

    return created


def main() -> None:
    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("--once", action="store_true", help="run one pass and exit")
    arg_parser.add_argument(
        "--dry-run", action="store_true", help="parse and print leads without creating anything"
    )
    args = arg_parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    config = Config()

    if args.once:
        created = process_mailbox(config, dry_run=args.dry_run)
        log.info("Done. Leads created: %d", created)
        return

    log.info("Polling %s every %ds", config.imap_user, config.poll_seconds)
    while True:
        try:
            process_mailbox(config, dry_run=args.dry_run)
        except Exception:
            log.exception("Pass failed; will retry next interval")
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    main()
