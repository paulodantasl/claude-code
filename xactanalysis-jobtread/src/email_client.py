"""Read-only IMAP access to the company's claims mailbox.

This module talks to *your* mail server only. It fetches unseen messages,
hands them to the parser, and marks them seen once processed. It has no
knowledge of, and no credentials for, any Verisk system.
"""

import email
import email.policy
import imaplib
import logging
from email.message import EmailMessage
from typing import Iterator, Tuple

log = logging.getLogger(__name__)


class MailboxClient:
    def __init__(self, host: str, port: int, user: str, password: str, folder: str = "INBOX"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.folder = folder
        self._conn = None

    def __enter__(self) -> "MailboxClient":
        self._conn = imaplib.IMAP4_SSL(self.host, self.port)
        self._conn.login(self.user, self.password)
        self._conn.select(self.folder)
        return self

    def __exit__(self, *exc) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
                self._conn.logout()
            except imaplib.IMAP4.error:
                pass

    def unseen_messages(self) -> Iterator[Tuple[bytes, EmailMessage]]:
        """Yield (uid, message) for every unseen message in the folder."""
        status, data = self._conn.uid("SEARCH", None, "UNSEEN")
        if status != "OK":
            log.error("IMAP search failed: %s", status)
            return
        uids = data[0].split()
        log.info("Found %d unseen message(s)", len(uids))
        for uid in uids:
            status, msg_data = self._conn.uid("FETCH", uid, "(BODY.PEEK[])")
            if status != "OK" or not msg_data or msg_data[0] is None:
                log.warning("Could not fetch message uid=%s", uid)
                continue
            raw = msg_data[0][1]
            message = email.message_from_bytes(raw, policy=email.policy.default)
            yield uid, message

    def mark_seen(self, uid: bytes) -> None:
        self._conn.uid("STORE", uid, "+FLAGS", "(\\Seen)")


def extract_text(message: EmailMessage) -> str:
    """Return the best-effort plain text of an email (text/plain preferred,
    stripped text/html as fallback)."""
    body = message.get_body(preferencelist=("plain",))
    if body is not None:
        return body.get_content()
    body = message.get_body(preferencelist=("html",))
    if body is not None:
        return _strip_html(body.get_content())
    # Non-multipart fallback
    payload = message.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace")
    return str(payload or "")


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    # Preserve line structure so "Label: value" rows survive tag removal.
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6]|table)>", "\n", text)
    text = re.sub(r"(?i)</t[dh]>", ": ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()
